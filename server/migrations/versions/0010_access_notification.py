"""Access (lpr_event), notification and dispute_evidence

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-22
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# SQL copied from docs/03-design/sql/schema.sql (v5); RLS and grants live in the same revision as the table (ADR-0005).


def upgrade() -> None:
    op.execute("""
-- v3: the gate and lpr_source tables are merged into gate_code / source_code (the OCR threshold moved to
-- zone_policy.ocr_review_threshold); parking_session, overstay_case and plate_access_log are removed
-- (v5: overstay needs no table — booking.checked_*_at + zone_policy.overstay_*; the logged plate reveal stays deferred) — see docs/03-design/08-deferred-tables.md.
-- Plain table in the MVP (no partitioning, no retention purge); at scale see docs/03-design/08-deferred-tables.md.
CREATE TABLE app.lpr_event (
  id                 bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  zone_id            uuid NOT NULL REFERENCES app.zone (id) ON DELETE RESTRICT,
  source_code        text NOT NULL CHECK (btrim(source_code) <> '' AND length(source_code) <= 64),
  source_event_id    text NOT NULL CHECK (length(source_event_id) BETWEEN 1 AND 128),
  gate_code          text NOT NULL CHECK (gate_code ~ '^[A-Z0-9_-]{1,32}$'),     -- G1, G2
  direction          app.gate_direction NOT NULL,
  occurred_at        timestamptz NOT NULL,
  received_at        timestamptz NOT NULL DEFAULT now(),
  plate_ciphertext   bytea,                        -- NULL when OCR read nothing; never selectable by the app role
  plate_hash         bytea CHECK (plate_hash IS NULL OR length(plate_hash) = 32),
  plate_masked       text,
  ocr_confidence     numeric(4,3) NOT NULL CHECK (ocr_confidence BETWEEN 0 AND 1),
  status             app.lpr_status NOT NULL,
  matched_vehicle_id uuid REFERENCES app.vehicle (id) ON DELETE SET NULL,
  matched_booking_id uuid REFERENCES app.booking (id) ON DELETE SET NULL,
  -- RESTRICT, not SET NULL: the CHECK below requires a reviewer for reviewed rows (check c).
  reviewed_by        uuid REFERENCES app.app_user (id) ON DELETE RESTRICT,
  reviewed_at        timestamptz,
  UNIQUE (zone_id, source_code, source_event_id),                   -- BR-13 / AC-10a dedupe (vendor re-sends)
  CHECK ((plate_ciphertext IS NULL) = (plate_hash IS NULL)),
  CHECK (status NOT IN ('confirmed_manual', 'unreadable') OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL))
);

CREATE INDEX lpr_event_zone_time_idx ON app.lpr_event (zone_id, occurred_at DESC);
CREATE INDEX lpr_event_review_idx ON app.lpr_event (zone_id, occurred_at) WHERE status = 'pending_review';
CREATE INDEX lpr_event_plate_idx ON app.lpr_event (plate_hash, occurred_at DESC) WHERE plate_hash IS NOT NULL;
CREATE INDEX lpr_event_booking_idx ON app.lpr_event (matched_booking_id) WHERE matched_booking_id IS NOT NULL;
CREATE INDEX lpr_event_vehicle_idx ON app.lpr_event (matched_vehicle_id) WHERE matched_vehicle_id IS NOT NULL;

-- 16. Notifications (M13)
-- -----------------------------------------------------------------------------------------------------
CREATE TABLE app.notification (
  id              uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  user_id         uuid NOT NULL REFERENCES app.app_user (id) ON DELETE CASCADE,
  zone_id         uuid REFERENCES app.zone (id) ON DELETE RESTRICT,
  kind            text NOT NULL CHECK (kind ~ '^[a-z_]{2,60}$'),
  title           text NOT NULL,
  body            text NOT NULL,
  link            jsonb CHECK (link IS NULL OR jsonb_typeof(link) = 'object'),  -- {"type":"agreement","id":…}
  idempotency_key text NOT NULL UNIQUE,            -- use case step key: a retry does not duplicate (no outbox, ADR-0011)
  read_at         timestamptz,
  created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX notification_inbox_idx ON app.notification (user_id, created_at DESC, id DESC);
CREATE INDEX notification_unread_idx ON app.notification (user_id) WHERE read_at IS NULL;

-- RLS (v5 sections 20.2, 20.6)
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['notification'] LOOP
    EXECUTE format('ALTER TABLE app.%I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format($p$CREATE POLICY own_or_system ON app.%I FOR ALL
                      USING (user_id = (SELECT app.ctx_user_id()) OR (SELECT app.ctx_role()) IN ('auth', 'system'))
                      WITH CHECK (user_id = (SELECT app.ctx_user_id()) OR (SELECT app.ctx_role()) IN ('auth', 'system'))$p$, t);
  END LOOP;
END $$;

-- 20.6 Access / LPR: BQL, guards and system jobs of the zone.
ALTER TABLE app.lpr_event ENABLE ROW LEVEL SECURITY;
CREATE POLICY zone_staff ON app.lpr_event FOR ALL
  USING (app.is_zone_staff(zone_id, '{zone_manager,guard,system}'))
  WITH CHECK (app.is_zone_staff(zone_id, '{zone_manager,guard,system}'));

-- v5: evidence of a dispute (section 14), append-only like consent_record. Defined here because it references consent_record.
-- Per kind: photo -> object keys + sha256; lpr_event -> id + snapshot; consent_record / agreement -> their id;
-- ai_vision_extraction -> confidence + snapshot; note -> snapshot {"text": ...}. The reference columns are only for their kind.
-- lpr_event and consent_record have no UNIQUE (id, zone_id), so their FKs are plain: the zone match of those two is an
-- application rule (W5 collects them inside the case's zone) and RLS hides other zones; agreement has the pair and uses it.
CREATE TABLE app.dispute_evidence (
  id                   bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  zone_id              uuid NOT NULL,
  case_id              uuid NOT NULL,
  kind                 app.evidence_kind NOT NULL,
  source               text NOT NULL CHECK (source IN ('reporter', 'system', 'zone_manager')),
  object_key_masked    text CHECK (object_key_masked IS NULL OR btrim(object_key_masked) <> ''),   -- blurred photo: the only image shown
  object_key_original  text CHECK (object_key_original IS NULL OR btrim(object_key_original) <> ''), -- column grant revoked from the app role (like plate_ciphertext)
  sha256               bytea CHECK (sha256 IS NULL OR length(sha256) = 32),                          -- photo hash
  lpr_event_id         bigint REFERENCES app.lpr_event (id) ON DELETE RESTRICT,
  consent_record_id    bigint REFERENCES app.consent_record (id) ON DELETE RESTRICT,
  agreement_id         uuid,
  -- Payload: copy of the LPR event (gate, direction, time, MASKED plate, OCR) so the evidence survives the 90-day LPR
  -- retention (D-05); vision extraction result; or the text of a note. Never plate ciphertext.
  snapshot             jsonb CHECK (snapshot IS NULL OR jsonb_typeof(snapshot) = 'object'),
  confidence           numeric(4,3) CHECK (confidence BETWEEN 0 AND 1),   -- OCR / vision confidence, shown as "Gợi ý"
  submitted_by         uuid REFERENCES app.app_user (id) ON DELETE RESTRICT,   -- NULL for system rows
  created_at           timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (case_id, zone_id) REFERENCES app.dispute_case (id, zone_id) ON DELETE RESTRICT,
  FOREIGN KEY (agreement_id, zone_id) REFERENCES app.agreement (id, zone_id) ON DELETE RESTRICT,
  CONSTRAINT dispute_evidence_kind_required CHECK (CASE kind
      WHEN 'photo'                THEN object_key_masked IS NOT NULL AND object_key_original IS NOT NULL AND sha256 IS NOT NULL
      WHEN 'lpr_event'            THEN lpr_event_id IS NOT NULL AND snapshot IS NOT NULL
      WHEN 'consent_record'       THEN consent_record_id IS NOT NULL
      WHEN 'agreement'            THEN agreement_id IS NOT NULL
      WHEN 'ai_vision_extraction' THEN confidence IS NOT NULL AND snapshot IS NOT NULL
      WHEN 'note'                 THEN snapshot IS NOT NULL
    END),
  CONSTRAINT dispute_evidence_kind_exclusive CHECK (
        (kind = 'photo' OR (object_key_masked IS NULL AND object_key_original IS NULL AND sha256 IS NULL))
    AND (kind = 'lpr_event' OR lpr_event_id IS NULL)
    AND (kind = 'consent_record' OR consent_record_id IS NULL)
    AND (kind = 'agreement' OR agreement_id IS NULL)),
  CONSTRAINT dispute_evidence_submitter CHECK (source = 'system' OR submitted_by IS NOT NULL)
);
CREATE INDEX dispute_evidence_case_idx ON app.dispute_evidence (case_id, created_at);
CREATE INDEX dispute_evidence_zone_idx ON app.dispute_evidence (zone_id, created_at DESC);
-- Idempotent W5 collection: a re-run cannot add the same item twice.
CREATE UNIQUE INDEX dispute_evidence_lpr_uq ON app.dispute_evidence (case_id, lpr_event_id) WHERE lpr_event_id IS NOT NULL;
CREATE UNIQUE INDEX dispute_evidence_consent_uq ON app.dispute_evidence (case_id, consent_record_id) WHERE consent_record_id IS NOT NULL;
CREATE UNIQUE INDEX dispute_evidence_agreement_uq ON app.dispute_evidence (case_id, agreement_id) WHERE agreement_id IS NOT NULL;
CREATE UNIQUE INDEX dispute_evidence_photo_uq ON app.dispute_evidence (case_id, sha256) WHERE kind = 'photo';
CREATE INDEX dispute_evidence_lpr_fk_idx ON app.dispute_evidence (lpr_event_id) WHERE lpr_event_id IS NOT NULL;
CREATE INDEX dispute_evidence_consent_fk_idx ON app.dispute_evidence (consent_record_id) WHERE consent_record_id IS NOT NULL;
CREATE INDEX dispute_evidence_agreement_fk_idx ON app.dispute_evidence (agreement_id) WHERE agreement_id IS NOT NULL;
CREATE TRIGGER dispute_evidence_append_only BEFORE UPDATE OR DELETE OR TRUNCATE ON app.dispute_evidence
  FOR EACH STATEMENT EXECUTE FUNCTION app.reject_mutation();

-- RLS dispute_evidence (v5 section 20.7)
-- dispute_evidence: the policies below only look at dispute_case, and no dispute_case policy looks back at dispute_evidence,
-- so the sub-select cannot recurse. The parties' sub-select runs under dispute_case's own RLS (parties_read), which is
-- exactly "my case". Original object keys are not selectable at all (column grant, section 21).
ALTER TABLE app.dispute_evidence ENABLE ROW LEVEL SECURITY;
CREATE POLICY zone_staff ON app.dispute_evidence FOR ALL
  USING (app.is_zone_staff(zone_id)) WITH CHECK (app.is_zone_staff(zone_id));
CREATE POLICY system_all ON app.dispute_evidence FOR ALL
  USING ((SELECT app.ctx_role()) = 'system') WITH CHECK ((SELECT app.ctx_role()) = 'system');
CREATE POLICY parties_read ON app.dispute_evidence FOR SELECT
  USING (EXISTS (SELECT 1 FROM app.dispute_case c WHERE c.id = dispute_evidence.case_id
                   AND (c.reporter_user_id = (SELECT app.ctx_user_id()) OR c.respondent_user_id = (SELECT app.ctx_user_id()))));
-- The reporter may add photos and notes to their own case while it is open; system / BQL write everything else.
CREATE POLICY reporter_insert ON app.dispute_evidence FOR INSERT
  WITH CHECK (source = 'reporter' AND kind IN ('photo', 'note') AND submitted_by = (SELECT app.ctx_user_id())
              AND EXISTS (SELECT 1 FROM app.dispute_case c WHERE c.id = dispute_evidence.case_id
                            AND c.reporter_user_id = (SELECT app.ctx_user_id())
                            AND c.status NOT IN ('resolved', 'dismissed')));

-- Grants (v5 section 21)
GRANT INSERT, UPDATE ON app.lpr_event TO parksmart_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON app.notification TO parksmart_app;
GRANT SELECT, INSERT ON app.dispute_evidence TO parksmart_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA app TO parksmart_app;
-- Ciphertext: never selectable (masked plates only).
REVOKE SELECT ON app.lpr_event FROM parksmart_app;
GRANT SELECT (id, zone_id, source_code, source_event_id, gate_code, direction, occurred_at, received_at, plate_hash,
              plate_masked, ocr_confidence, status, matched_vehicle_id, matched_booking_id, reviewed_by, reviewed_at)
  ON app.lpr_event TO parksmart_app;
-- dispute_evidence is append-only; the original photo key is not selectable (BR-09).
REVOKE UPDATE, DELETE, TRUNCATE ON app.dispute_evidence FROM parksmart_app;
REVOKE SELECT ON app.dispute_evidence FROM parksmart_app;
GRANT SELECT (id, zone_id, case_id, kind, source, object_key_masked, sha256, lpr_event_id, consent_record_id, agreement_id,
              snapshot, confidence, submitted_by, created_at)
  ON app.dispute_evidence TO parksmart_app;
""")


def downgrade() -> None:
    op.execute("""
DROP TABLE app.dispute_evidence;
DROP TABLE app.notification;
DROP TABLE app.lpr_event;
""")
