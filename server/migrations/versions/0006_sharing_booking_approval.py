"""Sharing, booking and approval: agent_thread, approval_request, share_window, parking_request, booking

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-22
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# SQL copied from docs/03-design/sql/schema.sql (v5); RLS and grants live in the same revision as the table (ADR-0005).


def upgrade() -> None:
    op.execute("""
-- One row per LangGraph thread: who is talking to the agent, which workflow, where it waits. The graph state itself is in
-- the checkpointer (schema agent). No raw message text (BR-14 / D-12): pending_card is the pseudonymised confirmation card.
CREATE TABLE app.agent_thread (
  thread_id    text PRIMARY KEY CHECK (length(thread_id) BETWEEN 1 AND 200),   -- = LangGraph thread id
  user_id      uuid NOT NULL REFERENCES app.app_user (id) ON DELETE RESTRICT,
  zone_id      uuid REFERENCES app.zone (id) ON DELETE RESTRICT,                -- zone of the slot once routed
  workflow     app.workflow_code NOT NULL,
  status       app.thread_status NOT NULL DEFAULT 'active',
  pending_card jsonb CHECK (pending_card IS NULL OR jsonb_typeof(pending_card) = 'object'),
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX agent_thread_user_idx ON app.agent_thread (user_id, updated_at DESC);
CREATE INDEX agent_thread_zone_idx ON app.agent_thread (zone_id) WHERE status = 'awaiting_manager';

CREATE TABLE app.approval_request (
  id            uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  zone_id       uuid NOT NULL REFERENCES app.zone (id) ON DELETE RESTRICT,   -- zone of the slot (BR-18)
  kind          app.approval_kind NOT NULL,
  subject_id    uuid NOT NULL,                     -- agreement / booking id
  thread_id     text NOT NULL REFERENCES app.agent_thread (thread_id) ON DELETE RESTRICT,   -- LangGraph thread to resume
  status        app.approval_status NOT NULL DEFAULT 'pending',
  summary       text,                              -- pseudonymised, for the queue list
  requested_at  timestamptz NOT NULL DEFAULT now(),
  due_at        timestamptz,
  -- Users are never hard-deleted (soft delete), so decision makers are kept with RESTRICT.
  decided_by    uuid REFERENCES app.app_user (id) ON DELETE RESTRICT,
  decided_at    timestamptz,
  decision_note text,
  updated_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (id, zone_id),
  CHECK ((status IN ('approved', 'rejected')) = (decided_by IS NOT NULL AND decided_at IS NOT NULL))
);
-- One open request per subject; also the BQL queue index.
CREATE UNIQUE INDEX approval_request_pending_uq ON app.approval_request (kind, subject_id) WHERE status = 'pending';
CREATE INDEX approval_request_queue_idx ON app.approval_request (zone_id, requested_at) WHERE status = 'pending';
CREATE INDEX approval_request_thread_idx ON app.approval_request (thread_id);

CREATE TABLE app.share_window (
  id              uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  zone_id         uuid NOT NULL,
  slot_id         uuid NOT NULL,
  owner_user_id   uuid NOT NULL REFERENCES app.app_user (id) ON DELETE RESTRICT,
  period          tstzrange NOT NULL CHECK (app.is_finite_range(period)),   -- owner away
  -- period minus buffers; bookings must fit inside it. Stored (not generated) because
  -- timestamptz ± interval is not IMMUTABLE.
  bookable_period tstzrange NOT NULL CHECK (app.is_finite_range(bookable_period)),
  open_scope      app.open_scope NOT NULL,         -- owner-chosen, <= pool max (trigger)
  status          app.share_status NOT NULL DEFAULT 'open',
  returned_at     timestamptz,                     -- early return (W3)
  idempotency_key text NOT NULL UNIQUE,            -- thread_id:step or client request id (check d)
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (id, slot_id, owner_user_id),
  FOREIGN KEY (slot_id, zone_id) REFERENCES app.slot (id, zone_id) ON DELETE RESTRICT,
  CHECK (period @> bookable_period),
  CHECK (open_scope <> 'public'),
  CHECK ((status = 'closed_early') = (returned_at IS NOT NULL)),
  CONSTRAINT share_window_no_overlap EXCLUDE USING gist (slot_id WITH =, period WITH &&)
    WHERE (status = 'open')
);
CREATE INDEX share_window_owner_idx ON app.share_window (owner_user_id, lower(period) DESC);
-- Matching (W1/W2): open windows in a zone covering a requested range.
CREATE INDEX share_window_match_idx ON app.share_window USING gist (zone_id, bookable_period) WHERE status = 'open';

-- BR-03 (no TH3 sharing), holder check, AC-23 (owner may only narrow the scope).
CREATE FUNCTION app.share_window_validate() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  v_type  app.slot_type;
  v_max   app.open_scope;
BEGIN
  SELECT s.slot_type, p.max_open_scope INTO v_type, v_max
  FROM app.slot s JOIN app.slot_pool p ON p.id = s.pool_id
  WHERE s.id = NEW.slot_id;

  IF v_type = 'TH3' THEN
    RAISE EXCEPTION 'BR-03: TH3 slots cannot be shared by individuals' USING ERRCODE = 'check_violation';
  END IF;
  IF NEW.open_scope > v_max THEN
    RAISE EXCEPTION 'AC-23: open_scope % exceeds pool maximum %', NEW.open_scope, v_max
      USING ERRCODE = 'check_violation';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM app.slot_holding h
                 WHERE h.slot_id = NEW.slot_id AND h.user_id = NEW.owner_user_id
                   AND h.voided_at IS NULL AND h.held_during @> NEW.period) THEN
    RAISE EXCEPTION 'owner does not hold slot % for the whole window', NEW.slot_id
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER share_window_validate BEFORE INSERT OR UPDATE OF slot_id, owner_user_id, period, open_scope
  ON app.share_window FOR EACH ROW EXECUTE FUNCTION app.share_window_validate();

-- Every request is kept, including blocked ones: KPI "giao dịch sai tư cách/phạm vi bị chặn" (AC-03, AC-22).
CREATE TABLE app.parking_request (
  id                uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  zone_id           uuid NOT NULL,                 -- zone of the requested building
  building_id       uuid NOT NULL,
  requester_user_id uuid NOT NULL REFERENCES app.app_user (id) ON DELETE RESTRICT,
  vehicle_id        uuid NOT NULL,
  requested_period  tstzrange NOT NULL CHECK (app.is_finite_range(requested_period)
                                              AND upper(requested_period) - lower(requested_period) <= interval '31 days'),
  computed_level    app.eligibility_level NOT NULL,
  outcome           app.request_outcome NOT NULL,
  block_reason      text CHECK (block_reason ~ '^BR-[0-9]{2}$'),     -- rule id, e.g. BR-01, BR-16
  channel           text NOT NULL DEFAULT 'app' CHECK (channel IN ('app', 'chat')),
  idempotency_key   text NOT NULL UNIQUE,
  created_at        timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (building_id, zone_id) REFERENCES app.building (id, zone_id) ON DELETE RESTRICT,
  FOREIGN KEY (vehicle_id, requester_user_id) REFERENCES app.vehicle (id, user_id) ON DELETE RESTRICT,
  CHECK ((outcome = 'blocked') = (block_reason IS NOT NULL))
);
CREATE INDEX parking_request_user_idx ON app.parking_request (requester_user_id, created_at DESC);
CREATE INDEX parking_request_kpi_idx ON app.parking_request (zone_id, created_at, outcome);

CREATE TABLE app.booking (
  id                        uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  ref_no                    bigint GENERATED ALWAYS AS IDENTITY UNIQUE,  -- shown as GD-0013
  zone_id                   uuid NOT NULL,
  slot_id                   uuid NOT NULL,
  request_id                uuid REFERENCES app.parking_request (id) ON DELETE RESTRICT,
  share_window_id           uuid,                  -- NULL for TH3 (zone-operated)
  provider_user_id          uuid,                  -- = share_window.owner_user_id (composite FK)
  renter_user_id            uuid NOT NULL REFERENCES app.app_user (id) ON DELETE RESTRICT,
  vehicle_id                uuid NOT NULL,
  period                    tstzrange NOT NULL CHECK (app.is_finite_range(period)),
  eligibility_level         app.eligibility_level NOT NULL,   -- stamped and re-checked by trigger
  price_vnd                 bigint NOT NULL CHECK (price_vnd >= 0),
  status                    app.booking_status NOT NULL DEFAULT 'held',
  hold_expires_at           timestamptz,
  -- v4: physical occupancy without parking_session: set by N1 from a matched lpr_event; N2 / overstay (v5) reads it.
  checked_in_at             timestamptz,
  checked_out_at            timestamptz,
  relocated_from_booking_id uuid REFERENCES app.booking (id) ON DELETE RESTRICT,   -- W3 replacement
  idempotency_key           text NOT NULL UNIQUE,  -- thread_id:step (ADR-0010)
  version                   integer NOT NULL DEFAULT 1,   -- optimistic locking for user-driven edits
  created_at                timestamptz NOT NULL DEFAULT now(),
  updated_at                timestamptz NOT NULL DEFAULT now(),
  UNIQUE (id, zone_id),
  FOREIGN KEY (slot_id, zone_id) REFERENCES app.slot (id, zone_id) ON DELETE RESTRICT,
  FOREIGN KEY (share_window_id, slot_id, provider_user_id)
    REFERENCES app.share_window (id, slot_id, owner_user_id) ON DELETE RESTRICT,
  FOREIGN KEY (vehicle_id, renter_user_id) REFERENCES app.vehicle (id, user_id) ON DELETE RESTRICT,
  CHECK ((share_window_id IS NULL) = (provider_user_id IS NULL)),
  CHECK (provider_user_id IS NULL OR provider_user_id <> renter_user_id),
  CHECK (status <> 'held' OR hold_expires_at IS NOT NULL),
  CONSTRAINT booking_check_times CHECK (checked_out_at IS NULL OR (checked_in_at IS NOT NULL AND checked_out_at >= checked_in_at)),
  -- The core double-booking guard: one live booking per slot per instant.
  CONSTRAINT booking_no_overlap EXCLUDE USING gist (slot_id WITH =, period WITH &&)
    WHERE (status IN ('held', 'pending_agreement', 'pending_approval', 'confirmed'))
);
CREATE INDEX booking_renter_idx ON app.booking (renter_user_id, lower(period) DESC);
CREATE INDEX booking_provider_idx ON app.booking (provider_user_id, lower(period) DESC) WHERE provider_user_id IS NOT NULL;
CREATE INDEX booking_share_window_idx ON app.booking (share_window_id) WHERE share_window_id IS NOT NULL;
CREATE INDEX booking_request_idx ON app.booking (request_id) WHERE request_id IS NOT NULL;
CREATE INDEX booking_relocated_from_idx ON app.booking (relocated_from_booking_id) WHERE relocated_from_booking_id IS NOT NULL;
CREATE INDEX booking_vehicle_idx ON app.booking (vehicle_id);
-- Hold sweeper and active-booking scans.
CREATE INDEX booking_hold_expiry_idx ON app.booking (hold_expires_at) WHERE status = 'held';
CREATE INDEX booking_active_end_idx ON app.booking (zone_id, upper(period)) WHERE status = 'confirmed';

-- -----------------------------------------------------------------------------------------------------
-- Returns only (level, valid_until): the BR-17 attestation. Asset, unit number and documents never leave
-- the owning zone. SECURITY DEFINER because the caller's RLS cannot see other zones' eligibility rows.
-- Callers other than system/BQL may only ask about themselves (IDOR guard).
CREATE FUNCTION app.eligibility_level_at(p_user uuid, p_building uuid, p_at timestamptz DEFAULT now())
RETURNS TABLE (level app.eligibility_level, valid_until timestamptz)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, app AS $$
DECLARE
  v_zone uuid;
BEGIN
  IF app.ctx_role() NOT IN ('system', 'zone_manager') AND p_user IS DISTINCT FROM app.ctx_user_id() THEN
    RAISE EXCEPTION 'not allowed to query eligibility of another user' USING ERRCODE = 'insufficient_privilege';
  END IF;
  SELECT b.zone_id INTO v_zone FROM app.building b WHERE b.id = p_building;
  IF v_zone IS NULL THEN
    RAISE EXCEPTION 'unknown building %', p_building USING ERRCODE = 'foreign_key_violation';
  END IF;

  RETURN QUERY
  SELECT x.lvl, x.until FROM (
    SELECT CASE WHEN a.building_id = p_building THEN 'L1'
                WHEN a.zone_id = v_zone          THEN 'L2'
                ELSE 'L3' END::app.eligibility_level AS lvl,
           upper(e.valid_during) AS until
    FROM app.eligibility e
    JOIN app.asset a ON a.id = e.asset_id
    WHERE e.user_id = p_user
      AND e.status = 'verified'
      AND e.valid_during @> p_at                   -- expiry enforced here, independent of N6 (BR-16)
    UNION ALL
    SELECT 'L4'::app.eligibility_level, NULL::timestamptz
  ) x
  ORDER BY x.lvl, x.until DESC NULLS FIRST          -- strongest level, longest validity
  LIMIT 1;
END $$;

-- Defence in depth for the rule engine's decision. The rule engine (policy/domain) decides; this trigger
-- only refuses rows that would break a hard invariant if the application had a bug.
CREATE FUNCTION app.booking_validate() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
  v_slot        record;
  v_window      record;
  v_vehicle_sc  app.size_class;
  v_level       app.eligibility_level;
BEGIN
  SELECT s.slot_type, s.building_id, s.operational_status, s.size_class
    INTO v_slot
  FROM app.slot s
  WHERE s.id = NEW.slot_id;

  IF v_slot.operational_status <> 'active' THEN
    RAISE EXCEPTION 'slot % is not bookable (operational_status %)', NEW.slot_id, v_slot.operational_status
      USING ERRCODE = 'check_violation';
  END IF;

  -- BR-11: vehicle must fit (ordered enum: S < M < L < XL).
  SELECT v.size_class INTO v_vehicle_sc FROM app.vehicle v WHERE v.id = NEW.vehicle_id;
  IF v_vehicle_sc > v_slot.size_class THEN
    RAISE EXCEPTION 'BR-11: vehicle does not fit slot %', NEW.slot_id USING ERRCODE = 'check_violation';
  END IF;

  -- Level re-derived from data (BR-15/BR-16); a mismatch means the caller priced on stale facts.
  SELECT l.level INTO v_level FROM app.eligibility_level_at(NEW.renter_user_id, v_slot.building_id, lower(NEW.period)) l;
  IF v_level IS DISTINCT FROM NEW.eligibility_level THEN
    RAISE EXCEPTION 'eligibility level mismatch: stored %, derived %', NEW.eligibility_level, v_level
      USING ERRCODE = 'check_violation';
  END IF;

  IF v_slot.slot_type = 'TH3' THEN
    IF NEW.share_window_id IS NOT NULL THEN
      RAISE EXCEPTION 'BR-03: TH3 bookings are zone-operated and have no share window'
        USING ERRCODE = 'check_violation';
    END IF;
  ELSE
    IF NEW.share_window_id IS NULL THEN
      RAISE EXCEPTION 'TH1/TH2 bookings require a share window' USING ERRCODE = 'check_violation';
    END IF;
    -- FOR SHARE: a concurrent cancel/early-return (UPDATE of the window) waits for this booking's transaction,
    -- and this check re-reads the window if such an UPDATE committed first (docs/03-design/05-concurrency.md §2).
    SELECT w.bookable_period, w.open_scope, w.status INTO v_window
    FROM app.share_window w WHERE w.id = NEW.share_window_id
    FOR SHARE;
    IF v_window.status <> 'open' OR NOT v_window.bookable_period @> NEW.period THEN
      RAISE EXCEPTION 'booking period must lie inside an open window''s bookable period (buffers, FR-06)'
        USING ERRCODE = 'check_violation';
    END IF;
    -- BR-01 / BR-04: level must be inside the window's open scope.
    IF NEW.eligibility_level > app.scope_max_level(v_window.open_scope) THEN
      RAISE EXCEPTION 'BR-01/BR-04: level % outside open scope %', NEW.eligibility_level, v_window.open_scope
        USING ERRCODE = 'check_violation';
    END IF;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER booking_validate BEFORE INSERT OR UPDATE OF slot_id, share_window_id, vehicle_id, period, eligibility_level
  ON app.booking FOR EACH ROW EXECUTE FUNCTION app.booking_validate();

-- updated_at maintenance (v5 section 18)
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['approval_request', 'share_window', 'booking', 'agent_thread'] LOOP
    EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE ON app.%I
                    FOR EACH ROW EXECUTE FUNCTION app.set_updated_at()', t || '_updated_at', t);
  END LOOP;
END $$;

-- RLS (v5 section 20.4 / 20.5)
ALTER TABLE app.agent_thread ENABLE ROW LEVEL SECURITY;
CREATE POLICY owner ON app.agent_thread FOR ALL
  USING (user_id = (SELECT app.ctx_user_id())) WITH CHECK (user_id = (SELECT app.ctx_user_id()));
CREATE POLICY system_all ON app.agent_thread FOR ALL
  USING ((SELECT app.ctx_role()) = 'system') WITH CHECK ((SELECT app.ctx_role()) = 'system');
CREATE POLICY zone_manager_read ON app.agent_thread FOR SELECT
  USING (status = 'awaiting_manager' AND app.is_zone_staff(zone_id, '{zone_manager}'));

ALTER TABLE app.approval_request ENABLE ROW LEVEL SECURITY;
CREATE POLICY zone_staff ON app.approval_request FOR ALL
  USING (app.is_zone_staff(zone_id)) WITH CHECK (app.is_zone_staff(zone_id));

ALTER TABLE app.share_window ENABLE ROW LEVEL SECURITY;
-- Open supply is visible chain-wide so a seeker can be matched in any zone (FR-27).
CREATE POLICY open_read ON app.share_window FOR SELECT
  USING (status = 'open' AND (SELECT app.ctx_role()) <> 'anonymous');
CREATE POLICY owner ON app.share_window FOR ALL
  USING (owner_user_id = (SELECT app.ctx_user_id())) WITH CHECK (owner_user_id = (SELECT app.ctx_user_id()));
CREATE POLICY zone_staff ON app.share_window FOR ALL
  USING (app.is_zone_staff(zone_id)) WITH CHECK (app.is_zone_staff(zone_id));
-- W1 runs in the seeker's context but must place holds in another zone: system role, scoped by zone_ids.

ALTER TABLE app.parking_request ENABLE ROW LEVEL SECURITY;
CREATE POLICY requester ON app.parking_request FOR ALL
  USING (requester_user_id = (SELECT app.ctx_user_id())) WITH CHECK (requester_user_id = (SELECT app.ctx_user_id()));
CREATE POLICY zone_staff ON app.parking_request FOR ALL
  USING (app.is_zone_staff(zone_id)) WITH CHECK (app.is_zone_staff(zone_id));

ALTER TABLE app.booking ENABLE ROW LEVEL SECURITY;
CREATE POLICY parties_read ON app.booking FOR SELECT
  USING (renter_user_id = (SELECT app.ctx_user_id()) OR provider_user_id = (SELECT app.ctx_user_id()));
CREATE POLICY zone_staff ON app.booking FOR ALL
  USING (app.is_zone_staff(zone_id, '{zone_manager,system,guard}'))
  WITH CHECK (app.is_zone_staff(zone_id));

-- Policies of earlier tables that read booking (v5 sections 20.2 / 20.1): only creatable once booking exists.
-- A BQL sees people who hold an entitlement or a booking in their zone (names for approvals).
CREATE POLICY zone_manager_read ON app.app_user FOR SELECT
  USING ((SELECT app.ctx_role()) = 'zone_manager' AND (
           EXISTS (SELECT 1 FROM app.eligibility e WHERE e.user_id = app_user.id AND e.zone_id = ANY (app.ctx_zone_ids()))
        OR EXISTS (SELECT 1 FROM app.booking b WHERE (b.renter_user_id = app_user.id OR b.provider_user_id = app_user.id)
                                                AND b.zone_id = ANY (app.ctx_zone_ids()))));

CREATE POLICY zone_staff_read ON app.vehicle FOR SELECT
  USING ((SELECT app.ctx_role()) IN ('zone_manager', 'guard') AND EXISTS (
           SELECT 1 FROM app.booking b WHERE b.vehicle_id = vehicle.id AND b.zone_id = ANY (app.ctx_zone_ids())));

-- Grants (v5 section 21)
GRANT SELECT, INSERT, UPDATE ON app.agent_thread, app.approval_request, app.share_window, app.parking_request,
  app.booking TO parksmart_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA app TO parksmart_app;
REVOKE ALL ON FUNCTION app.share_window_validate(), app.booking_validate(),
  app.eligibility_level_at(uuid, uuid, timestamptz) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION app.share_window_validate(), app.booking_validate(),
  app.eligibility_level_at(uuid, uuid, timestamptz) TO parksmart_app;
""")


def downgrade() -> None:
    op.execute("""
DROP POLICY IF EXISTS zone_staff_read ON app.vehicle;
DROP POLICY IF EXISTS zone_manager_read ON app.app_user;
DROP TABLE app.booking;
DROP TABLE app.parking_request;
DROP TABLE app.share_window;
DROP TABLE app.approval_request;
DROP TABLE app.agent_thread;
DROP FUNCTION app.booking_validate();
DROP FUNCTION app.eligibility_level_at(uuid, uuid, timestamptz);
DROP FUNCTION app.share_window_validate();
""")
