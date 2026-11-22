-- =====================================================================================================
-- ParkSmart AI (P-142) — PostgreSQL schema
-- Target: PostgreSQL 16 (compose image pgvector/pgvector:pg16, RDS PostgreSQL 16).
-- v7 (2026-11-22): 26 tables — plan 024, pilot use case final (BR-20…BR-29, D-38…D-41): owner OTP + 30' listing expiry on
--   share_window; renter queue statuses, GPS/ETA fields (no coordinates), TH3 priority flag and renter OTP / hold deadline /
--   no-show fee on booking; two-layer approval review on approval_request; bql_registry_import (auto-match at onboarding);
--   pilot parameters on zone_policy (hold_ttl replaced by hold_after_eta / hold_max / th3_hold_max).
-- v6 (2026-11-22): still 25 tables — plan 022/023, one-building pilot (D-34…D-37): renter queue on parking_request,
--   share_window.owner_exited_at (slot free only after the owner's car left), early return with ETA and renter priority
--   (recovery_case ETA / decision / owner buffer slot, building.intake_paused_at), payment becomes a fee ledger (no QR).
-- v5 (2026-11-19): 25 tables — plan 003: overstay fee (W4, no table: 4 zone_policy columns + payment_kind 'overstay_fee')
--   and disputes (W5): dispute_case + dispute_evidence.
-- v4 (2026-11-18): lean MVP, 23 tables — plan 002 / ADR-0011 / D-32 (v3 had 27 tables: plan 001, D-31).
-- Full v2 design (57 tables): git show 333b85b:docs/database/02-schema.sql
-- The removed tables/functions and how to bring each back: docs/03-design/08-deferred-tables.md.
-- Executed on PG 17.10 up to v5 only; v6 and v7 are not executed yet (syntax checked with pglast) — see docs/03-design/01-data-model.md §6.
-- Uses only PG ≤16 features. Extensions: btree_gist (EXCLUDE on time ranges), pgcrypto (plate crypto
-- per ADR-0005; optional if plates are encrypted in the app), vector (RAG W7, section 19).
--
-- Run as the schema owner role (parksmart_owner) — never as the application role.
--   psql -v ON_ERROR_STOP=1 -f docs/03-design/sql/schema.sql
-- In the repo this file is split into Alembic revisions (op.execute("""SQL""")), see docs/06-operations/01-database-operations.md.
--
-- Conventions
--   * schema `app` for business tables; schema `agent` is reserved for langgraph-checkpoint-postgres.
--   * PK: uuid (UUIDv7, app.uuid_v7()) for entities; bigint identity for the append-heavy logs
--     (lpr_event, consent_record, ai_decision_log); text PK for agent_thread (= LangGraph thread id).
--     Rationale: docs/03-design/01-data-model.md §4.
--   * every zone-owned table carries zone_id NOT NULL and a composite FK (x_id, zone_id) to its parent, so
--     the denormalised zone_id used by RLS can never disagree with the hierarchy.
--   * money: bigint VND (đồng has no minor unit), CHECK >= 0.
--   * time: timestamptz everywhere; time windows are tstzrange '[)' (half-open).
--   * every write target keeps idempotency_key text NOT NULL UNIQUE (booking, payment, share_window, parking_request,
--     notification, recovery_case, ai_decision_log): there is no idempotency_keys table (docs/03-design/08-deferred-tables.md).
--   * section numbers are kept from v2 so references in the other docs stay valid; section 14 (disputes) is back in v5
--     (dispute_evidence sits in section 18 because it references consent_record); 15 (swaps) and 18b (privacy & retention)
--     no longer exist in the MVP.
-- =====================================================================================================

SET client_min_messages = warning;
SET lock_timeout = '5s';            -- migrations must not queue behind long locks (docs/06-operations/01-database-operations.md §1)
SET statement_timeout = '5min';

CREATE SCHEMA IF NOT EXISTS app;
CREATE SCHEMA IF NOT EXISTS agent;   -- filled by langgraph-checkpoint-postgres (ADR-0005)

CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- -----------------------------------------------------------------------------------------------------
-- 0. Roles (cluster-wide; passwords are set out of band from SSM, never in migrations)
-- -----------------------------------------------------------------------------------------------------
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'parksmart_owner') THEN
    CREATE ROLE parksmart_owner NOLOGIN;                        -- owns objects; migrations SET ROLE to it
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'parksmart_app') THEN
    CREATE ROLE parksmart_app NOLOGIN NOBYPASSRLS;              -- api / worker / agent-worker (DML only)
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'parksmart_checkpointer') THEN
    CREATE ROLE parksmart_checkpointer NOLOGIN NOBYPASSRLS;     -- LangGraph saver, schema agent only
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'parksmart_readonly') THEN
    CREATE ROLE parksmart_readonly NOLOGIN NOBYPASSRLS;         -- ad-hoc analysis / future replica
  END IF;
END $$;

-- Session guard rails for the application role (docs/03-design/05-concurrency.md §0). Jobs may raise statement_timeout
-- with SET LOCAL for a known long query.
ALTER ROLE parksmart_app SET statement_timeout = '5s';
ALTER ROLE parksmart_app SET lock_timeout = '2s';
ALTER ROLE parksmart_app SET idle_in_transaction_session_timeout = '30s';

REVOKE CREATE ON SCHEMA public FROM PUBLIC;

-- -----------------------------------------------------------------------------------------------------
-- 1. Enumerations (fixed sets the code switches on; open-ended catalogues are columns or tables instead)
-- -----------------------------------------------------------------------------------------------------
CREATE TYPE app.slot_type          AS ENUM ('TH1', 'TH2', 'TH3');
-- Order matters: building < zone < chain < public, compared with < / <= in triggers.
CREATE TYPE app.open_scope         AS ENUM ('building', 'zone', 'chain', 'public');
-- Order matters: L1 (strongest) < L2 < L3 < L4.
CREATE TYPE app.eligibility_level  AS ENUM ('L1', 'L2', 'L3', 'L4');
-- Order matters: S < M < L < XL. BR-11: a vehicle fits a slot when vehicle.size_class <= slot.size_class.
-- v3: replaces the size_class lookup table (docs/03-design/08-deferred-tables.md); a new size is an ALTER TYPE ... ADD VALUE.
CREATE TYPE app.size_class         AS ENUM ('S', 'M', 'L', 'XL');
-- v4: replaces slot.is_active; only 'active' slots can be booked (booking_validate).
CREATE TYPE app.slot_operational_status AS ENUM ('active', 'maintenance', 'blocked');
CREATE TYPE app.user_role          AS ENUM ('resident', 'renter', 'guard', 'zone_manager', 'chain_operator');
CREATE TYPE app.user_status        AS ENUM ('active', 'locked', 'deleted');
CREATE TYPE app.building_kind      AS ENUM ('residential_tower', 'lowrise_cluster', 'public_lot');
CREATE TYPE app.asset_kind         AS ENUM ('apartment', 'shophouse', 'office', 'clinic', 'kindergarten', 'other');
CREATE TYPE app.eligibility_role   AS ENUM ('owner', 'tenant', 'authorized', 'employee');
CREATE TYPE app.eligibility_status AS ENUM ('pending', 'verified', 'revoked', 'expired');
CREATE TYPE app.holding_kind       AS ENUM ('owner', 'lessee');   -- v3: 'swap_usage' returns with swaps (M11)
CREATE TYPE app.share_status       AS ENUM ('open', 'closed_early', 'cancelled', 'expired');
CREATE TYPE app.request_outcome    AS ENUM ('matched', 'redirected_th3', 'redirected_public', 'blocked', 'no_match', 'queued');
-- v7 (BR-21, BR-22, BR-28): only for outcome 'queued'. queued → eligible (ETA ≤ 30' or manual, D-39) → assigned (slot
-- chosen) → otp_pending (3' to enter the renter OTP) → holding (OTP ok, fee recorded) → parked (car in, gate 'in').
-- Off-path ends: expired (hold lapsed / N9), rejected (BQL or rule said no), escalated (waiting for the BQL, approval_request),
-- left (renter left the queue). 'left' is kept from v6 (not in the spec list, kept for the renter-cancel case).
CREATE TYPE app.queue_status       AS ENUM ('queued', 'eligible', 'assigned', 'otp_pending', 'holding', 'parked',
                                            'expired', 'rejected', 'escalated', 'left');
CREATE TYPE app.booking_status     AS ENUM ('held', 'pending_agreement', 'pending_approval', 'confirmed',
                                            'completed', 'relocated', 'cancelled', 'expired', 'rejected');
CREATE TYPE app.agreement_status   AS ENUM ('pending_confirmation', 'pending_approval', 'effective',
                                            'rejected', 'expired', 'cancelled');
-- v5: 'dispute_decision' (W5: the BQL decides a dispute, subject_id = dispute_case.id); 'swap' returns with M11.
-- v7: 'booking_review' (two-layer review of a renter's booking, BR-26) and 'registration_review' (BR-26 / FR-38: a
-- registration that does not match the BQL registry). subject_id = booking id / app_user id.
CREATE TYPE app.approval_kind      AS ENUM ('agreement_over_threshold', 'early_return_escalation', 'dispute_decision',
                                            'booking_review', 'registration_review');
-- v7 (BR-26): layer 1 rule engine → pass / reject (self-rejected, never queued) / gray (missing data, near a threshold);
-- layer 2 AI risk on passed cases → normal (auto-approved) / suspicious (to the BQL with reasons). BQL decision after escalation.
CREATE TYPE app.rule_result        AS ENUM ('pass', 'reject', 'gray');
CREATE TYPE app.ai_risk_review     AS ENUM ('normal', 'suspicious');
CREATE TYPE app.bql_decision       AS ENUM ('approved', 'rejected', 'timed_out');   -- timed_out = no answer in bql_review_ttl → rejected (BR-26)
-- v7 (FR-38): result of matching a registration against the BQL registry import.
CREATE TYPE app.registry_match     AS ENUM ('auto_matched', 'needs_bql');
CREATE TYPE app.approval_status    AS ENUM ('pending', 'approved', 'rejected', 'expired', 'cancelled');
-- v4: enum ledger_entry_type removed with the ledger (docs/03-design/08-deferred-tables.md).
-- payment.direction tells charges from refunds (v6: only 'cancel_refund' is a refund).
-- v5: overstay_fee (W4, FR-12) is a CHARGE to the renter, computed by the rule engine at exit (checked_out_at set; trigger
-- payment_overstay_guard). Payee rule, no payee column (fee ledger, A-05): the fee goes to the provider
-- (booking.provider_user_id), or to the zone for a TH3 booking (provider_user_id IS NULL).
-- v6 (D-37): payment is a fee ledger, no QR / VietQR. 'cancel_refund' (BR-23) replaces the old early-return kinds
-- 'relocation_th3' / 'early_return_refund' (renter priority: the renter is never moved to TH3 against their will, D-36).
CREATE TYPE app.payment_kind       AS ENUM ('share_booking', 'th3_visit', 'cancel_refund', 'overstay_fee');
CREATE TYPE app.payment_status     AS ENUM ('recorded', 'cancelled');
CREATE TYPE app.gate_direction     AS ENUM ('in', 'out');
CREATE TYPE app.lpr_status         AS ENUM ('accepted', 'pending_review', 'confirmed_manual', 'unreadable');
-- v4: agent_thread / recovery_case / consent_record / ai_decision_log (plan 002 section 3.2).
CREATE TYPE app.workflow_code      AS ENUM ('W0', 'W1', 'W2', 'W3', 'W4', 'W5', 'W6', 'W7');
CREATE TYPE app.thread_status      AS ENUM ('active', 'awaiting_user', 'awaiting_manager', 'completed', 'failed');
CREATE TYPE app.recovery_trigger   AS ENUM ('owner_early_return');
CREATE TYPE app.recovery_status    AS ENUM ('open', 'options_ready', 'awaiting_consent', 'resolved', 'escalated', 'cancelled');
-- v7 (BR-25): 'owner_listing_otp' (owner's OTP at posting, consent to rent the window), 'renter_assignment_otp' (renter's OTP
-- at assignment, consent to the slot and the charge). 'location_share' now covers each GPS sampling window of a request (BR-27).
CREATE TYPE app.consent_action     AS ENUM ('registration_terms', 'plate_processing', 'agreement_confirm', 'accept_relocation',
                                            'location_share', 'owner_listing_otp', 'renter_assignment_otp');
-- v7 (BR-27): gps = the app's location sample (only the ETA is kept), manual = 'Tôi đang đến' or 15 / 30 / 60 minutes picked,
-- none = no ETA yet (far away by default, BR-27). v6 'location' renamed to 'gps'.
CREATE TYPE app.eta_source         AS ENUM ('gps', 'manual', 'none');
CREATE TYPE app.relocation_decision AS ENUM ('move', 'stay');        -- v6 (D-36): the renter's choice on an early return
CREATE TYPE app.consent_decision   AS ENUM ('accepted', 'rejected', 'withdrawn');
CREATE TYPE app.ai_risk_level      AS ENUM ('low', 'medium', 'high');
CREATE TYPE app.ai_outcome         AS ENUM ('suggested', 'auto_applied', 'blocked_by_rule', 'sent_to_human', 'failed', 'degraded');
-- v5: disputes (W5, FR-13..16). Five categories are enough for the MVP (plan 003 section 3.3).
CREATE TYPE app.dispute_category   AS ENUM ('slot_occupied', 'overstay', 'wrong_vehicle', 'damage', 'other');
CREATE TYPE app.dispute_status     AS ENUM ('open', 'collecting_evidence', 'awaiting_decision', 'resolved', 'dismissed');
CREATE TYPE app.evidence_kind      AS ENUM ('photo', 'lpr_event', 'consent_record', 'agreement', 'ai_vision_extraction', 'note');

-- -----------------------------------------------------------------------------------------------------
-- 2. Helper functions
-- -----------------------------------------------------------------------------------------------------

-- UUIDv7 (time-ordered → B-tree inserts stay at the right edge). Native uuidv7() arrives in PG18;
-- the app may also generate v7 ids itself (needed when the id doubles as an idempotency handle).
CREATE FUNCTION app.uuid_v7() RETURNS uuid
LANGUAGE sql VOLATILE PARALLEL SAFE AS $$
  SELECT encode(
           set_bit(set_bit(
             overlay(uuid_send(gen_random_uuid())
                     PLACING substring(int8send((extract(epoch FROM clock_timestamp()) * 1000)::bigint) FROM 3)
                     FROM 1 FOR 6),
           52, 1), 53, 1),
         'hex')::uuid;
$$;

-- RLS context. platform.db.unit_of_work(ctx) runs SET LOCAL app.user_id / app.role / app.zone_ids
-- (ADR-0005). Missing settings resolve to "no access", never to "all access".
-- v4: the zone_ids claim of a BQL / guard is {app_user.staff_zone_id} (one zone per staff member; the staff_zone junction
-- table is deferred, docs/03-design/08-deferred-tables.md).
--   app.role ∈ resident | renter | guard | zone_manager | chain_operator | system | auth
--   app.zone_ids is an array literal: '{uuid,uuid}'
CREATE FUNCTION app.ctx_user_id() RETURNS uuid
LANGUAGE sql STABLE PARALLEL SAFE AS $$ SELECT NULLIF(current_setting('app.user_id', true), '')::uuid $$;

CREATE FUNCTION app.ctx_role() RETURNS text
LANGUAGE sql STABLE PARALLEL SAFE AS $$ SELECT coalesce(NULLIF(current_setting('app.role', true), ''), 'anonymous') $$;

CREATE FUNCTION app.ctx_zone_ids() RETURNS uuid[]
LANGUAGE sql STABLE PARALLEL SAFE AS $$
  SELECT coalesce(NULLIF(current_setting('app.zone_ids', true), '')::uuid[], '{}'::uuid[])
$$;

-- True when the session acts as staff (default: BQL or system job) of the given zone.
CREATE FUNCTION app.is_zone_staff(p_zone uuid, p_roles text[] DEFAULT '{zone_manager,system}')
RETURNS boolean LANGUAGE sql STABLE PARALLEL SAFE AS $$
  SELECT app.ctx_role() = ANY (p_roles) AND p_zone = ANY (app.ctx_zone_ids())
$$;

-- Maps an open scope to the weakest eligibility level it admits (PRD §4).
CREATE FUNCTION app.scope_max_level(p_scope app.open_scope) RETURNS app.eligibility_level
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
  SELECT CASE p_scope WHEN 'building' THEN 'L1' WHEN 'zone' THEN 'L2' WHEN 'chain' THEN 'L3' ELSE 'L4' END
         ::app.eligibility_level
$$;

-- A well-formed booking/sharing window: non-empty, both bounds finite.
CREATE FUNCTION app.is_finite_range(r tstzrange) RETURNS boolean
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
  SELECT NOT isempty(r) AND NOT lower_inf(r) AND NOT upper_inf(r)
$$;

CREATE FUNCTION app.set_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END $$;

-- -----------------------------------------------------------------------------------------------------
-- 3. Facility (M2) and pools (M3): Zone → Building → Slot (one operator, no chain table)
-- -----------------------------------------------------------------------------------------------------
-- v3: the chain table is removed (one operator, docs/03-design/08-deferred-tables.md); zone.code is globally unique instead of
-- unique per chain.
CREATE TABLE app.zone (
  id          uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  code        text NOT NULL UNIQUE CHECK (code ~ '^[A-Z0-9_-]{1,32}$'),
  name        text NOT NULL CHECK (btrim(name) <> ''),
  -- Business-day boundaries ("expires on day D", the KPI view's local day) use this zone.
  timezone    text NOT NULL DEFAULT 'Asia/Ho_Chi_Minh',
  is_active   boolean NOT NULL DEFAULT true,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE app.building (
  id          uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  zone_id     uuid NOT NULL REFERENCES app.zone (id) ON DELETE RESTRICT,
  -- v3: the subzone table is merged into this column (docs/03-design/08-deferred-tables.md); NULL = building belongs to no subzone.
  subzone_code text CHECK (subzone_code ~ '^[A-Z0-9_-]{1,32}$'),
  code        text NOT NULL,
  name        text NOT NULL CHECK (btrim(name) <> ''),
  kind        app.building_kind NOT NULL,
  is_active   boolean NOT NULL DEFAULT true,
  -- v6 BR-24 (D-36): set when an early-returning owner found no free buffer slot; the rule engine rejects new requests
  -- for this building until the BQL clears it. NULL = taking requests.
  intake_paused_at    timestamptz,
  intake_pause_reason text CHECK (intake_pause_reason IS NULL OR btrim(intake_pause_reason) <> ''),
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (zone_id, code),
  UNIQUE (id, zone_id),
  CHECK ((intake_paused_at IS NULL) = (intake_pause_reason IS NULL))
);

-- Pool = slots of one type in one building (TH1) or one zone (TH2/TH3). Holds the open scope (FR-26).
-- v7 TH3 guest lot: no counter table. Free TH3 slots = active TH3 slots minus live bookings now (see app.th3_free_slots).
CREATE TABLE app.slot_pool (
  id                  uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  zone_id             uuid NOT NULL REFERENCES app.zone (id) ON DELETE RESTRICT,
  building_id         uuid,
  slot_type           app.slot_type NOT NULL,
  -- Widest scope the rules allow; owners may only narrow it per share window (AC-23).
  max_open_scope      app.open_scope NOT NULL,
  -- BR-02: one-time developer consent for the whole TH2 pool.
  investor_consent_at timestamptz,
  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now(),
  UNIQUE NULLS NOT DISTINCT (zone_id, building_id, slot_type),
  UNIQUE (id, slot_type, zone_id),
  FOREIGN KEY (building_id, zone_id) REFERENCES app.building (id, zone_id) ON DELETE RESTRICT,
  -- PRD §4 table: default / maximum scope per slot type.
  CONSTRAINT slot_pool_scope_by_type CHECK (
       (slot_type = 'TH1' AND building_id IS NOT NULL AND max_open_scope IN ('building', 'zone'))
    OR (slot_type = 'TH2' AND max_open_scope IN ('zone', 'chain') AND investor_consent_at IS NOT NULL)
    OR (slot_type = 'TH3' AND max_open_scope = 'public'))
);

-- A public lot is a building of kind public_lot whose slots sit on level 'G'.
CREATE TABLE app.slot (
  id              uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  zone_id         uuid NOT NULL,
  building_id     uuid NOT NULL,
  pool_id         uuid NOT NULL,
  -- Denormalised from the pool for cheap filtering; the composite FK keeps it consistent.
  slot_type       app.slot_type NOT NULL,
  -- v3: the basement table is merged into this column (docs/03-design/08-deferred-tables.md): B1, B2, G.
  level_code      text NOT NULL CHECK (level_code ~ '^[A-Z0-9]{1,8}$'),
  code            text NOT NULL,                   -- B2-045
  size_class      app.size_class NOT NULL,
  -- v4: replaces is_active; slots are never deleted (history references them), only taken out of service.
  operational_status app.slot_operational_status NOT NULL DEFAULT 'active',
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (building_id, code),
  UNIQUE (id, zone_id),
  UNIQUE (id, zone_id, slot_type),
  FOREIGN KEY (building_id, zone_id) REFERENCES app.building (id, zone_id) ON DELETE RESTRICT,
  FOREIGN KEY (pool_id, slot_type, zone_id) REFERENCES app.slot_pool (id, slot_type, zone_id) ON DELETE RESTRICT
);
CREATE INDEX slot_pool_id_idx ON app.slot (pool_id);
CREATE INDEX slot_building_idx ON app.slot (building_id);
CREATE INDEX slot_zone_type_idx ON app.slot (zone_id, slot_type) WHERE operational_status = 'active';

-- -----------------------------------------------------------------------------------------------------
-- 4. Identity (M1 accounts): one account for the whole chain (FR-23)
-- -----------------------------------------------------------------------------------------------------
CREATE TABLE app.app_user (
  id             uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  full_name      text NOT NULL CHECK (btrim(full_name) <> '' AND length(full_name) <= 200),
  -- E.164, normalised by the app (+84…). Login identifier. NULL only on a deleted account
  -- (erasure itself is deferred, docs/03-design/08-deferred-tables.md); live accounts always have a phone.
  phone_e164     text CHECK (phone_e164 ~ '^\+[1-9][0-9]{7,14}$'),
  email          text CHECK (email IS NULL OR email ~ '^[^@\s]+@[^@\s]+$'),
  password_hash  text NOT NULL CHECK (password_hash LIKE '$argon2id$%'),   -- ADR-0006
  role           app.user_role NOT NULL DEFAULT 'resident',
  status         app.user_status NOT NULL DEFAULT 'active',
  failed_logins  smallint NOT NULL DEFAULT 0 CHECK (failed_logins >= 0),
  locked_until   timestamptz,
  deleted_at     timestamptz,                      -- soft delete
  -- v4: the one zone a BQL / guard works for (JWT claim zone_ids = {staff_zone_id}); replaces the staff_zone junction
  -- table (docs/03-design/08-deferred-tables.md). Consent (A-03 / BR-09) lives in consent_record, not here.
  staff_zone_id  uuid REFERENCES app.zone (id) ON DELETE RESTRICT,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT app_user_deleted_consistent CHECK ((status = 'deleted') = (deleted_at IS NOT NULL)),
  CONSTRAINT app_user_phone_required CHECK (status = 'deleted' OR phone_e164 IS NOT NULL),
  CONSTRAINT app_user_staff_zone_role CHECK (staff_zone_id IS NULL OR role IN ('guard', 'zone_manager'))
);
CREATE INDEX app_user_staff_zone_idx ON app.app_user (staff_zone_id) WHERE staff_zone_id IS NOT NULL;
-- Unique among live accounts only, so a deleted account does not block re-registration.
CREATE UNIQUE INDEX app_user_phone_uq ON app.app_user (phone_e164) WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX app_user_email_uq ON app.app_user (lower(email)) WHERE deleted_at IS NULL AND email IS NOT NULL;

-- v4: staff_zone (junction) and refresh_token are removed: one zone per staff member in app_user.staff_zone_id; access JWT
-- only (8 h for the demo, ADR-0011). See docs/03-design/08-deferred-tables.md.

-- Vehicles belong to a user, not a zone. Plate stored three ways (docs/03-design/01-data-model.md §4.6):
--   plate_ciphertext — AES-256-GCM envelope produced by the APP (data key wrapped by KMS, D-07 and
--                      docs/03-design/09-adr-0005-amendment-proposal.md); never selectable by the app role (column grant).
--                      v3: MVP shows masked plates only; the logged reveal functions are deferred
--                      (docs/03-design/08-deferred-tables.md), so AC-12 holds because no original plate is ever shown.
--   plate_hash       — HMAC-SHA256(normalised plate) with a separate KMS-held key ("blind index").
--   plate_masked     — display form "30A-•••.••".
CREATE TABLE app.vehicle (
  id                uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  user_id           uuid NOT NULL REFERENCES app.app_user (id) ON DELETE RESTRICT,
  plate_ciphertext  bytea,
  plate_key_version smallint NOT NULL DEFAULT 1 CHECK (plate_key_version > 0),
  plate_hash        bytea CHECK (length(plate_hash) = 32),
  plate_masked      text NOT NULL CHECK (btrim(plate_masked) <> ''),
  size_class        app.size_class NOT NULL,
  is_active         boolean NOT NULL DEFAULT true, -- soft delete: bookings and LPR history keep pointing here
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now(),
  UNIQUE (id, user_id),
  CONSTRAINT vehicle_plate_pair CHECK ((plate_ciphertext IS NULL) = (plate_hash IS NULL)),
  CONSTRAINT vehicle_active_has_plate CHECK (NOT is_active OR plate_ciphertext IS NOT NULL)
);
CREATE UNIQUE INDEX vehicle_user_plate_uq ON app.vehicle (user_id, plate_hash) WHERE is_active;
CREATE INDEX vehicle_plate_hash_idx ON app.vehicle (plate_hash) WHERE is_active;   -- LPR match (N1)

-- v7 (BR-26, FR-38): the BQL imports its registry ONCE at go-live (residents, shophouse owners, slots per household with
-- size, plates). One row per line of a batch. A registration (owner, renter) is matched against it automatically:
-- phone + unit (+ plate_hash) found → auto_matched (activated, no BQL); otherwise needs_bql. Zone-private (RLS zone staff).
-- Plates arrive in clear only in the import job: stored as plate_hash (same HMAC key as vehicle) and plate_masked.
CREATE TABLE app.bql_registry_import (
  id               bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  zone_id          uuid NOT NULL REFERENCES app.zone (id) ON DELETE RESTRICT,
  batch_id         uuid NOT NULL,                  -- one file import; re-running the same batch adds nothing (UNIQUE below)
  line_no          integer NOT NULL CHECK (line_no > 0),
  role             text NOT NULL CHECK (role IN ('resident', 'shophouse_owner')),
  full_name        text NOT NULL CHECK (btrim(full_name) <> '' AND length(full_name) <= 200),   -- PII: zone staff only
  phone_e164       text CHECK (phone_e164 ~ '^\+[1-9][0-9]{7,14}$'),
  building_id      uuid,                           -- NULL for a shophouse outside any tower (A-10)
  unit_code        text NOT NULL CHECK (btrim(unit_code) <> ''),   -- household / shophouse, same code as asset.code
  slot_code        text CHECK (slot_code IS NULL OR btrim(slot_code) <> ''),   -- one line per slot of the household
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
-- Matching lookups (registration time) and the BQL's list of lines that still need a decision.
CREATE INDEX bql_registry_phone_idx ON app.bql_registry_import (zone_id, phone_e164) WHERE phone_e164 IS NOT NULL;
CREATE INDEX bql_registry_plate_idx ON app.bql_registry_import (zone_id, plate_hash) WHERE plate_hash IS NOT NULL;
CREATE INDEX bql_registry_review_idx ON app.bql_registry_import (zone_id, created_at) WHERE match_status = 'needs_bql';

-- -----------------------------------------------------------------------------------------------------
-- 5. Eligibility (M1): (asset, role, validity) entitlements, verified by the BQL of the asset's zone
-- -----------------------------------------------------------------------------------------------------
-- Assets are what confer eligibility (apartment, shophouse, office…). Parking slots are NOT assets here:
-- slot usage rights live in slot_holding (see docs/03-design/01-data-model.md assumption AS-07).
CREATE TABLE app.asset (
  id          uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  zone_id     uuid NOT NULL REFERENCES app.zone (id) ON DELETE RESTRICT,
  -- NULL for low-rise shophouses that belong to no tower (A-10 → their holders are L2, not L1).
  building_id uuid,
  kind        app.asset_kind NOT NULL,
  code        text NOT NULL,                       -- unit number: PII-adjacent, never leaves the zone (BR-17)
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (zone_id, code),
  UNIQUE (id, zone_id),
  FOREIGN KEY (building_id, zone_id) REFERENCES app.building (id, zone_id) ON DELETE RESTRICT
);
CREATE INDEX asset_building_idx ON app.asset (building_id) WHERE building_id IS NOT NULL;

CREATE TABLE app.eligibility (
  id            uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  user_id       uuid NOT NULL REFERENCES app.app_user (id) ON DELETE RESTRICT,
  asset_id      uuid NOT NULL,
  zone_id       uuid NOT NULL,                     -- = asset.zone_id (composite FK)
  role          app.eligibility_role NOT NULL,
  -- '[from, until)'; upper unbounded = no expiry (owner). Tenants/employees carry an end (BR-16).
  valid_during  tstzrange NOT NULL CHECK (NOT isempty(valid_during) AND NOT lower_inf(valid_during)),
  status        app.eligibility_status NOT NULL DEFAULT 'pending',
  verified_by   uuid REFERENCES app.app_user (id) ON DELETE RESTRICT,
  verified_at   timestamptz,
  revoked_at    timestamptz,
  revoke_reason text,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (asset_id, zone_id) REFERENCES app.asset (id, zone_id) ON DELETE RESTRICT,
  CHECK (status <> 'verified' OR (verified_by IS NOT NULL AND verified_at IS NOT NULL)),
  CHECK (status <> 'revoked' OR revoked_at IS NOT NULL),
  -- No two live entitlements for the same person/asset/role over overlapping time.
  CONSTRAINT eligibility_no_overlap EXCLUDE USING gist (
    user_id WITH =, asset_id WITH =, role WITH =, valid_during WITH &&)
    WHERE (status IN ('pending', 'verified'))
);
CREATE INDEX eligibility_user_idx ON app.eligibility USING gist (user_id, valid_during) WHERE status = 'verified';
CREATE INDEX eligibility_zone_status_idx ON app.eligibility (zone_id, status);
CREATE INDEX eligibility_asset_idx ON app.eligibility (asset_id);
-- N6: verified rows whose validity ends soon / has ended.
CREATE INDEX eligibility_expiry_idx ON app.eligibility (upper(valid_during))
  WHERE status = 'verified' AND NOT upper_inf(valid_during);

-- Usage right on a TH1/TH2 slot over time (who may share it). TH3 has no individual holder (BR-03).
-- A change of holder closes one holding and opens another, so history is preserved.
CREATE TABLE app.slot_holding (
  id               uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  zone_id          uuid NOT NULL,
  slot_id          uuid NOT NULL,
  slot_type        app.slot_type NOT NULL,
  user_id          uuid NOT NULL REFERENCES app.app_user (id) ON DELETE RESTRICT,
  kind             app.holding_kind NOT NULL,
  held_during      tstzrange NOT NULL CHECK (NOT isempty(held_during) AND NOT lower_inf(held_during)),
  -- A holding entered by mistake is voided, not deleted; voided rows no longer block the slot.
  voided_at        timestamptz,
  void_reason      text CHECK (void_reason IS NULL OR btrim(void_reason) <> ''),
  created_at       timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (slot_id, zone_id, slot_type) REFERENCES app.slot (id, zone_id, slot_type) ON DELETE RESTRICT,
  CONSTRAINT slot_holding_type_kind CHECK (
       (slot_type = 'TH1' AND kind = 'owner')
    OR (slot_type = 'TH2' AND kind = 'lessee')),
  CHECK ((voided_at IS NULL) = (void_reason IS NULL)),
  CONSTRAINT slot_holding_no_overlap EXCLUDE USING gist (slot_id WITH =, held_during WITH &&)
    WHERE (voided_at IS NULL)
);
CREATE INDEX slot_holding_user_idx ON app.slot_holding (user_id);

-- -----------------------------------------------------------------------------------------------------
-- 6. Policy & configuration (M3). Versioned: a new row per change, agreements pin the version used.
-- -----------------------------------------------------------------------------------------------------
CREATE TABLE app.zone_policy (
  id                         uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  zone_id                    uuid NOT NULL REFERENCES app.zone (id) ON DELETE RESTRICT,
  version                    integer NOT NULL CHECK (version > 0),
  effective_from             timestamptz NOT NULL,
  -- The PRD leaves every value below TBD (A-07). DEFAULTS ARE RESEARCHED DEFAULTS, NOT RULES:
  -- "default, confirm with BQL". Rationale and sources per column: docs/03-design/07-db-decision-log.md (D-id in brackets).
  buffer_before              interval NOT NULL DEFAULT '15 minutes'        -- default, confirm with BQL [D-02]
                               CHECK (buffer_before >= interval '0'),
  buffer_after               interval NOT NULL DEFAULT '30 minutes'        -- default, confirm with BQL [D-02]
                               CHECK (buffer_after >= interval '0'),
  approval_threshold_vnd     bigint NOT NULL DEFAULT 1000000               -- default, confirm with BQL [D-08] BR-12
                               CHECK (approval_threshold_vnd >= 0),
  -- v7 pilot parameters (BR-20…BR-28, D-38…D-41): config, review after the 2-week pilot. Replaces v6 hold_ttl (fixed 10').
  hold_after_eta             interval NOT NULL DEFAULT '10 minutes'        -- v7: BR-22: hold = ETA + this
                               CHECK (hold_after_eta > interval '0'),
  hold_max                   interval NOT NULL DEFAULT '40 minutes'        -- v7: BR-22: cap for an ordinary slot
                               CHECK (hold_max > interval '0'),
  th3_hold_max               interval NOT NULL DEFAULT '60 minutes'        -- v7: BR-28: cap for a TH3 hold
                               CHECK (th3_hold_max > interval '0'),
  otp_confirm_ttl            interval NOT NULL DEFAULT '3 minutes'         -- v7: BR-22: renter OTP after assignment
                               CHECK (otp_confirm_ttl > interval '0'),
  listing_expiry             interval NOT NULL DEFAULT '30 minutes'        -- v7: BR-20: posted window not left by then → expired
                               CHECK (listing_expiry > interval '0'),
  eta_assign_max             interval NOT NULL DEFAULT '30 minutes'        -- v7: BR-21: eligible when last ETA ≤ this (traffic incl.)
                               CHECK (eta_assign_max > interval '0'),
  gps_interval               interval NOT NULL DEFAULT '15 minutes'        -- v7: BR-27: GPS sampling only while queued
                               CHECK (gps_interval > interval '0'),
  bql_review_ttl             interval NOT NULL DEFAULT '10 minutes'        -- v7: BR-26: BQL must answer or it is a rejection
                               CHECK (bql_review_ttl > interval '0'),
  no_show_fee_rate           numeric(4,3) NOT NULL DEFAULT 0.300           -- v7: BR-22: share of price kept when the renter does not come
                               CHECK (no_show_fee_rate BETWEEN 0 AND 1),
  no_show_min_hours          smallint NOT NULL DEFAULT 1                   -- v7: BR-22: fee is at least this many hours of price
                               CHECK (no_show_min_hours >= 0),
  th3_guest_alert_slots      smallint NOT NULL DEFAULT 2                   -- v7: BR-28: ≤ this many free TH3 slots → alert BQL + guard
                               CHECK (th3_guest_alert_slots >= 0),
  agreement_confirm_ttl      interval NOT NULL DEFAULT '30 minutes'        -- default, confirm with BQL [D-16]
                               CHECK (agreement_confirm_ttl > interval '0'),
  -- BR-16: a running booking survives the expiry of its entitlement for at most this long (NULL = to its end).
  eligibility_grace_max      interval DEFAULT '7 days'                     -- default, confirm with BQL [D-04]
                               CHECK (eligibility_grace_max IS NULL OR eligibility_grace_max >= interval '0'),
  -- Owner returns early (BR-07 v6, ADR-0014). Only rule implemented: the renter keeps the slot to the booked end unless
  -- they choose to move (same price, no extra charge); the owner parks on a free TH3 buffer slot of the building at no
  -- cost; no buffer → BQL + building intake pause (BR-24).  [D-09 revised by D-36]
  early_return_cost_rule     text NOT NULL DEFAULT 'renter_priority_owner_buffer'   -- default, confirm with BQL (A-12)
                               CHECK (early_return_cost_rule IN ('renter_priority_owner_buffer')),
  -- BR-13: below this OCR confidence an LPR event goes to manual review. v3: moved here from lpr_source
  -- (lpr_source table removed, docs/03-design/08-deferred-tables.md).  [D-21]
  ocr_review_threshold       numeric(4,3) NOT NULL DEFAULT 0.800           -- default, confirm with BQL [D-21]
                               CHECK (ocr_review_threshold BETWEEN 0 AND 1),
  -- BR-19 prices. v3: the price_rule table is merged into this column (docs/03-design/08-deferred-tables.md).
  -- Shape {"TH1":{"L1":{"hour":10000,"day":50000},…},…}, integer VND; the rule engine (Pydantic) validates it.
  prices                     jsonb NOT NULL CHECK (jsonb_typeof(prices) = 'object'),
  -- v5 overstay (FR-11, FR-12, BR-08): no overstay table. N2 reminds the renter overstay_pre_reminder before the booking end
  -- and at the end; at exit the rule engine charges nothing up to end + overstay_grace, otherwise
  -- ceil((checked_out_at - end) / overstay_billing_step) * overstay_fee_per_hour_vnd * step / 1 h (billed from the end).
  overstay_pre_reminder      interval NOT NULL DEFAULT '20 minutes'        -- default, confirm with BQL [D-03]
                               CHECK (overstay_pre_reminder >= interval '0'),
  overstay_grace             interval NOT NULL DEFAULT '10 minutes'        -- default, confirm with BQL [D-03]
                               CHECK (overstay_grace >= interval '0'),
  overstay_fee_per_hour_vnd  bigint NOT NULL DEFAULT 50000                 -- default, confirm with BQL [D-03]; 0 = no fee
                               CHECK (overstay_fee_per_hour_vnd >= 0),
  overstay_billing_step      interval NOT NULL DEFAULT '15 minutes'        -- default, confirm with BQL [D-03]
                               CHECK (overstay_billing_step > interval '0'),
  -- Agreement text of this policy version (Markdown with placeholders). v3: the agreement_template table is merged
  -- into this column (docs/03-design/08-deferred-tables.md); agreement.zone_policy_id pins the version used.
  agreement_template_md      text NOT NULL CHECK (btrim(agreement_template_md) <> ''),
  created_by                 uuid REFERENCES app.app_user (id) ON DELETE SET NULL,
  created_at                 timestamptz NOT NULL DEFAULT now(),
  UNIQUE (zone_id, version),
  UNIQUE (id, zone_id)
);
CREATE INDEX zone_policy_current_idx ON app.zone_policy (zone_id, effective_from DESC);

-- Policy in force for a zone at a time (latest version already effective).
CREATE FUNCTION app.current_zone_policy(p_zone uuid, p_at timestamptz DEFAULT now())
RETURNS app.zone_policy LANGUAGE sql STABLE AS $$
  SELECT * FROM app.zone_policy p WHERE p.zone_id = p_zone AND p.effective_from <= p_at
  ORDER BY p.effective_from DESC, p.version DESC LIMIT 1
$$;

-- v3: holiday table removed (it fed the N4 forecast, deferred); see docs/03-design/08-deferred-tables.md.

-- -----------------------------------------------------------------------------------------------------
-- 7. Agent threads (M14) and approvals (M12 HITL queue). Defined before the tables that reference them.
-- -----------------------------------------------------------------------------------------------------
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
  kind          app.approval_kind NOT NULL,   -- v7
  subject_id    uuid NOT NULL,                     -- agreement / booking id
  thread_id     text NOT NULL REFERENCES app.agent_thread (thread_id) ON DELETE RESTRICT,   -- LangGraph thread to resume
  status        app.approval_status NOT NULL DEFAULT 'pending',
  summary       text,                              -- pseudonymised, for the queue list
  requested_at  timestamptz NOT NULL DEFAULT now(),
  -- v7 BR-26 two-layer review (NULL for kinds that do not pass it). Layer 1 = rule_result, layer 2 = ai_risk.
  -- AI only tightens: a rule 'reject' is never queued, and only gray or suspicious cases reach the BQL.
  rule_result   app.rule_result,   -- v7
  ai_risk       app.ai_risk_review,   -- v7
  reasons       jsonb NOT NULL DEFAULT '[]' CHECK (jsonb_typeof(reasons) = 'array'),   -- v7: [{"code","text","source"}], pseudonymised
  escalated_at  timestamptz,                       -- v7: NULL = decided without the BQL (auto approve / auto reject)
  bql_deadline_at timestamptz,                     -- v7 (was due_at): escalated_at + bql_review_ttl; late = rejected (BR-26)
  bql_decision  app.bql_decision,   -- v7
  -- Users are never hard-deleted (soft delete), so decision makers are kept with RESTRICT.
  decided_by    uuid REFERENCES app.app_user (id) ON DELETE RESTRICT,
  decided_at    timestamptz,
  decision_note text,
  updated_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (id, zone_id),
  CHECK ((status IN ('approved', 'rejected')) = (decided_by IS NOT NULL AND decided_at IS NOT NULL)),
  CONSTRAINT approval_request_rule_not_reject CHECK (rule_result IS DISTINCT FROM 'reject'),
  CONSTRAINT approval_request_escalation CHECK (
       (escalated_at IS NULL OR rule_result = 'gray' OR ai_risk = 'suspicious')
   AND (bql_deadline_at IS NULL OR escalated_at IS NOT NULL)
   AND (bql_decision IS NULL OR escalated_at IS NOT NULL))
);
-- One open request per subject; also the BQL queue index.
CREATE UNIQUE INDEX approval_request_pending_uq ON app.approval_request (kind, subject_id) WHERE status = 'pending';
CREATE INDEX approval_request_queue_idx ON app.approval_request (zone_id, requested_at) WHERE status = 'pending';
CREATE INDEX approval_request_thread_idx ON app.approval_request (thread_id);

-- -----------------------------------------------------------------------------------------------------
-- 8. Sharing (M4): owner publishes a window with buffers (FR-06); free only once the owner's car left (BR-20 v6)
-- -----------------------------------------------------------------------------------------------------
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
  -- v6 BR-20 (D-35): N1 sets this from the gate 'out' event of a vehicle of owner_user_id after the window was posted.
  -- Matching only offers open windows with owner_exited_at set; posted but car still inside = not free.
  owner_exited_at timestamptz,
  -- v7 BR-25: the owner's OTP "đồng ý cho thuê khung giờ" with the system. The OTP itself is not stored (SMS/OTP service);
  -- only the confirmation time. A window is open only after it (CHECK below).
  owner_otp_confirmed_at timestamptz,   -- v7
  -- v7 BR-20: posting time + listing_expiry (zone_policy). Posted, car not out by then → status 'expired', owner posts again.
  expires_at      timestamptz NOT NULL,   -- v7
  idempotency_key text NOT NULL UNIQUE,            -- thread_id:step or client request id (check d)
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (id, slot_id, owner_user_id),
  FOREIGN KEY (slot_id, zone_id) REFERENCES app.slot (id, zone_id) ON DELETE RESTRICT,
  CHECK (period @> bookable_period),
  CHECK (open_scope <> 'public'),
  CHECK ((status = 'closed_early') = (returned_at IS NOT NULL)),
  CHECK (status <> 'open' OR owner_otp_confirmed_at IS NOT NULL),
  CHECK (owner_exited_at IS NULL OR owner_otp_confirmed_at IS NOT NULL),
  CONSTRAINT share_window_no_overlap EXCLUDE USING gist (slot_id WITH =, period WITH &&)
    WHERE (status = 'open')
);
CREATE INDEX share_window_owner_idx ON app.share_window (owner_user_id, lower(period) DESC);
-- Matching (W1/W2): open windows in a zone covering a requested range.
CREATE INDEX share_window_match_idx ON app.share_window USING gist (zone_id, bookable_period) WHERE status = 'open';
-- v6 queue matching (W2): windows that are really free (owner's car left), oldest exit first (BR-21).
CREATE INDEX share_window_available_idx ON app.share_window (zone_id, owner_exited_at)
  WHERE status = 'open' AND owner_exited_at IS NOT NULL;
-- v7 BR-20 sweeper: posted windows whose car has not left yet, oldest deadline first.
CREATE INDEX share_window_listing_expiry_idx ON app.share_window (expires_at)
  WHERE status = 'open' AND owner_exited_at IS NULL;

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

-- -----------------------------------------------------------------------------------------------------
-- 9. Booking (M5): requests (KPI source) and bookings (the reservation)
-- -----------------------------------------------------------------------------------------------------
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
  -- v6 queue (BR-21, D-34): a request with no free fitting slot waits in the building queue. Order = queued_at
  -- (not the renter's ETA). The planned exit time is upper(requested_period).
  queue_status      app.queue_status,   -- v7
  queued_at         timestamptz,
  -- v7 (BR-21, BR-27): ETA of the renter. Only the minutes and the time are kept; NO coordinates, anywhere (BR-27).
  -- The ETA comes from the TravelTimeProvider port (mock in dev/CI/demo). The LLM receives the minutes only.
  last_eta_minutes  smallint CHECK (last_eta_minutes IS NULL OR last_eta_minutes BETWEEN 0 AND 720),   -- v7
  last_eta_at       timestamptz,   -- v7
  eta_source        app.eta_source NOT NULL DEFAULT 'none',   -- v7
  gps_consent_id    bigint REFERENCES app.consent_record (id) ON DELETE RESTRICT,   -- v7: 'location_share' consent (NĐ 13/2023)
  gps_missed_streak smallint NOT NULL DEFAULT 0 CHECK (gps_missed_streak >= 0),   -- v7: 2 in a row → remind, never drop (BR-27)
  -- v7 (BR-28): renter linked to the urban area (other tower in the zone, shophouse owner…): priority at the TH3 guest lot.
  is_urban_related  boolean NOT NULL DEFAULT false,   -- v7
  idempotency_key   text NOT NULL UNIQUE,
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (building_id, zone_id) REFERENCES app.building (id, zone_id) ON DELETE RESTRICT,
  FOREIGN KEY (vehicle_id, requester_user_id) REFERENCES app.vehicle (id, user_id) ON DELETE RESTRICT,
  CHECK ((outcome = 'blocked') = (block_reason IS NOT NULL)),
  CONSTRAINT parking_request_queue_shape CHECK ((outcome = 'queued') = (queue_status IS NOT NULL)
                                                AND (queue_status IS NULL) = (queued_at IS NULL)),
  CONSTRAINT parking_request_eta_shape CHECK ((last_eta_minutes IS NULL) = (last_eta_at IS NULL)
                                              AND (eta_source = 'none' OR last_eta_at IS NOT NULL)
                                              AND (eta_source <> 'gps' OR gps_consent_id IS NOT NULL))
);
CREATE INDEX parking_request_user_idx ON app.parking_request (requester_user_id, created_at DESC);
CREATE INDEX parking_request_kpi_idx ON app.parking_request (zone_id, created_at, outcome);
-- v7: the live building queue (queued / eligible), first in first served by queued_at.
CREATE INDEX parking_request_queue_idx ON app.parking_request (building_id, queued_at)
  WHERE queue_status IN ('queued', 'eligible');
-- v7: one live request per renter and building (queued … parked). Replaces the v6 'waiting' index.
CREATE UNIQUE INDEX parking_request_one_live_uq ON app.parking_request (requester_user_id, building_id)
  WHERE queue_status IN ('queued', 'eligible', 'assigned', 'otp_pending', 'holding', 'parked');

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
  -- v7 BR-22: assigned_at starts the renter's OTP window (otp_confirm_ttl). While renter_otp_confirmed_at is NULL,
  -- hold_expires_at = assigned_at + otp_confirm_ttl; after the OTP it is ETA + hold_after_eta (cap hold_max, TH3 th3_hold_max).
  assigned_at               timestamptz,   -- v7
  renter_otp_confirmed_at   timestamptz,   -- v7: the renter's OTP "nhận chỗ, đồng ý bị trừ tiền" (BR-25); the charge is recorded here
  hold_expires_at           timestamptz,
  -- v7 BR-22: kept when the renter does not come (30% of price, at least no_show_min_hours of price); the rest is refunded.
  -- Filled by the job that expires the hold; the fee belongs to the provider (TH3: the zone).
  no_show_fee_vnd           bigint CHECK (no_show_fee_vnd >= 0),   -- v7
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
  CONSTRAINT booking_otp_shape CHECK (renter_otp_confirmed_at IS NULL
                                      OR (assigned_at IS NOT NULL AND renter_otp_confirmed_at >= assigned_at)),
  CONSTRAINT booking_no_show_shape CHECK (no_show_fee_vnd IS NULL
                                          OR (status = 'expired' AND no_show_fee_vnd <= price_vnd)),
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

-- v7 BR-28: free guest-lot (TH3) slots of a zone at a time = active TH3 slots without a live booking covering that time.
-- No counter table: the number is derived, so it cannot drift from the bookings. Alert when ≤ zone_policy.th3_guest_alert_slots.
CREATE FUNCTION app.th3_free_slots(p_zone uuid, p_at timestamptz DEFAULT now()) RETURNS integer
LANGUAGE sql STABLE AS $$
  SELECT count(*)::integer
  FROM app.slot s
  WHERE s.zone_id = p_zone AND s.slot_type = 'TH3' AND s.operational_status = 'active'
    AND NOT EXISTS (SELECT 1 FROM app.booking b
                    WHERE b.slot_id = s.id AND b.status IN ('held', 'pending_agreement', 'pending_approval', 'confirmed')
                      AND b.period @> p_at)
$$;

-- -----------------------------------------------------------------------------------------------------
-- 10. Eligibility level at a location (FR-24, BR-15) and booking guard (BR-01/04/11/16)
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

-- -----------------------------------------------------------------------------------------------------
-- 11. Agreements (M6), recovery cases (W3) and the append-only guard
-- -----------------------------------------------------------------------------------------------------
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

-- v4: otp_challenge, ledger_entry, ledger_head and the functions ledger_hash / ledger_append / ledger_verify (with enum
-- ledger_entry_type) are removed (docs/03-design/08-deferred-tables.md). The agreement OTP (hash, TTL, attempt counter) lives in Redis
-- (ADR-0006, ADR-0011); the evidence of both confirmations is a consent_record row (section 18).

-- Append-only guard, even for the table owner (grants alone do not stop the owner). Statement-level, so even an
-- UPDATE/DELETE that matches no row is refused. No purge path exists in the MVP (retention enforcement is deferred,
-- docs/03-design/08-deferred-tables.md). Used by consent_record and ai_decision_log.
CREATE FUNCTION app.reject_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION '% is append-only (% rejected)', TG_TABLE_NAME, TG_OP USING ERRCODE = 'insufficient_privilege';
END $$;

-- W3 (owner returns early, Ưu tiên 2): one open case per booking. v6 (D-36, ADR-0014): new_return_at is the owner's ETA
-- (one-time location or minutes picked; no coordinates stored). The rule engine fills `options` (other free slots for
-- the renter); the LLM only words the message (BR-14). Renter priority: 'move' → replacement booking, 'stay' (or no
-- answer by deadline_at) → the owner gets a TH3 buffer slot of the building; no buffer → escalated + intake pause.
CREATE TABLE app.recovery_case (
  id                   uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  zone_id              uuid NOT NULL,
  booking_id           uuid NOT NULL,                -- the booking hit by the early return
  trigger              app.recovery_trigger NOT NULL DEFAULT 'owner_early_return',
  new_return_at        timestamptz NOT NULL,         -- v6: owner ETA
  eta_source           app.eta_source NOT NULL DEFAULT 'manual',   -- v7
  renter_decision      app.relocation_decision,      -- NULL until the renter answers (or N9 sets 'stay' at deadline_at)
  owner_buffer_slot_id uuid,                         -- 'stay': TH3 buffer slot given to the owner, free of charge
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
  FOREIGN KEY (owner_buffer_slot_id, zone_id) REFERENCES app.slot (id, zone_id) ON DELETE RESTRICT,
  -- v6: a resolved case is either a move (replacement booking) or a stay (owner buffer slot).
  CONSTRAINT recovery_case_resolved_has_booking CHECK (status <> 'resolved'
    OR (renter_decision = 'move' AND relocated_booking_id IS NOT NULL)
    OR (renter_decision = 'stay' AND owner_buffer_slot_id IS NOT NULL)),
  CONSTRAINT recovery_case_move_has_no_buffer CHECK (renter_decision IS DISTINCT FROM 'move' OR owner_buffer_slot_id IS NULL),
  CONSTRAINT recovery_case_escalated_has_approval CHECK (status <> 'escalated' OR approval_request_id IS NOT NULL)
);
CREATE UNIQUE INDEX recovery_case_open_uq ON app.recovery_case (booking_id) WHERE status NOT IN ('resolved', 'cancelled');
CREATE INDEX recovery_case_zone_idx ON app.recovery_case (zone_id, deadline_at) WHERE status NOT IN ('resolved', 'cancelled');
CREATE INDEX recovery_case_relocated_idx ON app.recovery_case (relocated_booking_id) WHERE relocated_booking_id IS NOT NULL;
CREATE INDEX recovery_case_approval_idx ON app.recovery_case (approval_request_id) WHERE approval_request_id IS NOT NULL;
CREATE INDEX recovery_case_slot_idx ON app.recovery_case (chosen_slot_id) WHERE chosen_slot_id IS NOT NULL;
CREATE INDEX recovery_case_buffer_idx ON app.recovery_case (owner_buffer_slot_id) WHERE owner_buffer_slot_id IS NOT NULL;

-- -----------------------------------------------------------------------------------------------------
-- 12. Payment (M7): fee ledger, no QR / VietQR, no money moves in the app (v6, D-37, A-05)
-- -----------------------------------------------------------------------------------------------------
-- v3: the voucher table (shophouse vouchers, FR-22) is removed (docs/03-design/08-deferred-tables.md); with it go
-- payment.voucher_id, payment.discount_vnd and the payment_validate_voucher trigger, and the gross/discount
-- pair collapses into a plain amount_vnd.
CREATE TABLE app.payment (
  id              uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  zone_id         uuid NOT NULL,
  booking_id      uuid NOT NULL,
  payer_user_id   uuid NOT NULL REFERENCES app.app_user (id) ON DELETE RESTRICT,
  kind            app.payment_kind NOT NULL,
  amount_vnd      bigint NOT NULL CHECK (amount_vnd >= 0),
  -- charge: payer_user_id owes it; refund: payer_user_id is the person refunded (BR-23).
  direction       text GENERATED ALWAYS AS (CASE WHEN kind = 'cancel_refund' THEN 'refund' ELSE 'charge' END) STORED,
  -- v6: 'recorded' when the rule engine writes it; 'cancelled' when voided (e.g. overstay fee waived by the BQL).
  -- The two parties settle outside the app (A-05); there is no provider, QR or paid timestamp.
  status          app.payment_status NOT NULL DEFAULT 'recorded',
  idempotency_key text NOT NULL UNIQUE,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (booking_id, zone_id) REFERENCES app.booking (id, zone_id) ON DELETE RESTRICT
);
CREATE INDEX payment_booking_idx ON app.payment (booking_id);
CREATE INDEX payment_payer_idx ON app.payment (payer_user_id, created_at DESC);
-- At most one live (recorded) entry per booking and kind (so also one overstay_fee per booking).
CREATE UNIQUE INDEX payment_recorded_uq ON app.payment (booking_id, kind) WHERE status = 'recorded';

-- v5: an overstay fee exists only once the car has left (N1 set checked_out_at). Defence in depth for the rule engine.
-- SECURITY DEFINER: the payer's RLS context may not see the booking row.
CREATE FUNCTION app.payment_overstay_guard() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, app AS $$
DECLARE
  v_out timestamptz;
  v_found boolean;
BEGIN
  SELECT b.checked_out_at, true INTO v_out, v_found FROM app.booking b WHERE b.id = NEW.booking_id;
  IF v_found IS TRUE AND v_out IS NULL THEN       -- unknown booking: let the foreign key report it
    RAISE EXCEPTION 'overstay_fee needs a checked-out booking (checked_out_at is NULL for %)', NEW.booking_id
      USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER payment_overstay_guard BEFORE INSERT OR UPDATE OF kind, booking_id ON app.payment
  FOR EACH ROW WHEN (NEW.kind = 'overstay_fee') EXECUTE FUNCTION app.payment_overstay_guard();

-- -----------------------------------------------------------------------------------------------------
-- 13. Access (M8): LPR events
-- -----------------------------------------------------------------------------------------------------
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

-- -----------------------------------------------------------------------------------------------------
-- 14. Disputes (M10, W5) — v5. 15. Swaps (M11): still not in the MVP (docs/03-design/08-deferred-tables.md)
-- -----------------------------------------------------------------------------------------------------
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
-- dispute_evidence references consent_record, so it is created in section 18.

-- -----------------------------------------------------------------------------------------------------
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

-- -----------------------------------------------------------------------------------------------------
-- 17. Reporting (M12): KPI view
-- -----------------------------------------------------------------------------------------------------
-- v3: the kpi_daily, vacancy_forecast, occupancy_hourly and reconciliation_report tables are removed
-- (docs/03-design/08-deferred-tables.md). The dashboard counts parking_request on the fly; the view carries aggregates only
-- (no personal data) — the only data a chain operator reads (PRD §9).
-- Owner-rights view on purpose (no security_invoker): the viewer cannot read parking_request (RLS), only these
-- aggregates, so the row filter lives inside the view: the chain operator sees every zone, BQL / system only their
-- own zones. Everyone else (resident, guard, no context) gets no rows.
CREATE VIEW app.kpi_daily_v WITH (security_barrier = true) AS
-- v5: one row per (zone, local day) that has at least one request, paid overstay fee or opened dispute; the first six
-- measures keep their v4 meaning (0 when the day has no request). The row filter is applied once, in visible_zone.
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
), fee AS (      -- overstay fees recorded (waived ones are 'cancelled' and drop out), VND; v6: by the day recorded
  SELECT p.zone_id, (p.created_at AT TIME ZONE vz.timezone)::date AS day, sum(p.amount_vnd)::bigint AS overstay_fees
  FROM app.payment p
  JOIN visible_zone vz ON vz.zone_id = p.zone_id
  WHERE p.kind = 'overstay_fee' AND p.status = 'recorded'
  GROUP BY p.zone_id, (p.created_at AT TIME ZONE vz.timezone)::date
), dsp AS (      -- disputes opened per day; average time to prepare the case file (created_at -> ready_at)
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
       dsp.dispute_prep_minutes_avg           AS dispute_prep_minutes_avg   -- NULL when no case was ready that day
FROM days d
LEFT JOIN req ON req.zone_id = d.zone_id AND req.day = d.day
LEFT JOIN fee ON fee.zone_id = d.zone_id AND fee.day = d.day
LEFT JOIN dsp ON dsp.zone_id = d.zone_id AND dsp.day = d.day;

-- -----------------------------------------------------------------------------------------------------
-- 18. Platform: consent evidence and AI decision log (append-only; ADR-0011)
-- -----------------------------------------------------------------------------------------------------
-- v4: outbox, idempotency_keys and audit_log (with audit_row() and its triggers) are removed; workflow_run stays removed
-- (docs/03-design/08-deferred-tables.md). Use cases insert `notification` in the same transaction and push realtime after commit.

-- Evidence of consent / confirmation (A-03, BR-09, FR-09, AC-07). Written once, never changed. evidence holds ids, hashes
-- and amounts only (e.g. body_sha256, price, policy version) — no names, no plates.
CREATE TABLE app.consent_record (
  id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id       uuid NOT NULL REFERENCES app.app_user (id) ON DELETE RESTRICT,
  zone_id       uuid REFERENCES app.zone (id) ON DELETE RESTRICT,   -- NULL for chain-wide terms (registration)
  action        app.consent_action NOT NULL,   -- v7
  -- v7: share_window (owner OTP, BR-25), booking (renter OTP, BR-25), parking_request (GPS sampling window, BR-27).
  subject_type  text NOT NULL CHECK (subject_type IN ('app_user', 'agreement', 'recovery_case',   -- v7
                                                      'share_window', 'booking', 'parking_request')),
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

-- One row per AI decision / suggestion step (guide ch.7 section 7.6, ch.11 section 11.7). Hashes only: no raw prompt, output
-- or user id (PII, BR-14). Not a substitute for OTel traces (ADR-0008): a queryable summary for the BQL screen. No purge in the MVP.
CREATE TABLE app.ai_decision_log (
  id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  thread_id           text REFERENCES app.agent_thread (thread_id) ON DELETE RESTRICT,
  zone_id             uuid REFERENCES app.zone (id) ON DELETE RESTRICT,
  user_hash           bytea NOT NULL CHECK (length(user_hash) = 32),   -- HMAC-SHA256 of the user id, never the raw id
  workflow            app.workflow_code NOT NULL,
  step                text NOT NULL CHECK (btrim(step) <> ''),          -- graph node name
  model_version       text,                                              -- NULL for deterministic steps
  input_hash          bytea NOT NULL CHECK (length(input_hash) = 32),   -- SHA-256
  output_hash         bytea NOT NULL CHECK (length(output_hash) = 32),  -- SHA-256
  risk_level          app.ai_risk_level NOT NULL,
  outcome             app.ai_outcome NOT NULL,
  human_approved      boolean,                                           -- NULL = no approval needed
  approval_request_id uuid REFERENCES app.approval_request (id) ON DELETE RESTRICT,
  trace_id            text,                                              -- OTel trace id (jump to Tempo)
  latency_ms          integer CHECK (latency_ms IS NULL OR latency_ms >= 0),
  idempotency_key     text NOT NULL UNIQUE,                              -- thread_id:checkpoint_id:node (ADR-0010)
  created_at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ai_decision_log_zone_idx ON app.ai_decision_log (zone_id, created_at DESC);
CREATE INDEX ai_decision_log_thread_idx ON app.ai_decision_log (thread_id);
CREATE INDEX ai_decision_log_approval_idx ON app.ai_decision_log (approval_request_id) WHERE approval_request_id IS NOT NULL;
CREATE TRIGGER ai_decision_log_append_only BEFORE UPDATE OR DELETE OR TRUNCATE ON app.ai_decision_log
  FOR EACH STATEMENT EXECUTE FUNCTION app.reject_mutation();

-- updated_at maintenance
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['zone', 'building', 'slot_pool', 'slot', 'app_user', 'vehicle', 'asset', 'eligibility',
                           'approval_request', 'share_window', 'parking_request', 'booking', 'agreement', 'payment',
                           'agent_thread', 'recovery_case', 'dispute_case'] LOOP
    EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE ON app.%I
                    FOR EACH ROW EXECUTE FUNCTION app.set_updated_at()', t || '_updated_at', t);
  END LOOP;
END $$;

-- -----------------------------------------------------------------------------------------------------
-- 18b. Privacy & retention: not in the MVP (privacy_request, retention_rule, purge/erasure functions)
-- -----------------------------------------------------------------------------------------------------
-- Retention periods (D-05/D-06) and erasure (D-14/D-15) are documented targets, not enforced; they must be
-- implemented before real user data is stored. See docs/03-design/08-deferred-tables.md.

-- -----------------------------------------------------------------------------------------------------
-- 18c. Agent schema (LangGraph checkpointer) — check b, D-12
-- -----------------------------------------------------------------------------------------------------
-- The saver creates its own tables (checkpoints, checkpoint_blobs, checkpoint_writes, checkpoint_migrations,
-- all keyed by thread_id) as parksmart_checkpointer. They hold serialized graph state, which RLS cannot inspect.
-- Protection is therefore (1) isolation: the app role has no access to schema agent and the checkpointer role
-- has no access to schema app; (2) content rule: state carries ids, pseudonyms and pseudonymised text only —
-- the pseudonym map is not persisted in clear (encrypted serializer, see docs/06-operations/02-database-security.md §3). (3) Purging finished
-- threads is deferred with the other retention jobs (app.purge_agent_checkpoints is removed in v3).
-- v4: app.agent_thread (section 7) is the business-side index of those threads: owner, workflow, status, zone.
REVOKE ALL ON SCHEMA agent FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE parksmart_checkpointer IN SCHEMA agent
  GRANT SELECT, DELETE ON TABLES TO parksmart_owner;

-- -----------------------------------------------------------------------------------------------------
-- 19. Knowledge base for W7 (RAG over zone/building rules). pgvector required in every real environment.
-- -----------------------------------------------------------------------------------------------------
-- v3: the knowledge_doc table is merged into the chunk (doc_title, source_uri, doc_version, is_active —
-- docs/03-design/08-deferred-tables.md). A document version is the set of chunks sharing (source_uri, doc_version).
CREATE TABLE app.knowledge_chunk (
  id          uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  zone_id     uuid REFERENCES app.zone (id) ON DELETE RESTRICT,           -- NULL = chain-wide
  building_id uuid,                                                       -- NULL = whole zone
  doc_title   text NOT NULL CHECK (btrim(doc_title) <> ''),
  source_uri  text NOT NULL,
  doc_version integer NOT NULL DEFAULT 1 CHECK (doc_version > 0),
  is_active   boolean NOT NULL DEFAULT true,
  ordinal     integer NOT NULL CHECK (ordinal >= 0),
  content     text NOT NULL CHECK (btrim(content) <> ''),
  created_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (source_uri, doc_version, ordinal),
  -- A building-scoped chunk must name its zone, and the pair must exist (same composite-FK rule as everywhere).
  CHECK (building_id IS NULL OR zone_id IS NOT NULL),
  FOREIGN KEY (building_id, zone_id) REFERENCES app.building (id, zone_id) ON DELETE RESTRICT
);
CREATE INDEX knowledge_chunk_scope_idx ON app.knowledge_chunk (zone_id, building_id) WHERE is_active;

-- The embedding column needs pgvector. Production/compose images ship it; this block fails loudly when it
-- is missing unless the verifier explicitly opts out (SET parksmart.allow_missing_pgvector = 'on').
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_available_extensions WHERE name = 'vector') THEN
    CREATE EXTENSION IF NOT EXISTS vector;
    -- Dimension fixed by the embedding model (TBD, Bedrock Titan v2 = 1024). No ANN index: a few dozen
    -- documents (ADR-0005) → exact scan is faster and exact. Add HNSW above ~50k chunks.
    ALTER TABLE app.knowledge_chunk ADD COLUMN embedding vector(1024) NOT NULL;
  ELSIF coalesce(current_setting('parksmart.allow_missing_pgvector', true), '') <> 'on' THEN
    RAISE EXCEPTION 'pgvector extension is not available';
  ELSE
    RAISE WARNING 'pgvector missing: knowledge_chunk.embedding NOT created (verification mode)';
  END IF;
END $$;

-- -----------------------------------------------------------------------------------------------------
-- 20. Row-Level Security (ADR-0005). The app role is not the owner and has no BYPASSRLS.
--     Pattern: (SELECT app.ctx_…()) is wrapped in a sub-select so the planner evaluates it once per query.
-- -----------------------------------------------------------------------------------------------------

-- 20.1 Reference / configuration: readable by any authenticated session, writable by the zone's BQL.
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['building', 'slot', 'slot_pool', 'zone_policy'] LOOP
    EXECUTE format('ALTER TABLE app.%I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format($p$CREATE POLICY read_authenticated ON app.%I FOR SELECT
                      USING ((SELECT app.ctx_role()) <> 'anonymous')$p$, t);
    EXECUTE format($p$CREATE POLICY manage_zone ON app.%I FOR ALL
                      USING (app.is_zone_staff(zone_id, '{zone_manager}'))
                      WITH CHECK (app.is_zone_staff(zone_id, '{zone_manager}'))$p$, t);
  END LOOP;
END $$;
-- v6 BR-24: W3 runs as 'system' and pauses / resumes intake of a building of its zone (intake_paused_at).
CREATE POLICY system_intake_pause ON app.building FOR UPDATE
  USING (app.is_zone_staff(zone_id, '{system}')) WITH CHECK (app.is_zone_staff(zone_id, '{system}'));
-- TH2 scope is a chain-operator decision (PRD §4, FR-26).
CREATE POLICY chain_operator_manage ON app.slot_pool FOR UPDATE
  USING ((SELECT app.ctx_role()) = 'chain_operator' AND slot_type = 'TH2')
  WITH CHECK ((SELECT app.ctx_role()) = 'chain_operator' AND slot_type = 'TH2');

-- v7 (FR-38): the BQL registry import holds names, phones and plate hashes of one zone: zone staff and the system only.
ALTER TABLE app.bql_registry_import ENABLE ROW LEVEL SECURITY;
CREATE POLICY zone_staff ON app.bql_registry_import FOR ALL
  USING (app.is_zone_staff(zone_id, '{zone_manager,system}'))
  WITH CHECK (app.is_zone_staff(zone_id, '{zone_manager,system}'));

-- 20.2 Identity
ALTER TABLE app.app_user ENABLE ROW LEVEL SECURITY;
CREATE POLICY self ON app.app_user FOR ALL
  USING (id = (SELECT app.ctx_user_id())) WITH CHECK (id = (SELECT app.ctx_user_id()));
CREATE POLICY auth_and_system ON app.app_user FOR ALL
  USING ((SELECT app.ctx_role()) IN ('auth', 'system')) WITH CHECK ((SELECT app.ctx_role()) IN ('auth', 'system'));
-- A BQL sees people who hold an entitlement or a booking in their zone (names for approvals).
CREATE POLICY zone_manager_read ON app.app_user FOR SELECT
  USING ((SELECT app.ctx_role()) = 'zone_manager' AND (
           EXISTS (SELECT 1 FROM app.eligibility e WHERE e.user_id = app_user.id AND e.zone_id = ANY (app.ctx_zone_ids()))
        OR EXISTS (SELECT 1 FROM app.booking b WHERE (b.renter_user_id = app_user.id OR b.provider_user_id = app_user.id)
                                                AND b.zone_id = ANY (app.ctx_zone_ids()))));

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

ALTER TABLE app.vehicle ENABLE ROW LEVEL SECURITY;
CREATE POLICY own_or_system ON app.vehicle FOR ALL
  USING (user_id = (SELECT app.ctx_user_id()) OR (SELECT app.ctx_role()) = 'system')
  WITH CHECK (user_id = (SELECT app.ctx_user_id()) OR (SELECT app.ctx_role()) = 'system');
CREATE POLICY zone_staff_read ON app.vehicle FOR SELECT
  USING ((SELECT app.ctx_role()) IN ('zone_manager', 'guard') AND EXISTS (
           SELECT 1 FROM app.booking b WHERE b.vehicle_id = vehicle.id AND b.zone_id = ANY (app.ctx_zone_ids())));

-- 20.3 Eligibility: the holder and the asset's zone only. Other zones use app.eligibility_level_at (BR-17).
ALTER TABLE app.asset ENABLE ROW LEVEL SECURITY;
CREATE POLICY zone_staff ON app.asset FOR ALL
  USING (app.is_zone_staff(zone_id)) WITH CHECK (app.is_zone_staff(zone_id));
CREATE POLICY holder_read ON app.asset FOR SELECT
  USING (EXISTS (SELECT 1 FROM app.eligibility e WHERE e.asset_id = asset.id AND e.user_id = (SELECT app.ctx_user_id())));

ALTER TABLE app.eligibility ENABLE ROW LEVEL SECURITY;
CREATE POLICY zone_staff ON app.eligibility FOR ALL
  USING (app.is_zone_staff(zone_id)) WITH CHECK (app.is_zone_staff(zone_id));
CREATE POLICY holder_read ON app.eligibility FOR SELECT USING (user_id = (SELECT app.ctx_user_id()));
-- A user may file a claim for themselves; only the zone's BQL can verify it (status stays pending).
CREATE POLICY holder_claim ON app.eligibility FOR INSERT
  WITH CHECK (user_id = (SELECT app.ctx_user_id()) AND status = 'pending');

ALTER TABLE app.slot_holding ENABLE ROW LEVEL SECURITY;
CREATE POLICY zone_staff ON app.slot_holding FOR ALL
  USING (app.is_zone_staff(zone_id)) WITH CHECK (app.is_zone_staff(zone_id));
CREATE POLICY holder_read ON app.slot_holding FOR SELECT USING (user_id = (SELECT app.ctx_user_id()));

-- 20.4 Sharing & booking
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

DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['booking', 'agreement'] LOOP
    EXECUTE format('ALTER TABLE app.%I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format($p$CREATE POLICY parties_read ON app.%I FOR SELECT
                      USING (renter_user_id = (SELECT app.ctx_user_id()) OR provider_user_id = (SELECT app.ctx_user_id()))$p$, t);
    EXECUTE format($p$CREATE POLICY zone_staff ON app.%I FOR ALL
                      USING (app.is_zone_staff(zone_id, '{zone_manager,system,guard}'))
                      WITH CHECK (app.is_zone_staff(zone_id))$p$, t);
  END LOOP;
END $$;

-- 20.5 Approvals, agent threads, recovery cases, money
ALTER TABLE app.agent_thread ENABLE ROW LEVEL SECURITY;
CREATE POLICY owner ON app.agent_thread FOR ALL
  USING (user_id = (SELECT app.ctx_user_id())) WITH CHECK (user_id = (SELECT app.ctx_user_id()));
CREATE POLICY system_all ON app.agent_thread FOR ALL
  USING ((SELECT app.ctx_role()) = 'system') WITH CHECK ((SELECT app.ctx_role()) = 'system');
CREATE POLICY zone_manager_read ON app.agent_thread FOR SELECT
  USING (status = 'awaiting_manager' AND app.is_zone_staff(zone_id, '{zone_manager}'));

ALTER TABLE app.recovery_case ENABLE ROW LEVEL SECURITY;
CREATE POLICY parties_read ON app.recovery_case FOR SELECT
  USING (EXISTS (SELECT 1 FROM app.booking b WHERE b.id = recovery_case.booking_id
                   AND (b.renter_user_id = (SELECT app.ctx_user_id()) OR b.provider_user_id = (SELECT app.ctx_user_id()))));
CREATE POLICY zone_staff ON app.recovery_case FOR ALL
  USING (app.is_zone_staff(zone_id)) WITH CHECK (app.is_zone_staff(zone_id));

ALTER TABLE app.approval_request ENABLE ROW LEVEL SECURITY;
CREATE POLICY zone_staff ON app.approval_request FOR ALL
  USING (app.is_zone_staff(zone_id)) WITH CHECK (app.is_zone_staff(zone_id));

ALTER TABLE app.payment ENABLE ROW LEVEL SECURITY;
CREATE POLICY payer ON app.payment FOR ALL
  USING (payer_user_id = (SELECT app.ctx_user_id())) WITH CHECK (payer_user_id = (SELECT app.ctx_user_id()));
CREATE POLICY zone_staff ON app.payment FOR ALL
  USING (app.is_zone_staff(zone_id)) WITH CHECK (app.is_zone_staff(zone_id));

-- 20.6 Access / LPR: BQL, guards and system jobs of the zone.
ALTER TABLE app.lpr_event ENABLE ROW LEVEL SECURITY;
CREATE POLICY zone_staff ON app.lpr_event FOR ALL
  USING (app.is_zone_staff(zone_id, '{zone_manager,guard,system}'))
  WITH CHECK (app.is_zone_staff(zone_id, '{zone_manager,guard,system}'));

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

-- 20.8 (swaps): not in the MVP.

-- 20.9 Platform and knowledge
ALTER TABLE app.consent_record ENABLE ROW LEVEL SECURITY;
CREATE POLICY own ON app.consent_record FOR SELECT USING (user_id = (SELECT app.ctx_user_id()));
CREATE POLICY own_insert ON app.consent_record FOR INSERT WITH CHECK (user_id = (SELECT app.ctx_user_id()));
CREATE POLICY zone_manager_read ON app.consent_record FOR SELECT USING (app.is_zone_staff(zone_id, '{zone_manager}'));
CREATE POLICY system_all ON app.consent_record FOR ALL
  USING ((SELECT app.ctx_role()) = 'system') WITH CHECK ((SELECT app.ctx_role()) = 'system');

-- Users never read the AI decision log; the BQL reads its own zone; the agent worker (system) writes and reads.
ALTER TABLE app.ai_decision_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY zone_manager_read ON app.ai_decision_log FOR SELECT USING (app.is_zone_staff(zone_id, '{zone_manager}'));
CREATE POLICY system_all ON app.ai_decision_log FOR ALL
  USING ((SELECT app.ctx_role()) = 'system') WITH CHECK ((SELECT app.ctx_role()) = 'system');

ALTER TABLE app.knowledge_chunk ENABLE ROW LEVEL SECURITY;
CREATE POLICY read_authenticated ON app.knowledge_chunk FOR SELECT USING ((SELECT app.ctx_role()) <> 'anonymous');
CREATE POLICY manage_zone ON app.knowledge_chunk FOR ALL
  USING (app.is_zone_staff(zone_id, '{zone_manager}')) WITH CHECK (app.is_zone_staff(zone_id, '{zone_manager}'));

-- Not RLS-protected on purpose (no zone-private data): zone. kpi_daily_v filters rows inside the view (section 17).

-- -----------------------------------------------------------------------------------------------------
-- 21. Grants: least privilege. The app role gets DML, never DDL, TRUNCATE or ownership.
-- -----------------------------------------------------------------------------------------------------
GRANT USAGE ON SCHEMA app TO parksmart_app, parksmart_readonly;
GRANT USAGE, CREATE ON SCHEMA agent TO parksmart_checkpointer;   -- the saver creates its own tables once

GRANT SELECT ON ALL TABLES IN SCHEMA app TO parksmart_app;
GRANT INSERT, UPDATE ON ALL TABLES IN SCHEMA app TO parksmart_app;
GRANT DELETE ON app.notification, app.knowledge_chunk TO parksmart_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA app TO parksmart_app;

-- Append-only tables: INSERT + SELECT only (the reject_mutation trigger also stops the owner).
REVOKE UPDATE, DELETE, TRUNCATE ON app.consent_record, app.ai_decision_log, app.dispute_evidence FROM parksmart_app;
-- The view is read-only for everybody (INSERT/UPDATE on it are not possible anyway, grants are cleaned up).
REVOKE INSERT, UPDATE ON app.kpi_daily_v FROM parksmart_app;

-- Ciphertext: never selectable (MVP shows masked plates only; the logged reveal functions are deferred).
REVOKE SELECT ON app.vehicle, app.lpr_event FROM parksmart_app;
GRANT SELECT (id, user_id, plate_key_version, plate_hash, plate_masked, size_class, is_active, created_at, updated_at)
  ON app.vehicle TO parksmart_app;
GRANT SELECT (id, zone_id, source_code, source_event_id, gate_code, direction, occurred_at, received_at, plate_hash,
              plate_masked, ocr_confidence, status, matched_vehicle_id, matched_booking_id, reviewed_by, reviewed_at)
  ON app.lpr_event TO parksmart_app;
-- Original evidence photo key: never selectable (the blurred copy object_key_masked is the only image shown, BR-09).
REVOKE SELECT ON app.dispute_evidence FROM parksmart_app;
GRANT SELECT (id, zone_id, case_id, kind, source, object_key_masked, sha256, lpr_event_id, consent_record_id, agreement_id,
              snapshot, confidence, submitted_by, created_at)
  ON app.dispute_evidence TO parksmart_app;

REVOKE ALL ON ALL FUNCTIONS IN SCHEMA app FROM PUBLIC;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA app TO parksmart_app;

-- Read-only role: aggregates only.
GRANT SELECT ON app.zone, app.kpi_daily_v TO parksmart_readonly;
