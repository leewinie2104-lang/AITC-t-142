"""Pilot one building: queue, OTP, ETA, two-layer approval, registry import, fee ledger (schema v5 -> v7)

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-22

Delta between docs/03-design/sql/schema.sql at v5 (what 0001-0011 build) and v7 (plan 024, BR-20...BR-29).
Safe-change notes (docs/06-operations/01-database-operations.md section 1):
- ALTER TYPE ... ADD VALUE cannot be used in the transaction that adds it (the 'queued' CHECK below needs it), so the
  six ADD VALUEs run first in an autocommit block with IF NOT EXISTS (re-runnable if a later statement fails).
- The pilot tables are empty when this runs: NOT NULL / CHECK constraints are added directly (no NOT VALID +
  VALIDATE dance). On a table that already holds rows the few data-dependent ones are backfilled or will fail loudly
  (called out inline). Do not run this against live data without re-reading those comments.
- Payment enums lose values, so they are replaced by new types (rename, create, ALTER COLUMN TYPE USING, drop).
- app.kpi_daily_v reads payment / parking_request columns that change, so it is dropped first and rebuilt last.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The view differs between v5 and v7 only in the `fee` CTE (paid_at / paid_simulated -> created_at / recorded).
_KPI_VIEW = r"""
CREATE VIEW app.kpi_daily_v WITH (security_barrier = true) AS
WITH visible_zone AS (
  SELECT z.id AS zone_id, z.timezone
  FROM app.zone z
  WHERE app.ctx_role() = 'chain_operator'
     OR (app.ctx_role() IN ('zone_manager', 'system') AND z.id = ANY (app.ctx_zone_ids()))
), req AS (
  SELECT pr.zone_id,
         (pr.created_at AT TIME ZONE vz.timezone)::date                      AS day,
         count(*)                                                            AS requests_total,
         count(*) FILTER (WHERE pr.outcome = 'matched')                      AS matched,
         count(*) FILTER (WHERE pr.outcome = 'redirected_th3')               AS redirected_th3,
         count(*) FILTER (WHERE pr.outcome = 'redirected_public')            AS redirected_public,
         count(*) FILTER (WHERE pr.outcome = 'blocked')                      AS blocked,
         count(*) FILTER (WHERE pr.outcome = 'no_match')                     AS no_match
  FROM app.parking_request pr
  JOIN visible_zone vz ON vz.zone_id = pr.zone_id
  GROUP BY pr.zone_id, (pr.created_at AT TIME ZONE vz.timezone)::date
), fee AS (
@@FEE@@
), dsp AS (
  SELECT d.zone_id, (d.created_at AT TIME ZONE vz.timezone)::date AS day,
         count(*) AS disputes_opened,
         round((avg(extract(epoch FROM d.ready_at - d.created_at)) FILTER (WHERE d.ready_at IS NOT NULL) / 60)::numeric, 1)
                  AS dispute_prep_minutes_avg
  FROM app.dispute_case d
  JOIN visible_zone vz ON vz.zone_id = d.zone_id
  GROUP BY d.zone_id, (d.created_at AT TIME ZONE vz.timezone)::date
), days AS (
  SELECT zone_id, day FROM req UNION SELECT zone_id, day FROM fee UNION SELECT zone_id, day FROM dsp
)
SELECT d.zone_id,
       d.day,
       coalesce(req.requests_total, 0)        AS requests_total,
       coalesce(req.matched, 0)               AS matched,
       coalesce(req.redirected_th3, 0)        AS redirected_th3,
       coalesce(req.redirected_public, 0)     AS redirected_public,
       coalesce(req.blocked, 0)               AS blocked,
       coalesce(req.no_match, 0)              AS no_match,
       coalesce(fee.overstay_fees, 0)::bigint AS overstay_fees,
       coalesce(dsp.disputes_opened, 0)       AS disputes_opened,
       dsp.dispute_prep_minutes_avg           AS dispute_prep_minutes_avg
FROM days d
LEFT JOIN req ON req.zone_id = d.zone_id AND req.day = d.day
LEFT JOIN fee ON fee.zone_id = d.zone_id AND fee.day = d.day
LEFT JOIN dsp ON dsp.zone_id = d.zone_id AND dsp.day = d.day;
-- The view is read-only for everybody; the readonly role reads aggregates only.
REVOKE INSERT, UPDATE ON app.kpi_daily_v FROM parksmart_app;
GRANT SELECT ON app.kpi_daily_v TO parksmart_app, parksmart_readonly;
"""

_FEE_V7 = """  SELECT p.zone_id, (p.created_at AT TIME ZONE vz.timezone)::date AS day, sum(p.amount_vnd)::bigint AS overstay_fees
  FROM app.payment p
  JOIN visible_zone vz ON vz.zone_id = p.zone_id
  WHERE p.kind = 'overstay_fee' AND p.status = 'recorded'
  GROUP BY p.zone_id, (p.created_at AT TIME ZONE vz.timezone)::date"""

_FEE_V5 = """  SELECT p.zone_id, (p.paid_at AT TIME ZONE vz.timezone)::date AS day, sum(p.amount_vnd)::bigint AS overstay_fees
  FROM app.payment p
  JOIN visible_zone vz ON vz.zone_id = p.zone_id
  WHERE p.kind = 'overstay_fee' AND p.status = 'paid_simulated'
  GROUP BY p.zone_id, (p.paid_at AT TIME ZONE vz.timezone)::date"""


def upgrade() -> None:
    # 1. Enum values: own autocommit block (a new value is unusable inside the transaction that adds it).
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE app.request_outcome ADD VALUE IF NOT EXISTS 'queued'")
        op.execute("ALTER TYPE app.approval_kind ADD VALUE IF NOT EXISTS 'booking_review'")
        op.execute("ALTER TYPE app.approval_kind ADD VALUE IF NOT EXISTS 'registration_review'")
        op.execute("ALTER TYPE app.consent_action ADD VALUE IF NOT EXISTS 'location_share'")
        op.execute("ALTER TYPE app.consent_action ADD VALUE IF NOT EXISTS 'owner_listing_otp'")
        op.execute("ALTER TYPE app.consent_action ADD VALUE IF NOT EXISTS 'renter_assignment_otp'")

    # 2. The view depends on payment.paid_at / status; rebuilt at the end.
    op.execute("DROP VIEW app.kpi_daily_v")

    # 3. New enum types.
    op.execute("""
CREATE TYPE app.queue_status AS ENUM ('queued', 'eligible', 'assigned', 'otp_pending', 'holding', 'parked',
                                      'expired', 'rejected', 'escalated', 'left');
CREATE TYPE app.rule_result AS ENUM ('pass', 'reject', 'gray');
CREATE TYPE app.ai_risk_review AS ENUM ('normal', 'suspicious');
CREATE TYPE app.bql_decision AS ENUM ('approved', 'rejected', 'timed_out');
CREATE TYPE app.registry_match AS ENUM ('auto_matched', 'needs_bql');
CREATE TYPE app.eta_source AS ENUM ('gps', 'manual', 'none');
CREATE TYPE app.relocation_decision AS ENUM ('move', 'stay');
""")

    # 4. Payment becomes a fee ledger (D-37). Enum types lose values, so they are replaced.
    # Old rows are mapped (empty in the pilot): relocation_th3 -> th3_visit, early_return_refund -> cancel_refund,
    # pending / paid_simulated -> recorded, failed / cancelled -> cancelled.
    op.execute("""
DROP TRIGGER payment_overstay_guard ON app.payment;
DROP INDEX app.payment_paid_uq;
ALTER TABLE app.payment DROP COLUMN direction, DROP COLUMN provider, DROP COLUMN paid_at;
ALTER TABLE app.payment ALTER COLUMN status DROP DEFAULT;
ALTER TYPE app.payment_kind RENAME TO payment_kind_v5;
ALTER TYPE app.payment_status RENAME TO payment_status_v5;
CREATE TYPE app.payment_kind AS ENUM ('share_booking', 'th3_visit', 'cancel_refund', 'overstay_fee');
CREATE TYPE app.payment_status AS ENUM ('recorded', 'cancelled');
ALTER TABLE app.payment
  ALTER COLUMN kind TYPE app.payment_kind USING (CASE kind::text
      WHEN 'relocation_th3' THEN 'th3_visit' WHEN 'early_return_refund' THEN 'cancel_refund' ELSE kind::text END
    )::app.payment_kind,
  ALTER COLUMN status TYPE app.payment_status USING (CASE status::text
      WHEN 'pending' THEN 'recorded' WHEN 'paid_simulated' THEN 'recorded' ELSE 'cancelled' END
    )::app.payment_status,
  ALTER COLUMN status SET DEFAULT 'recorded';
DROP TYPE app.payment_kind_v5;
DROP TYPE app.payment_status_v5;
ALTER TABLE app.payment ADD COLUMN direction text
  GENERATED ALWAYS AS (CASE WHEN kind = 'cancel_refund' THEN 'refund' ELSE 'charge' END) STORED;
CREATE UNIQUE INDEX payment_recorded_uq ON app.payment (booking_id, kind) WHERE status = 'recorded';
CREATE TRIGGER payment_overstay_guard BEFORE INSERT OR UPDATE OF kind, booking_id ON app.payment
  FOR EACH ROW WHEN (NEW.kind = 'overstay_fee') EXECUTE FUNCTION app.payment_overstay_guard();
""")

    # 5. zone_policy: hold_ttl is replaced by the pilot parameters; early-return rule changes (D-36).
    op.execute("""
ALTER TABLE app.zone_policy
  ADD COLUMN hold_after_eta interval NOT NULL DEFAULT '10 minutes' CHECK (hold_after_eta > interval '0'),
  ADD COLUMN hold_max interval NOT NULL DEFAULT '40 minutes' CHECK (hold_max > interval '0'),
  ADD COLUMN th3_hold_max interval NOT NULL DEFAULT '60 minutes' CHECK (th3_hold_max > interval '0'),
  ADD COLUMN otp_confirm_ttl interval NOT NULL DEFAULT '3 minutes' CHECK (otp_confirm_ttl > interval '0'),
  ADD COLUMN listing_expiry interval NOT NULL DEFAULT '30 minutes' CHECK (listing_expiry > interval '0'),
  ADD COLUMN eta_assign_max interval NOT NULL DEFAULT '30 minutes' CHECK (eta_assign_max > interval '0'),
  ADD COLUMN gps_interval interval NOT NULL DEFAULT '15 minutes' CHECK (gps_interval > interval '0'),
  ADD COLUMN bql_review_ttl interval NOT NULL DEFAULT '10 minutes' CHECK (bql_review_ttl > interval '0'),
  ADD COLUMN no_show_fee_rate numeric(4,3) NOT NULL DEFAULT 0.300 CHECK (no_show_fee_rate BETWEEN 0 AND 1),
  ADD COLUMN no_show_min_hours smallint NOT NULL DEFAULT 1 CHECK (no_show_min_hours >= 0),
  ADD COLUMN th3_guest_alert_slots smallint NOT NULL DEFAULT 2 CHECK (th3_guest_alert_slots >= 0);
-- Keep a customised hold time: it becomes the "after ETA" part.
UPDATE app.zone_policy SET hold_after_eta = hold_ttl;
ALTER TABLE app.zone_policy DROP COLUMN hold_ttl;
ALTER TABLE app.zone_policy DROP CONSTRAINT zone_policy_early_return_cost_rule_check;
UPDATE app.zone_policy SET early_return_cost_rule = 'renter_priority_owner_buffer';
ALTER TABLE app.zone_policy ALTER COLUMN early_return_cost_rule SET DEFAULT 'renter_priority_owner_buffer';
ALTER TABLE app.zone_policy ADD CONSTRAINT zone_policy_early_return_cost_rule_check
  CHECK (early_return_cost_rule IN ('renter_priority_owner_buffer'));
""")

    # 6. building: intake pause (BR-24) + the policy that lets the system role set it.
    op.execute("""
ALTER TABLE app.building
  ADD COLUMN intake_paused_at timestamptz,
  ADD COLUMN intake_pause_reason text CHECK (intake_pause_reason IS NULL OR btrim(intake_pause_reason) <> ''),
  ADD CHECK ((intake_paused_at IS NULL) = (intake_pause_reason IS NULL));
CREATE POLICY system_intake_pause ON app.building FOR UPDATE
  USING (app.is_zone_staff(zone_id, '{system}')) WITH CHECK (app.is_zone_staff(zone_id, '{system}'));
""")

    # 7. bql_registry_import (new table) + RLS + grants in the same revision.
    op.execute(r"""
CREATE TABLE app.bql_registry_import (
  id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  zone_id          uuid NOT NULL REFERENCES app.zone (id) ON DELETE RESTRICT,
  batch_id         uuid NOT NULL,
  line_no          integer NOT NULL CHECK (line_no > 0),
  role             text NOT NULL CHECK (role IN ('resident', 'shophouse_owner')),
  full_name        text NOT NULL CHECK (btrim(full_name) <> '' AND length(full_name) <= 200),
  phone_e164       text CHECK (phone_e164 ~ '^\+[1-9][0-9]{7,14}$'),
  building_id      uuid,
  unit_code        text NOT NULL CHECK (btrim(unit_code) <> ''),
  slot_code        text CHECK (slot_code IS NULL OR btrim(slot_code) <> ''),
  size_class       app.size_class,
  plate_hash       bytea CHECK (plate_hash IS NULL OR length(plate_hash) = 32),
  plate_masked     text CHECK (plate_masked IS NULL OR btrim(plate_masked) <> ''),
  match_status     app.registry_match NOT NULL DEFAULT 'needs_bql',
  matched_user_id  uuid REFERENCES app.app_user (id) ON DELETE RESTRICT,
  matched_at       timestamptz,
  created_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (batch_id, line_no),
  FOREIGN KEY (building_id, zone_id) REFERENCES app.building (id, zone_id) ON DELETE RESTRICT,
  CONSTRAINT bql_registry_slot_size CHECK (slot_code IS NULL OR size_class IS NOT NULL),
  CONSTRAINT bql_registry_match_shape CHECK ((match_status = 'auto_matched') = (matched_user_id IS NOT NULL AND matched_at IS NOT NULL))
);
CREATE INDEX bql_registry_phone_idx ON app.bql_registry_import (zone_id, phone_e164) WHERE phone_e164 IS NOT NULL;
CREATE INDEX bql_registry_plate_idx ON app.bql_registry_import (zone_id, plate_hash) WHERE plate_hash IS NOT NULL;
CREATE INDEX bql_registry_review_idx ON app.bql_registry_import (zone_id, created_at) WHERE match_status = 'needs_bql';
ALTER TABLE app.bql_registry_import ENABLE ROW LEVEL SECURITY;
CREATE POLICY zone_staff ON app.bql_registry_import FOR ALL
  USING (app.is_zone_staff(zone_id, '{zone_manager,system}'))
  WITH CHECK (app.is_zone_staff(zone_id, '{zone_manager,system}'));
GRANT SELECT, INSERT, UPDATE ON app.bql_registry_import TO parksmart_app;
GRANT USAGE ON SEQUENCE app.bql_registry_import_id_seq TO parksmart_app;
""")

    # 8. approval_request: two-layer review (BR-26). due_at is renamed, not dropped (same meaning, escalation deadline).
    op.execute("""
ALTER TABLE app.approval_request RENAME COLUMN due_at TO bql_deadline_at;
ALTER TABLE app.approval_request
  ADD COLUMN rule_result app.rule_result,
  ADD COLUMN ai_risk app.ai_risk_review,
  ADD COLUMN reasons jsonb NOT NULL DEFAULT '[]' CHECK (jsonb_typeof(reasons) = 'array'),
  ADD COLUMN escalated_at timestamptz,
  ADD COLUMN bql_decision app.bql_decision,
  ADD CONSTRAINT approval_request_rule_not_reject CHECK (rule_result IS DISTINCT FROM 'reject'),
  ADD CONSTRAINT approval_request_escalation CHECK (
       (escalated_at IS NULL OR rule_result = 'gray' OR ai_risk = 'suspicious')
   AND (bql_deadline_at IS NULL OR escalated_at IS NOT NULL)
   AND (bql_decision IS NULL OR escalated_at IS NOT NULL));
""")

    # 9. share_window: owner OTP, exit tracking, listing expiry (BR-20, BR-25).
    # expires_at is NOT NULL: nullable add, backfill with created_at + the default 30' listing_expiry, then SET NOT NULL.
    # The two OTP CHECKs are NOT backfilled (a consent time must not be invented): they fail if open windows already
    # exist, which is intended - the pilot table is empty.
    op.execute("""
ALTER TABLE app.share_window
  ADD COLUMN owner_exited_at timestamptz,
  ADD COLUMN owner_otp_confirmed_at timestamptz,
  ADD COLUMN expires_at timestamptz;
UPDATE app.share_window SET expires_at = created_at + interval '30 minutes';
ALTER TABLE app.share_window ALTER COLUMN expires_at SET NOT NULL;
ALTER TABLE app.share_window
  ADD CHECK (status <> 'open' OR owner_otp_confirmed_at IS NOT NULL),
  ADD CHECK (owner_exited_at IS NULL OR owner_otp_confirmed_at IS NOT NULL);
CREATE INDEX share_window_available_idx ON app.share_window (zone_id, owner_exited_at)
  WHERE status = 'open' AND owner_exited_at IS NOT NULL;
CREATE INDEX share_window_listing_expiry_idx ON app.share_window (expires_at)
  WHERE status = 'open' AND owner_exited_at IS NULL;
""")

    # 10. parking_request: building queue, ETA (no coordinates), TH3 priority. Uses 'queued' (committed in step 1).
    op.execute("""
ALTER TABLE app.parking_request
  ADD COLUMN queue_status app.queue_status,
  ADD COLUMN queued_at timestamptz,
  ADD COLUMN last_eta_minutes smallint CHECK (last_eta_minutes IS NULL OR last_eta_minutes BETWEEN 0 AND 720),
  ADD COLUMN last_eta_at timestamptz,
  ADD COLUMN eta_source app.eta_source NOT NULL DEFAULT 'none',
  ADD COLUMN gps_consent_id bigint REFERENCES app.consent_record (id) ON DELETE RESTRICT,
  ADD COLUMN gps_missed_streak smallint NOT NULL DEFAULT 0 CHECK (gps_missed_streak >= 0),
  ADD COLUMN is_urban_related boolean NOT NULL DEFAULT false,
  ADD COLUMN updated_at timestamptz NOT NULL DEFAULT now(),
  ADD CONSTRAINT parking_request_queue_shape CHECK ((outcome = 'queued') = (queue_status IS NOT NULL)
                                                    AND (queue_status IS NULL) = (queued_at IS NULL)),
  ADD CONSTRAINT parking_request_eta_shape CHECK ((last_eta_minutes IS NULL) = (last_eta_at IS NULL)
                                                  AND (eta_source = 'none' OR last_eta_at IS NOT NULL)
                                                  AND (eta_source <> 'gps' OR gps_consent_id IS NOT NULL));
CREATE INDEX parking_request_queue_idx ON app.parking_request (building_id, queued_at)
  WHERE queue_status IN ('queued', 'eligible');
CREATE UNIQUE INDEX parking_request_one_live_uq ON app.parking_request (requester_user_id, building_id)
  WHERE queue_status IN ('queued', 'eligible', 'assigned', 'otp_pending', 'holding', 'parked');
CREATE TRIGGER parking_request_updated_at BEFORE UPDATE ON app.parking_request
  FOR EACH ROW EXECUTE FUNCTION app.set_updated_at();
""")

    # 11. booking: renter OTP, assignment time, no-show fee (BR-22, BR-25).
    op.execute("""
ALTER TABLE app.booking
  ADD COLUMN assigned_at timestamptz,
  ADD COLUMN renter_otp_confirmed_at timestamptz,
  ADD COLUMN no_show_fee_vnd bigint CHECK (no_show_fee_vnd >= 0),
  ADD CONSTRAINT booking_otp_shape CHECK (renter_otp_confirmed_at IS NULL
                                          OR (assigned_at IS NOT NULL AND renter_otp_confirmed_at >= assigned_at)),
  ADD CONSTRAINT booking_no_show_shape CHECK (no_show_fee_vnd IS NULL
                                              OR (status = 'expired' AND no_show_fee_vnd <= price_vnd));

CREATE FUNCTION app.th3_free_slots(p_zone uuid, p_at timestamptz DEFAULT now()) RETURNS integer
LANGUAGE sql STABLE AS $$
  SELECT count(*)::integer
  FROM app.slot s
  WHERE s.zone_id = p_zone AND s.slot_type = 'TH3' AND s.operational_status = 'active'
    AND NOT EXISTS (SELECT 1 FROM app.booking b
                    WHERE b.slot_id = s.id AND b.status IN ('held', 'pending_agreement', 'pending_approval', 'confirmed')
                      AND b.period @> p_at)
$$;
REVOKE ALL ON FUNCTION app.th3_free_slots(uuid, timestamptz) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.th3_free_slots(uuid, timestamptz) TO parksmart_app;
""")

    # 12. recovery_case: owner ETA, renter decision, owner buffer slot (D-36).
    # v5 resolved cases were always a move to a replacement booking, so they are backfilled as 'move'.
    op.execute("""
ALTER TABLE app.recovery_case
  ADD COLUMN eta_source app.eta_source NOT NULL DEFAULT 'manual',
  ADD COLUMN renter_decision app.relocation_decision,
  ADD COLUMN owner_buffer_slot_id uuid,
  ADD FOREIGN KEY (owner_buffer_slot_id, zone_id) REFERENCES app.slot (id, zone_id) ON DELETE RESTRICT;
UPDATE app.recovery_case SET renter_decision = 'move' WHERE status = 'resolved' AND relocated_booking_id IS NOT NULL;
ALTER TABLE app.recovery_case DROP CONSTRAINT recovery_case_resolved_has_booking;
ALTER TABLE app.recovery_case
  ADD CONSTRAINT recovery_case_resolved_has_booking CHECK (status <> 'resolved'
    OR (renter_decision = 'move' AND relocated_booking_id IS NOT NULL)
    OR (renter_decision = 'stay' AND owner_buffer_slot_id IS NOT NULL)),
  ADD CONSTRAINT recovery_case_move_has_no_buffer CHECK (renter_decision IS DISTINCT FROM 'move' OR owner_buffer_slot_id IS NULL);
CREATE INDEX recovery_case_buffer_idx ON app.recovery_case (owner_buffer_slot_id) WHERE owner_buffer_slot_id IS NOT NULL;
""")

    # 13. consent_record: wider subject_type. Append-only trigger fires on UPDATE / DELETE only, so DDL is fine.
    op.execute("""
ALTER TABLE app.consent_record DROP CONSTRAINT consent_record_subject_type_check;
ALTER TABLE app.consent_record ADD CONSTRAINT consent_record_subject_type_check
  CHECK (subject_type IN ('app_user', 'agreement', 'recovery_case', 'share_window', 'booking', 'parking_request'));
""")

    # 14. Rebuild the dashboard view on the v7 payment ledger.
    op.execute(_KPI_VIEW.replace("@@FEE@@", _FEE_V7))


def downgrade() -> None:
    # Back to schema v5. Fails (on purpose) if rows use v7-only values: queued requests, new approval kinds, new
    # consent actions or subject types, 'stay' recoveries without a replacement booking.
    op.execute("DROP VIEW app.kpi_daily_v")

    op.execute("""
ALTER TABLE app.consent_record DROP CONSTRAINT consent_record_subject_type_check;
ALTER TABLE app.consent_record ADD CONSTRAINT consent_record_subject_type_check
  CHECK (subject_type IN ('app_user', 'agreement', 'recovery_case'));

DROP INDEX app.recovery_case_buffer_idx;
ALTER TABLE app.recovery_case
  DROP CONSTRAINT recovery_case_move_has_no_buffer,
  DROP CONSTRAINT recovery_case_resolved_has_booking;
ALTER TABLE app.recovery_case
  DROP COLUMN owner_buffer_slot_id, DROP COLUMN renter_decision, DROP COLUMN eta_source;
ALTER TABLE app.recovery_case ADD CONSTRAINT recovery_case_resolved_has_booking
  CHECK (status <> 'resolved' OR relocated_booking_id IS NOT NULL);

DROP FUNCTION app.th3_free_slots(uuid, timestamptz);
ALTER TABLE app.booking
  DROP CONSTRAINT booking_no_show_shape, DROP CONSTRAINT booking_otp_shape,
  DROP COLUMN no_show_fee_vnd, DROP COLUMN renter_otp_confirmed_at, DROP COLUMN assigned_at;

DROP TRIGGER parking_request_updated_at ON app.parking_request;
DROP INDEX app.parking_request_one_live_uq;
DROP INDEX app.parking_request_queue_idx;
ALTER TABLE app.parking_request
  DROP CONSTRAINT parking_request_eta_shape, DROP CONSTRAINT parking_request_queue_shape,
  DROP COLUMN updated_at, DROP COLUMN is_urban_related, DROP COLUMN gps_missed_streak, DROP COLUMN gps_consent_id,
  DROP COLUMN eta_source, DROP COLUMN last_eta_at, DROP COLUMN last_eta_minutes,
  DROP COLUMN queued_at, DROP COLUMN queue_status;

DROP INDEX app.share_window_listing_expiry_idx;
DROP INDEX app.share_window_available_idx;
ALTER TABLE app.share_window
  DROP COLUMN expires_at, DROP COLUMN owner_otp_confirmed_at, DROP COLUMN owner_exited_at;

ALTER TABLE app.approval_request
  DROP CONSTRAINT approval_request_escalation, DROP CONSTRAINT approval_request_rule_not_reject,
  DROP COLUMN bql_decision, DROP COLUMN escalated_at, DROP COLUMN reasons, DROP COLUMN ai_risk,
  DROP COLUMN rule_result;
ALTER TABLE app.approval_request RENAME COLUMN bql_deadline_at TO due_at;

DROP TABLE app.bql_registry_import;

DROP POLICY system_intake_pause ON app.building;
ALTER TABLE app.building
  DROP COLUMN intake_pause_reason, DROP COLUMN intake_paused_at;

ALTER TABLE app.zone_policy ADD COLUMN hold_ttl interval NOT NULL DEFAULT '10 minutes' CHECK (hold_ttl > interval '0');
UPDATE app.zone_policy SET hold_ttl = hold_after_eta;
ALTER TABLE app.zone_policy
  DROP COLUMN th3_guest_alert_slots, DROP COLUMN no_show_min_hours, DROP COLUMN no_show_fee_rate,
  DROP COLUMN bql_review_ttl, DROP COLUMN gps_interval, DROP COLUMN eta_assign_max, DROP COLUMN listing_expiry,
  DROP COLUMN otp_confirm_ttl, DROP COLUMN th3_hold_max, DROP COLUMN hold_max, DROP COLUMN hold_after_eta;
ALTER TABLE app.zone_policy DROP CONSTRAINT zone_policy_early_return_cost_rule_check;
UPDATE app.zone_policy SET early_return_cost_rule = 'renter_pays_th3_relocated';
ALTER TABLE app.zone_policy ALTER COLUMN early_return_cost_rule SET DEFAULT 'renter_pays_th3_relocated';
ALTER TABLE app.zone_policy ADD CONSTRAINT zone_policy_early_return_cost_rule_check
  CHECK (early_return_cost_rule IN ('renter_pays_th3_relocated'));
""")

    # Payment back to the VietQR-mock shape. recorded -> pending (no paid_at to justify paid_simulated).
    op.execute("""
DROP TRIGGER payment_overstay_guard ON app.payment;
DROP INDEX app.payment_recorded_uq;
ALTER TABLE app.payment DROP COLUMN direction;
ALTER TABLE app.payment ALTER COLUMN status DROP DEFAULT;
ALTER TYPE app.payment_kind RENAME TO payment_kind_v7;
ALTER TYPE app.payment_status RENAME TO payment_status_v7;
CREATE TYPE app.payment_kind AS ENUM ('share_booking', 'th3_visit', 'relocation_th3', 'early_return_refund', 'overstay_fee');
CREATE TYPE app.payment_status AS ENUM ('pending', 'paid_simulated', 'failed', 'cancelled');
ALTER TABLE app.payment
  ALTER COLUMN kind TYPE app.payment_kind USING (CASE kind::text
      WHEN 'cancel_refund' THEN 'early_return_refund' ELSE kind::text END)::app.payment_kind,
  ALTER COLUMN status TYPE app.payment_status USING (CASE status::text
      WHEN 'recorded' THEN 'pending' ELSE status::text END)::app.payment_status,
  ALTER COLUMN status SET DEFAULT 'pending';
DROP TYPE app.payment_kind_v7;
DROP TYPE app.payment_status_v7;
ALTER TABLE app.payment
  ADD COLUMN direction text
    GENERATED ALWAYS AS (CASE WHEN kind = 'early_return_refund' THEN 'refund' ELSE 'charge' END) STORED,
  ADD COLUMN provider text NOT NULL DEFAULT 'vietqr_mock' CHECK (provider = 'vietqr_mock'),
  ADD COLUMN paid_at timestamptz,
  ADD CHECK ((status = 'paid_simulated') = (paid_at IS NOT NULL));
CREATE UNIQUE INDEX payment_paid_uq ON app.payment (booking_id, kind) WHERE status = 'paid_simulated';
CREATE TRIGGER payment_overstay_guard BEFORE INSERT OR UPDATE OF kind, booking_id ON app.payment
  FOR EACH ROW WHEN (NEW.kind = 'overstay_fee') EXECUTE FUNCTION app.payment_overstay_guard();
""")

    # Enum values cannot be removed with ALTER TYPE, so the three extended enums are recreated with the v5 labels.
    # The cast fails if a row still holds a v7-only label.
    op.execute("""
ALTER TYPE app.request_outcome RENAME TO request_outcome_v7;
CREATE TYPE app.request_outcome AS ENUM ('matched', 'redirected_th3', 'redirected_public', 'blocked', 'no_match');
-- The CHECK keeps a literal of the old type, which blocks the column type change: drop it and add it back.
ALTER TABLE app.parking_request DROP CONSTRAINT parking_request_check;
ALTER TABLE app.parking_request
  ALTER COLUMN outcome TYPE app.request_outcome USING outcome::text::app.request_outcome;
ALTER TABLE app.parking_request ADD CHECK ((outcome = 'blocked') = (block_reason IS NOT NULL));
DROP TYPE app.request_outcome_v7;

ALTER TYPE app.approval_kind RENAME TO approval_kind_v7;
CREATE TYPE app.approval_kind AS ENUM ('agreement_over_threshold', 'early_return_escalation', 'dispute_decision');
ALTER TABLE app.approval_request ALTER COLUMN kind TYPE app.approval_kind USING kind::text::app.approval_kind;
DROP TYPE app.approval_kind_v7;

ALTER TYPE app.consent_action RENAME TO consent_action_v7;
CREATE TYPE app.consent_action AS ENUM ('registration_terms', 'plate_processing', 'agreement_confirm', 'accept_relocation');
ALTER TABLE app.consent_record ALTER COLUMN action TYPE app.consent_action USING action::text::app.consent_action;
DROP TYPE app.consent_action_v7;

DROP TYPE app.relocation_decision;
DROP TYPE app.eta_source;
DROP TYPE app.registry_match;
DROP TYPE app.bql_decision;
DROP TYPE app.ai_risk_review;
DROP TYPE app.rule_result;
DROP TYPE app.queue_status;
""")

    op.execute(_KPI_VIEW.replace("@@FEE@@", _FEE_V5))
