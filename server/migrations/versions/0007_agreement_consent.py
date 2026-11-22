"""Agreements, recovery cases, append-only guard, consent_record and dispute_case

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-22
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# SQL copied from docs/03-design/sql/schema.sql (v5); RLS and grants live in the same revision as the table (ADR-0005).


def upgrade() -> None:
    op.execute("""
-- v3: no template_id — the text comes from zone_policy.agreement_template_md of the pinned zone_policy_id
-- (agreement_template table removed, docs/03-design/08-deferred-tables.md).
CREATE TABLE app.agreement (
  id                    uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  zone_id               uuid NOT NULL,             -- zone of the slot: its policy and price frame (AC-07)
  booking_id            uuid NOT NULL UNIQUE,
  zone_policy_id        uuid NOT NULL,             -- policy version used for price / fees / template
  provider_user_id      uuid NOT NULL REFERENCES app.app_user (id) ON DELETE RESTRICT,
  renter_user_id        uuid NOT NULL REFERENCES app.app_user (id) ON DELETE RESTRICT,
  price_vnd             bigint NOT NULL CHECK (price_vnd >= 0),
  -- Rendered text is immutable evidence; its hash goes into consent_record.evidence.
  body_rendered         text NOT NULL,
  body_sha256           bytea NOT NULL CHECK (length(body_sha256) = 32),
  status                app.agreement_status NOT NULL DEFAULT 'pending_confirmation',
  requires_approval     boolean NOT NULL,          -- price over zone threshold (BR-12), decided by rule engine
  approval_request_id   uuid,
  confirm_deadline      timestamptz NOT NULL,
  provider_confirmed_at timestamptz,
  renter_confirmed_at   timestamptz,
  effective_at          timestamptz,
  created_at            timestamptz NOT NULL DEFAULT now(),
  updated_at            timestamptz NOT NULL DEFAULT now(),
  UNIQUE (id, zone_id),
  FOREIGN KEY (booking_id, zone_id) REFERENCES app.booking (id, zone_id) ON DELETE RESTRICT,
  FOREIGN KEY (zone_policy_id, zone_id) REFERENCES app.zone_policy (id, zone_id) ON DELETE RESTRICT,
  FOREIGN KEY (approval_request_id, zone_id) REFERENCES app.approval_request (id, zone_id) ON DELETE RESTRICT,
  -- AC-07: effective only when both parties confirmed; AC-15: and approved when over threshold.
  CHECK (status <> 'effective' OR (provider_confirmed_at IS NOT NULL AND renter_confirmed_at IS NOT NULL
                                   AND effective_at IS NOT NULL
                                   AND (NOT requires_approval OR approval_request_id IS NOT NULL))),
  CHECK (status <> 'pending_approval' OR (requires_approval AND approval_request_id IS NOT NULL))
);
CREATE INDEX agreement_provider_idx ON app.agreement (provider_user_id);
CREATE INDEX agreement_renter_idx ON app.agreement (renter_user_id);
CREATE INDEX agreement_policy_idx ON app.agreement (zone_policy_id);
CREATE INDEX agreement_approval_idx ON app.agreement (approval_request_id) WHERE approval_request_id IS NOT NULL;
CREATE INDEX agreement_deadline_idx ON app.agreement (confirm_deadline) WHERE status = 'pending_confirmation';

-- Append-only guard, even for the table owner (grants alone do not stop the owner). Statement-level, so even an
-- UPDATE/DELETE that matches no row is refused. No purge path exists in the MVP (retention enforcement is deferred,
-- docs/03-design/08-deferred-tables.md). Used by consent_record and ai_decision_log.
CREATE FUNCTION app.reject_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION '% is append-only (% rejected)', TG_TABLE_NAME, TG_OP USING ERRCODE = 'insufficient_privilege';
END $$;

-- W3 (owner returns early, Ưu tiên 2): one open case per booking. The rule engine fills `options` (candidate slots and
-- prices); the LLM only words the proposal (BR-14). A resolved case points at the replacement booking.
CREATE TABLE app.recovery_case (
  id                   uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  zone_id              uuid NOT NULL,
  booking_id           uuid NOT NULL,                -- the booking hit by the early return
  trigger              app.recovery_trigger NOT NULL DEFAULT 'owner_early_return',
  new_return_at        timestamptz NOT NULL,
  options              jsonb NOT NULL DEFAULT '[]' CHECK (jsonb_typeof(options) = 'array'),
  chosen_slot_id       uuid,
  relocated_booking_id uuid,                         -- the replacement booking
  approval_request_id  uuid,                         -- escalation to the BQL
  status               app.recovery_status NOT NULL DEFAULT 'open',
  deadline_at          timestamptz NOT NULL,
  resolution_note      text,
  idempotency_key      text NOT NULL UNIQUE,
  version              integer NOT NULL DEFAULT 1,
  created_at           timestamptz NOT NULL DEFAULT now(),
  updated_at           timestamptz NOT NULL DEFAULT now(),
  UNIQUE (id, zone_id),
  FOREIGN KEY (booking_id, zone_id) REFERENCES app.booking (id, zone_id) ON DELETE RESTRICT,
  FOREIGN KEY (chosen_slot_id, zone_id) REFERENCES app.slot (id, zone_id) ON DELETE RESTRICT,
  FOREIGN KEY (relocated_booking_id, zone_id) REFERENCES app.booking (id, zone_id) ON DELETE RESTRICT,
  FOREIGN KEY (approval_request_id, zone_id) REFERENCES app.approval_request (id, zone_id) ON DELETE RESTRICT,
  CONSTRAINT recovery_case_resolved_has_booking CHECK (status <> 'resolved' OR relocated_booking_id IS NOT NULL),
  CONSTRAINT recovery_case_escalated_has_approval CHECK (status <> 'escalated' OR approval_request_id IS NOT NULL)
);
CREATE UNIQUE INDEX recovery_case_open_uq ON app.recovery_case (booking_id) WHERE status NOT IN ('resolved', 'cancelled');
CREATE INDEX recovery_case_zone_idx ON app.recovery_case (zone_id, deadline_at) WHERE status NOT IN ('resolved', 'cancelled');
CREATE INDEX recovery_case_relocated_idx ON app.recovery_case (relocated_booking_id) WHERE relocated_booking_id IS NOT NULL;
CREATE INDEX recovery_case_approval_idx ON app.recovery_case (approval_request_id) WHERE approval_request_id IS NOT NULL;
CREATE INDEX recovery_case_slot_idx ON app.recovery_case (chosen_slot_id) WHERE chosen_slot_id IS NOT NULL;

-- A resident reports a problem at slot S: the case lives in the zone of S, so it reaches that zone's BQL (BR-18). W5 collects
-- evidence (dispute_evidence, section 18), the vision model only SUGGESTS (BR-14), the BQL decides through an approval_request
-- of kind dispute_decision. v2's dispute_ticket + dispute_party are folded into reporter / respondent columns.
CREATE TABLE app.dispute_case (
  id                  uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  ref_no              bigint GENERATED ALWAYS AS IDENTITY UNIQUE,   -- shown as TC-0031
  zone_id             uuid NOT NULL,                    -- zone of the slot (BR-18): routes the case to its BQL
  slot_id             uuid NOT NULL,
  booking_id          uuid,                             -- when the dispute concerns a booking (NULL otherwise)
  reporter_user_id    uuid NOT NULL REFERENCES app.app_user (id) ON DELETE RESTRICT,
  -- Resolved from the booking / LPR match (plate hash), never from a raw plate; NULL while unknown.
  respondent_user_id  uuid REFERENCES app.app_user (id) ON DELETE RESTRICT,
  category            app.dispute_category NOT NULL,
  description         text NOT NULL CHECK (btrim(description) <> ''),   -- stored after plate masking (BR-09)
  status              app.dispute_status NOT NULL DEFAULT 'open',
  -- Pseudonymised AI suggestion, never a verdict (BR-14).
  ai_summary          text,
  ai_confidence       numeric(4,3) CHECK (ai_confidence BETWEEN 0 AND 1),
  thread_id           text REFERENCES app.agent_thread (thread_id) ON DELETE RESTRICT,   -- the W5 thread
  approval_request_id uuid,                             -- BQL decision (HITL), kind dispute_decision
  ready_at            timestamptz,                      -- evidence complete: KPI "thời gian lập hồ sơ tranh chấp"
  -- Final outcome chosen by the BQL. 'fee_waived' (overstay): the overstay_fee payment is set to 'cancelled'.
  resolution_code     text CHECK (resolution_code IN ('fee_waived', 'upheld', 'rejected', 'other')),
  resolution_note     text,
  resolved_by         uuid REFERENCES app.app_user (id) ON DELETE RESTRICT,
  resolved_at         timestamptz,
  idempotency_key     text NOT NULL UNIQUE,             -- thread_id:step or client request id
  version             integer NOT NULL DEFAULT 1,
  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now(),
  UNIQUE (id, zone_id),
  -- With booking_id / approval_request_id NULL the composite FKs are skipped (MATCH SIMPLE), as intended.
  FOREIGN KEY (slot_id, zone_id) REFERENCES app.slot (id, zone_id) ON DELETE RESTRICT,
  FOREIGN KEY (booking_id, zone_id) REFERENCES app.booking (id, zone_id) ON DELETE RESTRICT,
  FOREIGN KEY (approval_request_id, zone_id) REFERENCES app.approval_request (id, zone_id) ON DELETE RESTRICT,
  CONSTRAINT dispute_case_parties_differ CHECK (respondent_user_id IS NULL OR respondent_user_id <> reporter_user_id),
  CONSTRAINT dispute_case_resolution_consistent CHECK (
        ((status IN ('resolved', 'dismissed')) = (resolved_by IS NOT NULL AND resolved_at IS NOT NULL))
    AND ((resolved_by IS NULL) = (resolved_at IS NULL))),
  CONSTRAINT dispute_case_resolution_code_final CHECK (resolution_code IS NULL OR status IN ('resolved', 'dismissed')),
  CONSTRAINT dispute_case_ready_before_decision CHECK (
    status NOT IN ('awaiting_decision', 'resolved', 'dismissed') OR ready_at IS NOT NULL)
);
-- BQL queue.
CREATE INDEX dispute_case_queue_idx ON app.dispute_case (zone_id, status, created_at DESC);
-- Later repeat-dispute job (N5 / M11).
CREATE INDEX dispute_case_slot_idx ON app.dispute_case (slot_id, created_at DESC);
CREATE INDEX dispute_case_reporter_idx ON app.dispute_case (reporter_user_id, created_at DESC);
CREATE INDEX dispute_case_respondent_idx ON app.dispute_case (respondent_user_id) WHERE respondent_user_id IS NOT NULL;
CREATE INDEX dispute_case_booking_idx ON app.dispute_case (booking_id) WHERE booking_id IS NOT NULL;
CREATE INDEX dispute_case_approval_idx ON app.dispute_case (approval_request_id) WHERE approval_request_id IS NOT NULL;
CREATE INDEX dispute_case_thread_idx ON app.dispute_case (thread_id) WHERE thread_id IS NOT NULL;
-- Against double reports. NULLs are distinct in a unique index, so a case without a booking would escape the first index:
-- it is deduplicated per slot by the second one (same reporter, same slot, same category, still open).
CREATE UNIQUE INDEX dispute_case_open_booking_uq ON app.dispute_case (reporter_user_id, booking_id, category)
  WHERE booking_id IS NOT NULL AND status NOT IN ('resolved', 'dismissed');
CREATE UNIQUE INDEX dispute_case_open_slot_uq ON app.dispute_case (reporter_user_id, slot_id, category)
  WHERE booking_id IS NULL AND status NOT IN ('resolved', 'dismissed');

-- Evidence of consent / confirmation (A-03, BR-09, FR-09, AC-07). Written once, never changed. evidence holds ids, hashes
-- and amounts only (e.g. body_sha256, price, policy version) — no names, no plates.
CREATE TABLE app.consent_record (
  id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id       uuid NOT NULL REFERENCES app.app_user (id) ON DELETE RESTRICT,
  zone_id       uuid REFERENCES app.zone (id) ON DELETE RESTRICT,   -- NULL for chain-wide terms (registration)
  action        app.consent_action NOT NULL,
  subject_type  text NOT NULL CHECK (subject_type IN ('app_user', 'agreement', 'recovery_case')),
  subject_id    uuid NOT NULL,
  terms_version text NOT NULL CHECK (btrim(terms_version) <> ''),
  decision      app.consent_decision NOT NULL,
  evidence      jsonb NOT NULL DEFAULT '{}' CHECK (jsonb_typeof(evidence) = 'object'),
  created_at    timestamptz NOT NULL DEFAULT now(),
  -- Natural idempotency: a replayed confirmation does not add a second row.
  CONSTRAINT consent_record_natural_uq UNIQUE (user_id, action, subject_id, terms_version, decision)
);
CREATE INDEX consent_record_subject_idx ON app.consent_record (subject_type, subject_id);
CREATE INDEX consent_record_zone_idx ON app.consent_record (zone_id, created_at DESC) WHERE zone_id IS NOT NULL;
CREATE TRIGGER consent_record_append_only BEFORE UPDATE OR DELETE OR TRUNCATE ON app.consent_record
  FOR EACH STATEMENT EXECUTE FUNCTION app.reject_mutation();

-- updated_at maintenance (v5 section 18)
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['agreement', 'recovery_case', 'dispute_case'] LOOP
    EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE ON app.%I
                    FOR EACH ROW EXECUTE FUNCTION app.set_updated_at()', t || '_updated_at', t);
  END LOOP;
END $$;

-- RLS (v5 sections 20.4, 20.5, 20.7, 20.9)
ALTER TABLE app.agreement ENABLE ROW LEVEL SECURITY;
CREATE POLICY parties_read ON app.agreement FOR SELECT
  USING (renter_user_id = (SELECT app.ctx_user_id()) OR provider_user_id = (SELECT app.ctx_user_id()));
CREATE POLICY zone_staff ON app.agreement FOR ALL
  USING (app.is_zone_staff(zone_id, '{zone_manager,system,guard}'))
  WITH CHECK (app.is_zone_staff(zone_id));

ALTER TABLE app.recovery_case ENABLE ROW LEVEL SECURITY;
CREATE POLICY parties_read ON app.recovery_case FOR SELECT
  USING (EXISTS (SELECT 1 FROM app.booking b WHERE b.id = recovery_case.booking_id
                   AND (b.renter_user_id = (SELECT app.ctx_user_id()) OR b.provider_user_id = (SELECT app.ctx_user_id()))));
CREATE POLICY zone_staff ON app.recovery_case FOR ALL
  USING (app.is_zone_staff(zone_id)) WITH CHECK (app.is_zone_staff(zone_id));

-- 20.7 Disputes (v5). BR-18: the BQL of the slot's zone works the queue; reporter and respondent see their own case only.
ALTER TABLE app.dispute_case ENABLE ROW LEVEL SECURITY;
CREATE POLICY zone_staff ON app.dispute_case FOR ALL
  USING (app.is_zone_staff(zone_id)) WITH CHECK (app.is_zone_staff(zone_id));
CREATE POLICY system_all ON app.dispute_case FOR ALL
  USING ((SELECT app.ctx_role()) = 'system') WITH CHECK ((SELECT app.ctx_role()) = 'system');
CREATE POLICY parties_read ON app.dispute_case FOR SELECT
  USING (reporter_user_id = (SELECT app.ctx_user_id()) OR respondent_user_id = (SELECT app.ctx_user_id()));
-- A resident files a case for themselves; everything after that (status, AI fields, decision) is written by system / BQL.
-- The respondent is derived by system / W5 from the booking or the LPR match, never named by the reporter (no accusing an
-- arbitrary user); a linked booking must be one the reporter is a party to (IDOR), and a linked thread must be their own.
-- The EXISTS sub-selects run under booking / agent_thread RLS, whose policies never look at dispute_case (no recursion).
CREATE POLICY reporter_insert ON app.dispute_case FOR INSERT
  WITH CHECK (reporter_user_id = (SELECT app.ctx_user_id()) AND status = 'open'
              AND respondent_user_id IS NULL AND ai_summary IS NULL AND ai_confidence IS NULL
              AND ready_at IS NULL AND approval_request_id IS NULL
              AND resolution_code IS NULL AND resolution_note IS NULL AND resolved_by IS NULL AND resolved_at IS NULL
              AND (booking_id IS NULL OR EXISTS (
                     SELECT 1 FROM app.booking b WHERE b.id = booking_id
                       AND (SELECT app.ctx_user_id()) IN (b.renter_user_id, b.provider_user_id)))
              AND (thread_id IS NULL OR EXISTS (
                     SELECT 1 FROM app.agent_thread t WHERE t.thread_id = dispute_case.thread_id
                       AND t.user_id = (SELECT app.ctx_user_id()))));

ALTER TABLE app.consent_record ENABLE ROW LEVEL SECURITY;
CREATE POLICY own ON app.consent_record FOR SELECT USING (user_id = (SELECT app.ctx_user_id()));
CREATE POLICY own_insert ON app.consent_record FOR INSERT WITH CHECK (user_id = (SELECT app.ctx_user_id()));
CREATE POLICY zone_manager_read ON app.consent_record FOR SELECT USING (app.is_zone_staff(zone_id, '{zone_manager}'));
CREATE POLICY system_all ON app.consent_record FOR ALL
  USING ((SELECT app.ctx_role()) = 'system') WITH CHECK ((SELECT app.ctx_role()) = 'system');

-- Grants (v5 section 21). Append-only consent_record: INSERT + SELECT only (reject_mutation also stops the owner).
GRANT SELECT, INSERT, UPDATE ON app.agreement, app.recovery_case, app.dispute_case TO parksmart_app;
GRANT SELECT, INSERT ON app.consent_record TO parksmart_app;
REVOKE UPDATE, DELETE, TRUNCATE ON app.consent_record FROM parksmart_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA app TO parksmart_app;
REVOKE ALL ON FUNCTION app.reject_mutation() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.reject_mutation() TO parksmart_app;
""")


def downgrade() -> None:
    op.execute("""
DROP TABLE app.consent_record;
DROP TABLE app.dispute_case;
DROP TABLE app.recovery_case;
DROP TABLE app.agreement;
DROP FUNCTION app.reject_mutation();
""")
