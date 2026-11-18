-- =====================================================================================================
-- ParkSmart AI (P-142) — PostgreSQL schema
-- Target: PostgreSQL 16 (compose image pgvector/pgvector:pg16, RDS PostgreSQL 16).
-- v2 (2026-11-18): decisions D-01…D-30 from 10-decision-log.md applied. Executed on PG 17.10 only — see
-- 00-overview.md §6 for why PG16/pgvector could not be run in this environment.
-- Uses only PG ≤16 features. Extensions: btree_gist (EXCLUDE on time ranges), pgcrypto (plate crypto
-- per ADR-0005; optional if plates are encrypted in the app), vector (RAG W7, section 18).
--
-- Run as the schema owner role (parksmart_owner) — never as the application role.
--   psql -v ON_ERROR_STOP=1 -f 02-schema.sql
-- In the repo this file is split into Alembic revisions (op.execute("""SQL""")), see 07-operations.md.
--
-- Conventions
--   * schema `app` for business tables; schema `agent` is reserved for langgraph-checkpoint-postgres.
--   * PK: uuid (UUIDv7, app.uuid_v7()) for entities; bigint identity for the two append-heavy logs
--     (lpr_event, outbox, audit_log) and a per-zone sequence for ledger_entry. Rationale: 00-overview.md §4.
--   * every zone-owned table carries zone_id NOT NULL and a composite FK (x_id, zone_id) to its parent, so
--     the denormalised zone_id used by RLS can never disagree with the hierarchy.
--   * money: bigint VND (đồng has no minor unit), CHECK >= 0.
--   * time: timestamptz everywhere; time windows are tstzrange '[)' (half-open).
-- =====================================================================================================

SET client_min_messages = warning;
SET lock_timeout = '5s';            -- migrations must not queue behind long locks (07-operations.md §1)
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

-- Session guard rails for the application role (05-concurrency.md §0). Jobs may raise statement_timeout
-- with SET LOCAL for a known long query.
ALTER ROLE parksmart_app SET statement_timeout = '5s';
ALTER ROLE parksmart_app SET lock_timeout = '2s';
ALTER ROLE parksmart_app SET idle_in_transaction_session_timeout = '30s';

REVOKE CREATE ON SCHEMA public FROM PUBLIC;

-- -----------------------------------------------------------------------------------------------------
-- 1. Enumerations (fixed sets the code switches on; open-ended catalogues are lookup tables instead)
-- -----------------------------------------------------------------------------------------------------
CREATE TYPE app.slot_type          AS ENUM ('TH1', 'TH2', 'TH3');
-- Order matters: building < zone < chain < public, compared with < / <= in triggers.
CREATE TYPE app.open_scope         AS ENUM ('building', 'zone', 'chain', 'public');
-- Order matters: L1 (strongest) < L2 < L3 < L4.
CREATE TYPE app.eligibility_level  AS ENUM ('L1', 'L2', 'L3', 'L4');
CREATE TYPE app.user_role          AS ENUM ('resident', 'renter', 'guard', 'zone_manager', 'chain_operator');
CREATE TYPE app.user_status        AS ENUM ('active', 'locked', 'deleted');
CREATE TYPE app.building_kind      AS ENUM ('residential_tower', 'lowrise_cluster', 'public_lot');
CREATE TYPE app.asset_kind         AS ENUM ('apartment', 'shophouse', 'office', 'clinic', 'kindergarten', 'other');
CREATE TYPE app.eligibility_role   AS ENUM ('owner', 'tenant', 'authorized', 'employee');
CREATE TYPE app.eligibility_status AS ENUM ('pending', 'verified', 'revoked', 'expired');
CREATE TYPE app.holding_kind       AS ENUM ('owner', 'lessee', 'swap_usage');
CREATE TYPE app.consent_kind       AS ENUM ('plate_photo_processing', 'sharing_rules');
CREATE TYPE app.share_status       AS ENUM ('open', 'closed_early', 'cancelled', 'expired');
CREATE TYPE app.request_outcome    AS ENUM ('matched', 'redirected_th3', 'redirected_public', 'blocked', 'no_match');
CREATE TYPE app.booking_status     AS ENUM ('held', 'pending_agreement', 'pending_approval', 'confirmed',
                                            'completed', 'relocated', 'cancelled', 'expired', 'rejected');
CREATE TYPE app.agreement_status   AS ENUM ('pending_confirmation', 'pending_approval', 'effective',
                                            'rejected', 'expired', 'cancelled');
CREATE TYPE app.approval_kind      AS ENUM ('agreement_over_threshold', 'dispute_verification', 'swap',
                                            'early_return_escalation');
CREATE TYPE app.approval_status    AS ENUM ('pending', 'approved', 'rejected', 'expired', 'cancelled');
CREATE TYPE app.ledger_entry_type  AS ENUM ('agreement_effective', 'early_return_relocation', 'overstay_fee',
                                            'swap_applied', 'booking_cancelled', 'payment_recorded',
                                            'early_return_settlement');   -- D-09
-- relocation_th3: renter pays the TH3 price for the relocated period; early_return_refund: unused share time
-- refunded to the renter (D-09). payment.direction tells charges from refunds.
CREATE TYPE app.payment_kind       AS ENUM ('share_booking', 'th3_visit', 'overstay_fee', 'relocation_th3',
                                            'early_return_refund');
CREATE TYPE app.payment_status     AS ENUM ('pending', 'paid_simulated', 'failed', 'cancelled');
CREATE TYPE app.voucher_status     AS ENUM ('issued', 'redeemed', 'expired', 'void');
CREATE TYPE app.lpr_source_kind    AS ENUM ('webhook', 'mqtt', 'db', 'csv', 'simulated');
CREATE TYPE app.gate_direction     AS ENUM ('in', 'out');
CREATE TYPE app.lpr_status         AS ENUM ('accepted', 'pending_review', 'confirmed_manual', 'unreadable');
CREATE TYPE app.overstay_status    AS ENUM ('open', 'charged', 'waived', 'escalated');
CREATE TYPE app.dispute_source     AS ENUM ('app', 'lpr');
CREATE TYPE app.dispute_status     AS ENUM ('open', 'awaiting_verification', 'resolved', 'dismissed');
CREATE TYPE app.evidence_kind      AS ENUM ('photo', 'lpr_event', 'ledger_entry');
CREATE TYPE app.swap_kind          AS ENUM ('two_party', 'chain');
CREATE TYPE app.swap_status        AS ENUM ('pending_approval', 'approved', 'rejected', 'applied', 'cancelled');
CREATE TYPE app.need_status        AS ENUM ('open', 'fulfilled', 'withdrawn');
CREATE TYPE app.day_kind           AS ENUM ('weekday', 'weekend', 'holiday');
CREATE TYPE app.workflow_code      AS ENUM ('W0', 'W1', 'W2', 'W3', 'W4', 'W5', 'W6', 'W7');
CREATE TYPE app.workflow_status    AS ENUM ('running', 'waiting_approval', 'completed', 'failed', 'cancelled');
CREATE TYPE app.privacy_request_kind   AS ENUM ('access', 'rectify', 'delete', 'withdraw_consent', 'restrict', 'object');
CREATE TYPE app.privacy_request_status AS ENUM ('received', 'acknowledged', 'completed', 'rejected');

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
-- 3. Facility (M2) and pools (M3): Chain → Zone → Subzone → Building → Basement → Slot
-- -----------------------------------------------------------------------------------------------------
CREATE TABLE app.chain (
  id          uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  code        text NOT NULL UNIQUE CHECK (code ~ '^[A-Z0-9_-]{2,32}$'),
  name        text NOT NULL CHECK (btrim(name) <> ''),
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE app.zone (
  id          uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  chain_id    uuid NOT NULL REFERENCES app.chain (id) ON DELETE RESTRICT,
  code        text NOT NULL CHECK (code ~ '^[A-Z0-9_-]{1,32}$'),
  name        text NOT NULL CHECK (btrim(name) <> ''),
  -- Business-day boundaries (daily reconciliation, "expires on day D", holidays) use this zone.
  timezone    text NOT NULL DEFAULT 'Asia/Ho_Chi_Minh',
  is_active   boolean NOT NULL DEFAULT true,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (chain_id, code)
);

CREATE TABLE app.subzone (
  id          uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  zone_id     uuid NOT NULL REFERENCES app.zone (id) ON DELETE RESTRICT,
  code        text NOT NULL,
  name        text NOT NULL CHECK (btrim(name) <> ''),
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (zone_id, code),
  UNIQUE (id, zone_id)
);

CREATE TABLE app.building (
  id          uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  zone_id     uuid NOT NULL,
  subzone_id  uuid NOT NULL,
  code        text NOT NULL,
  name        text NOT NULL CHECK (btrim(name) <> ''),
  kind        app.building_kind NOT NULL,
  is_active   boolean NOT NULL DEFAULT true,
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (zone_id, code),
  UNIQUE (id, zone_id),
  FOREIGN KEY (subzone_id, zone_id) REFERENCES app.subzone (id, zone_id) ON DELETE RESTRICT
);

-- A public lot is modelled as a building of kind public_lot with one ground-level "basement".
CREATE TABLE app.basement (
  id          uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  zone_id     uuid NOT NULL,
  building_id uuid NOT NULL,
  code        text NOT NULL,                       -- B1, B2, G
  created_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (building_id, code),
  UNIQUE (id, building_id, zone_id),
  FOREIGN KEY (building_id, zone_id) REFERENCES app.building (id, zone_id) ON DELETE RESTRICT
);

-- Vehicle/slot size catalogue (TBD in docs → lookup table so BQL can extend it without a migration).
-- A vehicle fits a slot when vehicle.rank <= slot.rank.
CREATE TABLE app.size_class (
  code          text PRIMARY KEY CHECK (code ~ '^[A-Z0-9_]{1,16}$'),
  rank          smallint NOT NULL UNIQUE CHECK (rank BETWEEN 1 AND 100),
  label_vi      text NOT NULL,
  max_length_cm integer CHECK (max_length_cm > 0),
  max_width_cm  integer CHECK (max_width_cm > 0)
);

-- Pool = slots of one type in one building (TH1) or one zone (TH2/TH3). Holds the open scope (FR-26).
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

CREATE TABLE app.slot (
  id              uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  zone_id         uuid NOT NULL,
  building_id     uuid NOT NULL,
  basement_id     uuid NOT NULL,
  pool_id         uuid NOT NULL,
  -- Denormalised from the pool for cheap filtering; the composite FK keeps it consistent.
  slot_type       app.slot_type NOT NULL,
  code            text NOT NULL,                   -- B2-045
  size_class_code text NOT NULL REFERENCES app.size_class (code) ON DELETE RESTRICT,
  is_active       boolean NOT NULL DEFAULT true,   -- soft retire; slots are referenced by history
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (building_id, code),
  UNIQUE (id, zone_id),
  UNIQUE (id, zone_id, slot_type),
  FOREIGN KEY (basement_id, building_id, zone_id) REFERENCES app.basement (id, building_id, zone_id) ON DELETE RESTRICT,
  FOREIGN KEY (pool_id, slot_type, zone_id) REFERENCES app.slot_pool (id, slot_type, zone_id) ON DELETE RESTRICT
);
CREATE INDEX slot_pool_id_idx ON app.slot (pool_id);
CREATE INDEX slot_zone_type_idx ON app.slot (zone_id, slot_type) WHERE is_active;

CREATE TABLE app.gate (
  id          uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  zone_id     uuid NOT NULL REFERENCES app.zone (id) ON DELETE RESTRICT,
  building_id uuid,
  code        text NOT NULL,                       -- G1, G2
  created_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (zone_id, code),
  UNIQUE (id, zone_id),
  FOREIGN KEY (building_id, zone_id) REFERENCES app.building (id, zone_id) ON DELETE RESTRICT
);

-- -----------------------------------------------------------------------------------------------------
-- 4. Identity (M1 accounts): one account for the whole chain (FR-23)
-- -----------------------------------------------------------------------------------------------------
CREATE TABLE app.app_user (
  id             uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  full_name      text NOT NULL CHECK (btrim(full_name) <> '' AND length(full_name) <= 200),
  -- E.164, normalised by the app (+84…). Login identifier.
  -- NULL only after erasure (D-14); live accounts always have a phone.
  phone_e164     text CHECK (phone_e164 ~ '^\+[1-9][0-9]{7,14}$'),
  email          text CHECK (email IS NULL OR email ~ '^[^@\s]+@[^@\s]+$'),
  password_hash  text NOT NULL CHECK (password_hash LIKE '$argon2id$%'),   -- ADR-0006
  role           app.user_role NOT NULL DEFAULT 'resident',
  status         app.user_status NOT NULL DEFAULT 'active',
  failed_logins  smallint NOT NULL DEFAULT 0 CHECK (failed_logins >= 0),
  locked_until   timestamptz,
  deleted_at     timestamptz,                      -- soft delete; PII is scrubbed by the erasure job
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT app_user_deleted_consistent CHECK ((status = 'deleted') = (deleted_at IS NOT NULL)),
  CONSTRAINT app_user_phone_required CHECK (status = 'deleted' OR phone_e164 IS NOT NULL)
);
-- Unique among live accounts only, so a deleted account does not block re-registration.
CREATE UNIQUE INDEX app_user_phone_uq ON app.app_user (phone_e164) WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX app_user_email_uq ON app.app_user (lower(email)) WHERE deleted_at IS NULL AND email IS NOT NULL;

-- Zones a BQL / guard works for (JWT claim zone_ids). Junction table, M:N.
CREATE TABLE app.staff_zone (
  user_id    uuid NOT NULL REFERENCES app.app_user (id) ON DELETE CASCADE,
  zone_id    uuid NOT NULL REFERENCES app.zone (id) ON DELETE RESTRICT,
  granted_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, zone_id)
);
CREATE INDEX staff_zone_zone_idx ON app.staff_zone (zone_id);

-- A-03 / BR-09: registration requires consent; withdrawal is a new state, never a delete.
CREATE TABLE app.consent (
  id           uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  user_id      uuid NOT NULL REFERENCES app.app_user (id) ON DELETE CASCADE,
  kind         app.consent_kind NOT NULL,
  text_version text NOT NULL,                      -- version of the consent text shown
  granted_at   timestamptz NOT NULL DEFAULT now(),
  withdrawn_at timestamptz,
  CHECK (withdrawn_at IS NULL OR withdrawn_at >= granted_at)
);
CREATE UNIQUE INDEX consent_active_uq ON app.consent (user_id, kind) WHERE withdrawn_at IS NULL;

-- ADR-0006: refresh tokens stored as hashes, rotated on every use; reuse revokes the family.
CREATE TABLE app.refresh_token (
  id          uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  user_id     uuid NOT NULL REFERENCES app.app_user (id) ON DELETE CASCADE,
  family_id   uuid NOT NULL,
  token_hash  bytea NOT NULL UNIQUE CHECK (length(token_hash) = 32),
  issued_at   timestamptz NOT NULL DEFAULT now(),
  expires_at  timestamptz NOT NULL,
  used_at     timestamptz,                         -- set when rotated; a second use = reuse attack
  revoked_at  timestamptz,
  CHECK (expires_at > issued_at)
);
CREATE INDEX refresh_token_user_idx ON app.refresh_token (user_id);
CREATE INDEX refresh_token_family_idx ON app.refresh_token (family_id) WHERE revoked_at IS NULL;

CREATE TABLE app.password_reset_token (
  id          uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  user_id     uuid NOT NULL REFERENCES app.app_user (id) ON DELETE CASCADE,
  token_hash  bytea NOT NULL UNIQUE CHECK (length(token_hash) = 32),
  expires_at  timestamptz NOT NULL,
  used_at     timestamptz,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX password_reset_token_user_idx ON app.password_reset_token (user_id);

-- Vehicles belong to a user, not a zone. Plate stored three ways (00-overview.md §4.6):
--   plate_ciphertext — AES-256-GCM envelope produced by the APP (data key wrapped by KMS, D-07 and
--                      adr-proposals/ADR-0005-amendment.md); never selectable by the app role directly
--                      (column grant), only through app.reveal_* functions that log access.
--   plate_hash       — HMAC-SHA256(normalised plate) with a separate KMS-held key ("blind index").
--   plate_masked     — display form "30A-•••.••".
-- On erasure (D-14) ciphertext and hash are set to NULL and the row is deactivated; bookings keep the id.
CREATE TABLE app.vehicle (
  id                uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  user_id           uuid NOT NULL REFERENCES app.app_user (id) ON DELETE RESTRICT,
  plate_ciphertext  bytea,
  plate_key_version smallint NOT NULL DEFAULT 1 CHECK (plate_key_version > 0),
  plate_hash        bytea CHECK (length(plate_hash) = 32),
  plate_masked      text NOT NULL CHECK (btrim(plate_masked) <> ''),
  size_class_code   text NOT NULL REFERENCES app.size_class (code) ON DELETE RESTRICT,
  is_active         boolean NOT NULL DEFAULT true, -- soft delete: bookings and LPR history keep pointing here
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now(),
  UNIQUE (id, user_id),
  CONSTRAINT vehicle_plate_pair CHECK ((plate_ciphertext IS NULL) = (plate_hash IS NULL)),
  CONSTRAINT vehicle_active_has_plate CHECK (NOT is_active OR plate_ciphertext IS NOT NULL)
);
CREATE UNIQUE INDEX vehicle_user_plate_uq ON app.vehicle (user_id, plate_hash) WHERE is_active;
CREATE INDEX vehicle_plate_hash_idx ON app.vehicle (plate_hash) WHERE is_active;   -- LPR match (N1)

-- -----------------------------------------------------------------------------------------------------
-- 5. Eligibility (M1): (asset, role, validity) entitlements, verified by the BQL of the asset's zone
-- -----------------------------------------------------------------------------------------------------
-- Assets are what confer eligibility (apartment, shophouse, office…). Parking slots are NOT assets here:
-- slot usage rights live in slot_holding (see 00-overview.md assumption AS-07).
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
-- Swaps (M11) close one holding and open another, so history is preserved.
CREATE TABLE app.slot_holding (
  id               uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  zone_id          uuid NOT NULL,
  slot_id          uuid NOT NULL,
  slot_type        app.slot_type NOT NULL,
  user_id          uuid NOT NULL REFERENCES app.app_user (id) ON DELETE RESTRICT,
  kind             app.holding_kind NOT NULL,
  held_during      tstzrange NOT NULL CHECK (NOT isempty(held_during) AND NOT lower_inf(held_during)),
  swap_proposal_id uuid,                           -- FK added after app.swap_proposal exists
  -- A holding entered by mistake is voided, not deleted; voided rows no longer block the slot.
  voided_at        timestamptz,
  void_reason      text CHECK (void_reason IS NULL OR btrim(void_reason) <> ''),
  created_at       timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (slot_id, zone_id, slot_type) REFERENCES app.slot (id, zone_id, slot_type) ON DELETE RESTRICT,
  CONSTRAINT slot_holding_type_kind CHECK (
       (slot_type = 'TH1' AND kind IN ('owner', 'swap_usage'))
    OR (slot_type = 'TH2' AND kind IN ('lessee', 'swap_usage'))),
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
  -- "default, confirm with BQL". Rationale and sources per column: 10-decision-log.md (D-id in brackets).
  buffer_before              interval NOT NULL DEFAULT '15 minutes'        -- default, confirm with BQL [D-02]
                               CHECK (buffer_before >= interval '0'),
  buffer_after               interval NOT NULL DEFAULT '30 minutes'        -- default, confirm with BQL [D-02]
                               CHECK (buffer_after >= interval '0'),
  approval_threshold_vnd     bigint NOT NULL DEFAULT 1000000               -- default, confirm with BQL [D-08] BR-12
                               CHECK (approval_threshold_vnd >= 0),
  hold_ttl                   interval NOT NULL DEFAULT '10 minutes'        -- default, confirm with BQL [D-16]
                               CHECK (hold_ttl > interval '0'),
  agreement_confirm_ttl      interval NOT NULL DEFAULT '30 minutes'        -- default, confirm with BQL [D-16]
                               CHECK (agreement_confirm_ttl > interval '0'),
  overstay_grace             interval NOT NULL DEFAULT '10 minutes'        -- default, confirm with BQL [D-03]
                               CHECK (overstay_grace >= interval '0'),
  overstay_fee_per_hour_vnd  bigint NOT NULL DEFAULT 50000                 -- default, confirm with BQL [D-03] BR-08
                               CHECK (overstay_fee_per_hour_vnd >= 0),
  overstay_reminder_every    interval NOT NULL DEFAULT '15 minutes'        -- default, confirm with BQL [D-03]
                               CHECK (overstay_reminder_every >= interval '1 minute'),
  -- BR-16: a running booking survives the expiry of its entitlement for at most this long (NULL = to its end).
  eligibility_grace_max      interval DEFAULT '7 days'                     -- default, confirm with BQL [D-04]
                               CHECK (eligibility_grace_max IS NULL OR eligibility_grace_max >= interval '0'),
  swap_requires_party_consent boolean NOT NULL DEFAULT true,               -- default, confirm with BQL [D-10]
  -- Who pays when the owner returns early (AC-09 TBD). Only rule implemented: renter pays the TH3 price for the
  -- relocated period, unused share time is refunded, the provider pays nothing extra.  [D-09]
  early_return_cost_rule     text NOT NULL DEFAULT 'renter_pays_th3_relocated'   -- default, confirm with BQL
                               CHECK (early_return_cost_rule IN ('renter_pays_th3_relocated')),
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

-- Price per (slot type × level × unit) — BR-19. Integer VND.
CREATE TABLE app.price_rule (
  id             uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  zone_policy_id uuid NOT NULL REFERENCES app.zone_policy (id) ON DELETE CASCADE,
  slot_type      app.slot_type NOT NULL,
  level          app.eligibility_level NOT NULL,
  unit           text NOT NULL CHECK (unit IN ('hour', 'day')),
  price_vnd      bigint NOT NULL CHECK (price_vnd >= 0),
  UNIQUE (zone_policy_id, slot_type, level, unit)
);

CREATE TABLE app.agreement_template (
  id             uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  zone_id        uuid NOT NULL REFERENCES app.zone (id) ON DELETE RESTRICT,
  version        integer NOT NULL CHECK (version > 0),
  body_md        text NOT NULL CHECK (btrim(body_md) <> ''),
  effective_from timestamptz NOT NULL,
  created_at     timestamptz NOT NULL DEFAULT now(),
  UNIQUE (zone_id, version),
  UNIQUE (id, zone_id)
);

-- Holidays for N4 forecasts (day_kind = holiday). Chain-wide calendar, local dates.
CREATE TABLE app.holiday (
  chain_id   uuid NOT NULL REFERENCES app.chain (id) ON DELETE CASCADE,
  day        date NOT NULL,
  name       text NOT NULL,
  PRIMARY KEY (chain_id, day)
);

-- -----------------------------------------------------------------------------------------------------
-- 7. Approvals (M12 HITL queue). Defined before the tables that reference it.
-- -----------------------------------------------------------------------------------------------------
CREATE TABLE app.approval_request (
  id            uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  zone_id       uuid NOT NULL REFERENCES app.zone (id) ON DELETE RESTRICT,   -- zone of the slot (BR-18)
  kind          app.approval_kind NOT NULL,
  subject_id    uuid NOT NULL,                     -- agreement / dispute_ticket / swap_proposal / booking id
  thread_id     text NOT NULL,                     -- LangGraph thread to resume
  status        app.approval_status NOT NULL DEFAULT 'pending',
  summary       text,                              -- pseudonymised, for the queue list
  requested_at  timestamptz NOT NULL DEFAULT now(),
  due_at        timestamptz,
  -- Users are never hard-deleted (soft delete + PII scrub), so decision makers are kept with RESTRICT.
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

-- -----------------------------------------------------------------------------------------------------
-- 8. Sharing (M4): owner publishes a window; the buffer protects the owner's return (BR-07, FR-06)
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
-- Hold sweeper and N2 overstay scan.
CREATE INDEX booking_hold_expiry_idx ON app.booking (hold_expires_at) WHERE status = 'held';
CREATE INDEX booking_active_end_idx ON app.booking (zone_id, upper(period)) WHERE status = 'confirmed';

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
  v_vehicle_rk  smallint;
  v_level       app.eligibility_level;
BEGIN
  SELECT s.slot_type, s.building_id, s.is_active, sc.rank AS size_rank
    INTO v_slot
  FROM app.slot s JOIN app.size_class sc ON sc.code = s.size_class_code
  WHERE s.id = NEW.slot_id;

  IF NOT v_slot.is_active THEN
    RAISE EXCEPTION 'slot % is retired', NEW.slot_id USING ERRCODE = 'check_violation';
  END IF;

  -- BR-11: vehicle must fit.
  SELECT sc.rank INTO v_vehicle_rk
  FROM app.vehicle v JOIN app.size_class sc ON sc.code = v.size_class_code
  WHERE v.id = NEW.vehicle_id;
  IF v_vehicle_rk > v_slot.size_rank THEN
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
    -- and this check re-reads the window if such an UPDATE committed first (05-concurrency.md §2).
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
-- 11. Agreements, OTP and the append-only hash-chained ledger (M6)
-- -----------------------------------------------------------------------------------------------------
CREATE TABLE app.agreement (
  id                    uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  zone_id               uuid NOT NULL,             -- zone of the slot: its template and price frame (AC-07)
  booking_id            uuid NOT NULL UNIQUE,
  template_id           uuid NOT NULL,
  zone_policy_id        uuid NOT NULL,             -- policy version used for price / fees
  provider_user_id      uuid NOT NULL REFERENCES app.app_user (id) ON DELETE RESTRICT,
  renter_user_id        uuid NOT NULL REFERENCES app.app_user (id) ON DELETE RESTRICT,
  price_vnd             bigint NOT NULL CHECK (price_vnd >= 0),
  -- Rendered text is immutable evidence; its hash goes into the ledger payload.
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
  FOREIGN KEY (template_id, zone_id) REFERENCES app.agreement_template (id, zone_id) ON DELETE RESTRICT,
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
CREATE INDEX agreement_template_idx ON app.agreement (template_id);
CREATE INDEX agreement_policy_idx ON app.agreement (zone_policy_id);
CREATE INDEX agreement_approval_idx ON app.agreement (approval_request_id) WHERE approval_request_id IS NOT NULL;
CREATE INDEX agreement_deadline_idx ON app.agreement (confirm_deadline) WHERE status = 'pending_confirmation';

-- ADR-0006: 6-digit OTP, hashed, expiring, limited attempts.
CREATE TABLE app.otp_challenge (
  id           uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  user_id      uuid NOT NULL REFERENCES app.app_user (id) ON DELETE CASCADE,
  purpose      text NOT NULL CHECK (purpose IN ('agreement_confirm')),
  subject_id   uuid NOT NULL,
  code_hash    bytea NOT NULL CHECK (length(code_hash) = 32),
  expires_at   timestamptz NOT NULL,
  attempts     smallint NOT NULL DEFAULT 0,
  max_attempts smallint NOT NULL DEFAULT 5 CHECK (max_attempts BETWEEN 1 AND 10),
  consumed_at  timestamptz,
  created_at   timestamptz NOT NULL DEFAULT now(),
  CHECK (attempts BETWEEN 0 AND max_attempts)
);
CREATE UNIQUE INDEX otp_challenge_active_uq ON app.otp_challenge (user_id, purpose, subject_id) WHERE consumed_at IS NULL;

-- One chain per zone: the BQL of the zone verifies its own chain, and zones do not contend on one lock.
CREATE TABLE app.ledger_head (
  zone_id   uuid PRIMARY KEY REFERENCES app.zone (id) ON DELETE RESTRICT,
  last_seq  bigint NOT NULL DEFAULT 0 CHECK (last_seq >= 0),
  last_hash bytea NOT NULL DEFAULT decode(repeat('00', 32), 'hex')
);

CREATE TABLE app.ledger_entry (
  zone_id         uuid NOT NULL REFERENCES app.zone (id) ON DELETE RESTRICT,
  seq             bigint NOT NULL CHECK (seq > 0),
  entry_type      app.ledger_entry_type NOT NULL,
  subject_type    text NOT NULL CHECK (subject_type IN ('agreement', 'booking', 'payment', 'overstay_case', 'swap_proposal')),
  subject_id      uuid NOT NULL,
  payload         jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),  -- ids + amounts, no names/plates
  idempotency_key text NOT NULL UNIQUE,
  created_at      timestamptz NOT NULL,
  prev_hash       bytea NOT NULL CHECK (length(prev_hash) = 32),
  hash            bytea NOT NULL CHECK (length(hash) = 32),
  PRIMARY KEY (zone_id, seq)
);
CREATE INDEX ledger_entry_subject_idx ON app.ledger_entry (subject_type, subject_id);
CREATE INDEX ledger_entry_zone_time_idx ON app.ledger_entry (zone_id, created_at);

-- Canonical hash input. jsonb::text is deterministic (keys sorted, whitespace normalised); the time is
-- hashed as epoch microseconds so the session TimeZone cannot change the result.
CREATE FUNCTION app.ledger_hash(p_prev bytea, p_zone uuid, p_seq bigint, p_type app.ledger_entry_type,
                                p_subject_type text, p_subject_id uuid, p_payload jsonb, p_at timestamptz)
RETURNS bytea LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
  SELECT sha256(p_prev || convert_to(concat_ws('|', p_zone::text, p_seq::text, p_type::text, p_subject_type,
                                               p_subject_id::text, p_payload::text,
                                               (extract(epoch FROM p_at) * 1000000)::bigint::text), 'UTF8'))
$$;

-- The only write path into the ledger. Serialises appends per zone with a row lock on ledger_head and is
-- idempotent on idempotency_key (LangGraph re-runs nodes on resume, arq retries jobs).
CREATE FUNCTION app.ledger_append(p_zone uuid, p_type app.ledger_entry_type, p_subject_type text,
                                  p_subject_id uuid, p_payload jsonb, p_idempotency_key text)
RETURNS TABLE (seq bigint, hash bytea)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, app AS $$
#variable_conflict use_column
DECLARE
  v_head app.ledger_head%ROWTYPE;
  v_at   timestamptz := date_trunc('milliseconds', clock_timestamp());
  v_hash bytea;
BEGIN
  IF NOT (app.is_zone_staff(p_zone) OR app.ctx_role() = 'system') THEN
    RAISE EXCEPTION 'ledger_append requires system or BQL context for zone %', p_zone
      USING ERRCODE = 'insufficient_privilege';
  END IF;

  INSERT INTO app.ledger_head (zone_id) VALUES (p_zone) ON CONFLICT (zone_id) DO NOTHING;
  SELECT * INTO v_head FROM app.ledger_head h WHERE h.zone_id = p_zone FOR UPDATE;

  -- Checked under the head lock, so two retries of the same step cannot both append.
  RETURN QUERY SELECT e.seq, e.hash FROM app.ledger_entry e WHERE e.idempotency_key = p_idempotency_key;
  IF FOUND THEN
    RETURN;
  END IF;

  v_hash := app.ledger_hash(v_head.last_hash, p_zone, v_head.last_seq + 1, p_type, p_subject_type,
                            p_subject_id, p_payload, v_at);
  INSERT INTO app.ledger_entry (zone_id, seq, entry_type, subject_type, subject_id, payload,
                                idempotency_key, created_at, prev_hash, hash)
  VALUES (p_zone, v_head.last_seq + 1, p_type, p_subject_type, p_subject_id, p_payload,
          p_idempotency_key, v_at, v_head.last_hash, v_hash);
  UPDATE app.ledger_head h SET last_seq = v_head.last_seq + 1, last_hash = v_hash WHERE h.zone_id = p_zone;

  RETURN QUERY SELECT v_head.last_seq + 1, v_hash;
END $$;

-- Integrity check (M6 "kiểm tra toàn vẹn"): returns the first broken seq, or NULL when the chain is intact.
CREATE FUNCTION app.ledger_verify(p_zone uuid) RETURNS bigint
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, app AS $$
DECLARE
  r      record;
  v_prev bytea := decode(repeat('00', 32), 'hex');
  v_seq  bigint := 0;
BEGIN
  IF NOT (app.is_zone_staff(p_zone) OR app.ctx_role() = 'system') THEN
    RAISE EXCEPTION 'ledger_verify requires system or BQL context' USING ERRCODE = 'insufficient_privilege';
  END IF;
  FOR r IN SELECT * FROM app.ledger_entry e WHERE e.zone_id = p_zone ORDER BY e.seq LOOP
    v_seq := v_seq + 1;
    IF r.seq <> v_seq OR r.prev_hash <> v_prev
       OR r.hash <> app.ledger_hash(v_prev, r.zone_id, r.seq, r.entry_type, r.subject_type, r.subject_id,
                                    r.payload, r.created_at) THEN
      RETURN r.seq;
    END IF;
    v_prev := r.hash;
  END LOOP;
  RETURN NULL;
END $$;

-- Append-only, even for the table owner (grants alone do not stop the owner). Statement-level, so even an
-- UPDATE/DELETE that matches no row is refused. Tables created with the trigger argument 'purgeable' accept a
-- DELETE only inside app.purge_expired() (which sets parksmart.retention_purge locally and deletes rows older
-- than their retention_rule). The ledger is NOT purgeable.
CREATE FUNCTION app.reject_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' AND TG_NARGS > 0 AND TG_ARGV[0] = 'purgeable'
     AND current_setting('parksmart.retention_purge', true) = 'on' THEN
    RETURN NULL;
  END IF;
  RAISE EXCEPTION '% is append-only (% rejected)', TG_TABLE_NAME, TG_OP USING ERRCODE = 'insufficient_privilege';
END $$;
CREATE TRIGGER ledger_entry_no_update BEFORE UPDATE OR DELETE OR TRUNCATE ON app.ledger_entry
  FOR EACH STATEMENT EXECUTE FUNCTION app.reject_mutation();

-- -----------------------------------------------------------------------------------------------------
-- 12. Payment (M7, VietQR mock) and shophouse vouchers (FR-22)
-- -----------------------------------------------------------------------------------------------------
CREATE TABLE app.voucher (
  id              uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  zone_id         uuid NOT NULL,
  issuer_user_id  uuid NOT NULL REFERENCES app.app_user (id) ON DELETE RESTRICT,
  issuer_asset_id uuid NOT NULL,                   -- the shophouse
  code            text NOT NULL UNIQUE CHECK (code ~ '^[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$'),  -- random, unguessable
  value_vnd       bigint NOT NULL CHECK (value_vnd > 0),
  valid_until     timestamptz NOT NULL,
  status          app.voucher_status NOT NULL DEFAULT 'issued',
  redeemed_at     timestamptz,
  idempotency_key text NOT NULL UNIQUE,            -- a retried "create voucher" must not mint a second code
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (id, zone_id),
  FOREIGN KEY (issuer_asset_id, zone_id) REFERENCES app.asset (id, zone_id) ON DELETE RESTRICT,
  CHECK ((status = 'redeemed') = (redeemed_at IS NOT NULL))
);
CREATE INDEX voucher_issuer_idx ON app.voucher (issuer_user_id, created_at DESC);
CREATE INDEX voucher_asset_idx ON app.voucher (issuer_asset_id);

CREATE TABLE app.payment (
  id              uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  zone_id         uuid NOT NULL,
  booking_id      uuid NOT NULL,
  payer_user_id   uuid NOT NULL REFERENCES app.app_user (id) ON DELETE RESTRICT,
  kind            app.payment_kind NOT NULL,
  gross_vnd       bigint NOT NULL CHECK (gross_vnd >= 0),
  discount_vnd    bigint NOT NULL DEFAULT 0 CHECK (discount_vnd >= 0),
  amount_vnd      bigint GENERATED ALWAYS AS (gross_vnd - discount_vnd) STORED,
  -- charge: payer_user_id pays; refund: payer_user_id is the person refunded (D-09).
  direction       text GENERATED ALWAYS AS (CASE WHEN kind = 'early_return_refund' THEN 'refund' ELSE 'charge' END) STORED,
  voucher_id      uuid UNIQUE,                     -- a voucher is redeemed at most once
  provider        text NOT NULL DEFAULT 'vietqr_mock' CHECK (provider = 'vietqr_mock'),  -- A-05: no real money
  status          app.payment_status NOT NULL DEFAULT 'pending',
  idempotency_key text NOT NULL UNIQUE,
  paid_at         timestamptz,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (booking_id, zone_id) REFERENCES app.booking (id, zone_id) ON DELETE RESTRICT,
  FOREIGN KEY (voucher_id, zone_id) REFERENCES app.voucher (id, zone_id) ON DELETE RESTRICT,
  CHECK (discount_vnd <= gross_vnd),
  CHECK (voucher_id IS NOT NULL OR discount_vnd = 0),
  CHECK (voucher_id IS NULL OR kind = 'th3_visit'),                  -- AC-16: vouchers only for TH3 visits
  CHECK ((status = 'paid_simulated') = (paid_at IS NOT NULL))
);
CREATE INDEX payment_booking_idx ON app.payment (booking_id);
CREATE INDEX payment_payer_idx ON app.payment (payer_user_id, created_at DESC);
-- At most one successful payment per booking and kind.
CREATE UNIQUE INDEX payment_paid_uq ON app.payment (booking_id, kind) WHERE status = 'paid_simulated';

-- AC-16: a voucher pays only for a TH3 booking in the voucher's zone.
CREATE FUNCTION app.payment_validate_voucher() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.voucher_id IS NOT NULL AND NOT EXISTS (
       SELECT 1 FROM app.booking b JOIN app.slot s ON s.id = b.slot_id
       WHERE b.id = NEW.booking_id AND s.slot_type = 'TH3') THEN
    RAISE EXCEPTION 'AC-16: vouchers apply to TH3 visits only' USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER payment_validate_voucher BEFORE INSERT OR UPDATE OF voucher_id, booking_id
  ON app.payment FOR EACH ROW EXECUTE FUNCTION app.payment_validate_voucher();

-- -----------------------------------------------------------------------------------------------------
-- 13. Access (M8): LPR sources, events (partitioned), sessions, overstay, plate-view audit
-- -----------------------------------------------------------------------------------------------------
CREATE TABLE app.lpr_source (
  id          uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  zone_id     uuid NOT NULL REFERENCES app.zone (id) ON DELETE RESTRICT,
  kind        app.lpr_source_kind NOT NULL,
  name        text NOT NULL,
  -- Below this OCR confidence an event goes to manual review (BR-13). Threshold TBD → per source.
  ocr_review_threshold numeric(4,3) NOT NULL DEFAULT 0.800 CHECK (ocr_review_threshold BETWEEN 0 AND 1),
  is_active   boolean NOT NULL DEFAULT true,
  created_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (zone_id, name),
  UNIQUE (id, zone_id)
);

-- Largest table (see 04-queries-indexes.md §4): monthly range partitions on occurred_at for cheap retention
-- (DROP old partitions) and smaller indexes. Dedup key includes occurred_at because a partitioned unique
-- constraint must contain the partition key; vendor re-sends carry the same (event id, timestamp).
-- Explicit sequence: identity columns on partitioned tables need PG17.
CREATE SEQUENCE app.lpr_event_id_seq AS bigint;
CREATE TABLE app.lpr_event (
  id                 bigint NOT NULL DEFAULT nextval('app.lpr_event_id_seq'),
  zone_id            uuid NOT NULL,
  source_id          uuid NOT NULL,
  source_event_id    text NOT NULL CHECK (length(source_event_id) BETWEEN 1 AND 128),
  gate_id            uuid NOT NULL,
  direction          app.gate_direction NOT NULL,
  occurred_at        timestamptz NOT NULL,
  received_at        timestamptz NOT NULL DEFAULT now(),
  plate_ciphertext   bytea,                        -- NULL when OCR read nothing
  plate_hash         bytea CHECK (plate_hash IS NULL OR length(plate_hash) = 32),
  plate_masked       text,
  ocr_confidence     numeric(4,3) NOT NULL CHECK (ocr_confidence BETWEEN 0 AND 1),
  status             app.lpr_status NOT NULL,
  matched_vehicle_id uuid REFERENCES app.vehicle (id) ON DELETE SET NULL,
  matched_booking_id uuid REFERENCES app.booking (id) ON DELETE SET NULL,
  -- RESTRICT, not SET NULL: the CHECK below requires a reviewer for reviewed rows (check c).
  reviewed_by        uuid REFERENCES app.app_user (id) ON DELETE RESTRICT,
  reviewed_at        timestamptz,
  PRIMARY KEY (id, occurred_at),
  UNIQUE (source_id, source_event_id, occurred_at),                 -- BR-13 / AC-10a dedupe
  FOREIGN KEY (source_id, zone_id) REFERENCES app.lpr_source (id, zone_id) ON DELETE RESTRICT,
  FOREIGN KEY (gate_id, zone_id) REFERENCES app.gate (id, zone_id) ON DELETE RESTRICT,
  CHECK ((plate_ciphertext IS NULL) = (plate_hash IS NULL)),
  CHECK (status NOT IN ('confirmed_manual', 'unreadable') OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL))
) PARTITION BY RANGE (occurred_at);

CREATE INDEX lpr_event_zone_time_idx ON app.lpr_event (zone_id, occurred_at DESC);
CREATE INDEX lpr_event_review_idx ON app.lpr_event (zone_id, occurred_at) WHERE status = 'pending_review';
CREATE INDEX lpr_event_plate_idx ON app.lpr_event (plate_hash, occurred_at DESC) WHERE plate_hash IS NOT NULL;
CREATE INDEX lpr_event_booking_idx ON app.lpr_event (matched_booking_id) WHERE matched_booking_id IS NOT NULL;
CREATE INDEX lpr_event_vehicle_idx ON app.lpr_event (matched_vehicle_id) WHERE matched_vehicle_id IS NOT NULL;
ALTER SEQUENCE app.lpr_event_id_seq OWNED BY app.lpr_event.id;

-- Catch-all so an out-of-range timestamp never fails ingestion; monitor that it stays empty (07-operations).
CREATE TABLE app.lpr_event_default PARTITION OF app.lpr_event DEFAULT;

-- Creates monthly partitions from the current month to p_months_ahead. Run daily by a bg job (idempotent).
CREATE FUNCTION app.ensure_lpr_partitions(p_months_ahead integer DEFAULT 2) RETURNS void
LANGUAGE plpgsql AS $$
DECLARE
  v_start date := date_trunc('month', now() AT TIME ZONE 'UTC')::date;
  v_from  date;
  v_name  text;
BEGIN
  FOR i IN 0 .. p_months_ahead LOOP
    v_from := (v_start + make_interval(months => i))::date;
    v_name := format('lpr_event_%s', to_char(v_from, 'YYYYMM'));
    IF to_regclass(format('app.%I', v_name)) IS NULL THEN
      -- Bounds spelled with an explicit +00 offset so the session TimeZone cannot shift them.
      EXECUTE format('CREATE TABLE app.%I PARTITION OF app.lpr_event FOR VALUES FROM (%L) TO (%L)',
                     v_name, v_from::text || ' 00:00:00+00',
                     (v_from + interval '1 month')::date::text || ' 00:00:00+00');
    END IF;
  END LOOP;
END $$;
DO $$ BEGIN PERFORM app.ensure_lpr_partitions(2); END $$;

-- A visit: entry/exit pair derived by N1. Event ids are kept without FK (partitioned parent, high churn).
CREATE TABLE app.parking_session (
  id             uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  zone_id        uuid NOT NULL REFERENCES app.zone (id) ON DELETE RESTRICT,
  booking_id     uuid REFERENCES app.booking (id) ON DELETE RESTRICT,
  vehicle_id     uuid REFERENCES app.vehicle (id) ON DELETE RESTRICT,
  entry_event_id bigint NOT NULL,
  exit_event_id  bigint,
  entered_at     timestamptz NOT NULL,
  exited_at      timestamptz,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  UNIQUE (zone_id, entry_event_id),
  CHECK ((exit_event_id IS NULL) = (exited_at IS NULL)),
  CHECK (exited_at IS NULL OR exited_at >= entered_at)
);
CREATE INDEX parking_session_open_idx ON app.parking_session (zone_id, vehicle_id) WHERE exited_at IS NULL;
CREATE INDEX parking_session_booking_idx ON app.parking_session (booking_id) WHERE booking_id IS NOT NULL;
CREATE INDEX parking_session_vehicle_idx ON app.parking_session (vehicle_id, entered_at DESC);

CREATE TABLE app.overstay_case (
  id                uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  zone_id           uuid NOT NULL,
  booking_id        uuid NOT NULL UNIQUE,          -- one case per booking: N2 can re-run safely
  detected_at       timestamptz NOT NULL,
  reminder_count    smallint NOT NULL DEFAULT 0 CHECK (reminder_count >= 0),
  last_reminded_at  timestamptz,
  ended_at          timestamptz,
  overstay_minutes  integer CHECK (overstay_minutes >= 0),
  fee_vnd           bigint CHECK (fee_vnd >= 0),
  status            app.overstay_status NOT NULL DEFAULT 'open',
  created_at        timestamptz NOT NULL DEFAULT now(),
  updated_at        timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (booking_id, zone_id) REFERENCES app.booking (id, zone_id) ON DELETE RESTRICT,
  CHECK (status <> 'charged' OR fee_vnd IS NOT NULL)
);
CREATE INDEX overstay_case_open_idx ON app.overstay_case (zone_id, detected_at) WHERE status = 'open';

-- Every view of an original plate (US-13, AC-12). Insert-only through app.reveal_* functions.
CREATE TABLE app.plate_access_log (
  id             bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  zone_id        uuid REFERENCES app.zone (id) ON DELETE RESTRICT,     -- NULL for owner viewing own vehicle
  viewer_user_id uuid NOT NULL REFERENCES app.app_user (id) ON DELETE RESTRICT,
  subject_type   text NOT NULL CHECK (subject_type IN ('lpr_event', 'vehicle', 'dispute_evidence')),
  subject_ref    text NOT NULL,
  reason         text NOT NULL CHECK (length(btrim(reason)) >= 5),
  viewed_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX plate_access_log_zone_idx ON app.plate_access_log (zone_id, viewed_at DESC);
CREATE INDEX plate_access_log_viewer_idx ON app.plate_access_log (viewer_user_id);
CREATE TRIGGER plate_access_log_append_only BEFORE UPDATE OR DELETE OR TRUNCATE ON app.plate_access_log
  FOR EACH STATEMENT EXECUTE FUNCTION app.reject_mutation('purgeable');

-- Only a BQL of the event's zone may read an original plate; the read is logged in the same transaction.
CREATE FUNCTION app.reveal_lpr_plate(p_event_id bigint, p_occurred_at timestamptz, p_reason text)
RETURNS bytea LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, app AS $$
DECLARE
  v_zone uuid;
  v_ct   bytea;
BEGIN
  SELECT e.zone_id, e.plate_ciphertext INTO v_zone, v_ct
  FROM app.lpr_event e WHERE e.id = p_event_id AND e.occurred_at = p_occurred_at;
  IF v_zone IS NULL OR NOT app.is_zone_staff(v_zone, '{zone_manager}') THEN
    RAISE EXCEPTION 'not allowed' USING ERRCODE = 'insufficient_privilege';
  END IF;
  INSERT INTO app.plate_access_log (zone_id, viewer_user_id, subject_type, subject_ref, reason)
  VALUES (v_zone, app.ctx_user_id(), 'lpr_event', p_event_id::text, p_reason);
  RETURN v_ct;
END $$;

-- Owner reads their own plate; a BQL may read it only when the vehicle has a booking in their zone.
CREATE FUNCTION app.reveal_vehicle_plate(p_vehicle_id uuid, p_reason text)
RETURNS bytea LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, app AS $$
DECLARE
  v_owner uuid;
  v_ct    bytea;
  v_zone  uuid;
BEGIN
  SELECT v.user_id, v.plate_ciphertext INTO v_owner, v_ct FROM app.vehicle v WHERE v.id = p_vehicle_id;
  IF v_owner IS NULL THEN
    RAISE EXCEPTION 'not allowed' USING ERRCODE = 'insufficient_privilege';
  END IF;
  IF v_owner IS DISTINCT FROM app.ctx_user_id() THEN
    SELECT b.zone_id INTO v_zone FROM app.booking b
    WHERE b.vehicle_id = p_vehicle_id AND app.is_zone_staff(b.zone_id, '{zone_manager}') LIMIT 1;
    IF v_zone IS NULL THEN
      RAISE EXCEPTION 'not allowed' USING ERRCODE = 'insufficient_privilege';
    END IF;
  END IF;
  INSERT INTO app.plate_access_log (zone_id, viewer_user_id, subject_type, subject_ref, reason)
  VALUES (v_zone, app.ctx_user_id(), 'vehicle', p_vehicle_id::text, p_reason);
  RETURN v_ct;
END $$;

-- -----------------------------------------------------------------------------------------------------
-- 14. Disputes (M10)
-- -----------------------------------------------------------------------------------------------------
CREATE TABLE app.dispute_category (
  code     text PRIMARY KEY CHECK (code ~ '^[a-z_]{2,40}$'),
  label_vi text NOT NULL
);

CREATE TABLE app.dispute_ticket (
  id               uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  ref_no           bigint GENERATED ALWAYS AS IDENTITY UNIQUE,   -- shown as TC-0031
  zone_id          uuid NOT NULL,                  -- zone of the slot (BR-18)
  slot_id          uuid NOT NULL,
  booking_id       uuid,
  source           app.dispute_source NOT NULL,
  category_code    text NOT NULL REFERENCES app.dispute_category (code) ON DELETE RESTRICT,
  description      text,
  status           app.dispute_status NOT NULL DEFAULT 'open',
  ai_summary       text,                           -- pseudonymised suggestion, never a verdict (BR-14)
  ai_confidence    numeric(4,3) CHECK (ai_confidence BETWEEN 0 AND 1),
  resolution_code  text,
  resolution_note  text,
  resolved_by      uuid REFERENCES app.app_user (id) ON DELETE RESTRICT,
  resolved_at      timestamptz,
  idempotency_key  text NOT NULL UNIQUE,
  created_at       timestamptz NOT NULL DEFAULT now(),
  updated_at       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (id, zone_id),
  FOREIGN KEY (slot_id, zone_id) REFERENCES app.slot (id, zone_id) ON DELETE RESTRICT,
  FOREIGN KEY (booking_id, zone_id) REFERENCES app.booking (id, zone_id) ON DELETE RESTRICT,
  CHECK ((status IN ('resolved', 'dismissed')) = (resolved_by IS NOT NULL AND resolved_at IS NOT NULL))
);
CREATE INDEX dispute_ticket_queue_idx ON app.dispute_ticket (zone_id, status, created_at DESC);
CREATE INDEX dispute_ticket_slot_idx ON app.dispute_ticket (slot_id, created_at DESC);          -- N5 repeat detection
CREATE INDEX dispute_ticket_booking_idx ON app.dispute_ticket (booking_id) WHERE booking_id IS NOT NULL;

-- zone_id is carried so RLS on this table does not need to query dispute_ticket (which would recurse
-- through dispute_ticket's party policy).
CREATE TABLE app.dispute_party (
  ticket_id uuid NOT NULL,
  zone_id   uuid NOT NULL,
  user_id   uuid NOT NULL REFERENCES app.app_user (id) ON DELETE RESTRICT,
  role      text NOT NULL CHECK (role IN ('reporter', 'respondent')),
  PRIMARY KEY (ticket_id, user_id),
  FOREIGN KEY (ticket_id, zone_id) REFERENCES app.dispute_ticket (id, zone_id) ON DELETE CASCADE
);
CREATE INDEX dispute_party_user_idx ON app.dispute_party (user_id);

-- Photos live in S3; the DB keeps keys and hashes only. The unmasked key is column-restricted like plates.
CREATE TABLE app.dispute_evidence (
  id                  uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  zone_id             uuid NOT NULL,
  ticket_id           uuid NOT NULL,
  kind                app.evidence_kind NOT NULL,
  object_key_original text,
  object_key_masked   text,
  sha256              bytea CHECK (sha256 IS NULL OR length(sha256) = 32),
  lpr_event_id        bigint,
  lpr_occurred_at     timestamptz,
  ledger_seq          bigint,
  -- Copy of the LPR event (gate, direction, time, masked plate, OCR) so evidence survives the 90-day drop of
  -- lpr_event partitions (D-05). Never contains the plate ciphertext.
  snapshot            jsonb CHECK (snapshot IS NULL OR jsonb_typeof(snapshot) = 'object'),
  created_at          timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (ticket_id, zone_id) REFERENCES app.dispute_ticket (id, zone_id) ON DELETE CASCADE,
  FOREIGN KEY (zone_id, ledger_seq) REFERENCES app.ledger_entry (zone_id, seq) ON DELETE RESTRICT,
  CHECK (
       (kind = 'photo'        AND object_key_original IS NOT NULL AND object_key_masked IS NOT NULL AND sha256 IS NOT NULL)
    OR (kind = 'lpr_event'    AND lpr_event_id IS NOT NULL AND lpr_occurred_at IS NOT NULL AND snapshot IS NOT NULL)
    OR (kind = 'ledger_entry' AND ledger_seq IS NOT NULL))
);
CREATE INDEX dispute_evidence_ticket_idx ON app.dispute_evidence (ticket_id);
-- Idempotency of W5 evidence collection (check d): the same item is attached once per ticket.
CREATE UNIQUE INDEX dispute_evidence_photo_uq  ON app.dispute_evidence (ticket_id, sha256)       WHERE kind = 'photo';
CREATE UNIQUE INDEX dispute_evidence_lpr_uq    ON app.dispute_evidence (ticket_id, lpr_event_id) WHERE kind = 'lpr_event';
CREATE UNIQUE INDEX dispute_evidence_ledger_uq ON app.dispute_evidence (ticket_id, ledger_seq)   WHERE kind = 'ledger_entry';

-- -----------------------------------------------------------------------------------------------------
-- 15. Swaps (M11): same zone only (BR-10), effective after BQL approval (FR-18)
-- -----------------------------------------------------------------------------------------------------
CREATE TABLE app.swap_need (
  id                    uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  zone_id               uuid NOT NULL,
  user_id               uuid NOT NULL REFERENCES app.app_user (id) ON DELETE RESTRICT,
  current_slot_id       uuid NOT NULL,
  desired_size_class    text REFERENCES app.size_class (code) ON DELETE RESTRICT,
  note                  text,
  status                app.need_status NOT NULL DEFAULT 'open',
  created_at            timestamptz NOT NULL DEFAULT now(),
  updated_at            timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (current_slot_id, zone_id) REFERENCES app.slot (id, zone_id) ON DELETE RESTRICT
);
CREATE UNIQUE INDEX swap_need_open_uq ON app.swap_need (user_id, current_slot_id) WHERE status = 'open';
CREATE INDEX swap_need_zone_idx ON app.swap_need (zone_id) WHERE status = 'open';

CREATE TABLE app.swap_proposal (
  id                  uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  ref_no              bigint GENERATED ALWAYS AS IDENTITY UNIQUE,   -- shown as HD-007
  zone_id             uuid NOT NULL REFERENCES app.zone (id) ON DELETE RESTRICT,
  kind                app.swap_kind NOT NULL,
  status              app.swap_status NOT NULL DEFAULT 'pending_approval',
  reason              text NOT NULL,
  score               numeric(6,3),
  approval_request_id uuid,
  effective_from      timestamptz,
  applied_at          timestamptz,
  idempotency_key     text NOT NULL UNIQUE,
  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now(),
  UNIQUE (id, zone_id),
  FOREIGN KEY (approval_request_id, zone_id) REFERENCES app.approval_request (id, zone_id) ON DELETE RESTRICT,
  CHECK (status NOT IN ('approved', 'applied') OR approval_request_id IS NOT NULL),
  CHECK ((status = 'applied') = (applied_at IS NOT NULL))
);
CREATE INDEX swap_proposal_zone_idx ON app.swap_proposal (zone_id, status, created_at DESC);
CREATE INDEX swap_proposal_approval_idx ON app.swap_proposal (approval_request_id) WHERE approval_request_id IS NOT NULL;

-- One leg = one slot changing usage holder. zone_id is shared with the proposal, so every slot is in the
-- proposal's zone (BR-10) by FK alone.
CREATE TABLE app.swap_leg (
  proposal_id  uuid NOT NULL,
  zone_id      uuid NOT NULL,
  slot_id      uuid NOT NULL,
  from_user_id uuid NOT NULL REFERENCES app.app_user (id) ON DELETE RESTRICT,
  to_user_id   uuid NOT NULL REFERENCES app.app_user (id) ON DELETE RESTRICT,
  ordinal      smallint NOT NULL CHECK (ordinal >= 1),
  accepted_at  timestamptz,                        -- from_user's consent (D-10)
  PRIMARY KEY (proposal_id, slot_id),
  UNIQUE (proposal_id, ordinal),
  FOREIGN KEY (proposal_id, zone_id) REFERENCES app.swap_proposal (id, zone_id) ON DELETE CASCADE,
  FOREIGN KEY (slot_id, zone_id) REFERENCES app.slot (id, zone_id) ON DELETE RESTRICT,
  CHECK (from_user_id <> to_user_id)
);
CREATE INDEX swap_leg_slot_idx ON app.swap_leg (slot_id);
CREATE INDEX swap_leg_from_idx ON app.swap_leg (from_user_id);
CREATE INDEX swap_leg_to_idx ON app.swap_leg (to_user_id);

-- D-10: when the zone policy requires it, every party must accept before BQL approval or application.
CREATE FUNCTION app.swap_proposal_validate() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.status IN ('approved', 'applied')
     AND coalesce((app.current_zone_policy(NEW.zone_id)).swap_requires_party_consent, true)
     AND EXISTS (SELECT 1 FROM app.swap_leg l WHERE l.proposal_id = NEW.id AND l.accepted_at IS NULL) THEN
    RAISE EXCEPTION 'D-10: every swap party must accept before approval' USING ERRCODE = 'check_violation';
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER swap_proposal_validate BEFORE INSERT OR UPDATE OF status ON app.swap_proposal
  FOR EACH ROW EXECUTE FUNCTION app.swap_proposal_validate();

ALTER TABLE app.slot_holding
  ADD CONSTRAINT slot_holding_swap_fk FOREIGN KEY (swap_proposal_id) REFERENCES app.swap_proposal (id) ON DELETE RESTRICT;
CREATE INDEX slot_holding_swap_idx ON app.slot_holding (swap_proposal_id) WHERE swap_proposal_id IS NOT NULL;

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
  idempotency_key text NOT NULL UNIQUE,            -- outbox event id: relay retries do not duplicate
  read_at         timestamptz,
  created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX notification_inbox_idx ON app.notification (user_id, created_at DESC, id DESC);
CREATE INDEX notification_unread_idx ON app.notification (user_id) WHERE read_at IS NULL;

-- -----------------------------------------------------------------------------------------------------
-- 17. Reporting (M12, N3, N4, N7)
-- -----------------------------------------------------------------------------------------------------
CREATE TABLE app.vacancy_forecast (
  slot_id      uuid NOT NULL,
  zone_id      uuid NOT NULL,
  day_kind     app.day_kind NOT NULL,
  hour_of_day  smallint NOT NULL CHECK (hour_of_day BETWEEN 0 AND 23),
  p_vacant     numeric(4,3) NOT NULL CHECK (p_vacant BETWEEN 0 AND 1),
  sample_days  integer NOT NULL CHECK (sample_days >= 0),
  computed_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (slot_id, day_kind, hour_of_day),
  FOREIGN KEY (slot_id, zone_id) REFERENCES app.slot (id, zone_id) ON DELETE CASCADE
);
CREATE INDEX vacancy_forecast_zone_idx ON app.vacancy_forecast (zone_id);

-- Aggregates only (no personal data) — the only data a chain operator reads (PRD §9).
CREATE TABLE app.kpi_daily (
  zone_id     uuid NOT NULL REFERENCES app.zone (id) ON DELETE RESTRICT,
  day         date NOT NULL,                       -- local date in zone.timezone
  metric      text NOT NULL CHECK (metric IN (
                 'extra_slot_hours', 'match_rate', 'cross_zone_fulfilment_rate', 'owner_return_conflicts',
                 'dispute_filing_minutes_p50', 'blocked_ineligible_tx', 'repeat_dispute_rate_after_swap')),
  value       numeric NOT NULL,
  computed_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (zone_id, day, metric)
);
CREATE INDEX kpi_daily_day_idx ON app.kpi_daily (day, metric);

CREATE TABLE app.reconciliation_report (
  id          uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  zone_id     uuid NOT NULL REFERENCES app.zone (id) ON DELETE RESTRICT,
  day         date NOT NULL,
  -- Report document (counts, mismatches with ids). jsonb because its shape evolves with N3, it is read whole
  -- and never filtered on inner keys.
  summary     jsonb NOT NULL CHECK (jsonb_typeof(summary) = 'object'),
  created_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (zone_id, day)
);

-- -----------------------------------------------------------------------------------------------------
-- 18. Platform: outbox, idempotency, workflow runs, audit log (ADR-0005, ADR-0010)
-- -----------------------------------------------------------------------------------------------------
CREATE TABLE app.outbox (
  id           bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  event_type   text NOT NULL CHECK (event_type ~ '^[A-Za-z][A-Za-z0-9_.]{1,80}$'),
  zone_id      uuid REFERENCES app.zone (id) ON DELETE RESTRICT,
  payload      jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),     -- ids only, no PII
  traceparent  text,
  attempts     integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  last_error   text,
  created_at   timestamptz NOT NULL DEFAULT now(),
  published_at timestamptz
);
-- Relay: SELECT … WHERE published_at IS NULL ORDER BY id FOR UPDATE SKIP LOCKED LIMIT n.
CREATE INDEX outbox_unpublished_idx ON app.outbox (id) WHERE published_at IS NULL;
CREATE INDEX outbox_published_idx ON app.outbox (published_at) WHERE published_at IS NOT NULL;  -- purge

CREATE TABLE app.idempotency_keys (
  key        text PRIMARY KEY CHECK (length(key) BETWEEN 1 AND 200),   -- thread_id:step or source:event_id
  result     jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idempotency_keys_created_idx ON app.idempotency_keys (created_at);   -- TTL purge

CREATE TABLE app.workflow_run (
  thread_id         text PRIMARY KEY,
  workflow          app.workflow_code NOT NULL,
  zone_id           uuid REFERENCES app.zone (id) ON DELETE RESTRICT,   -- zone of the slot, NULL before routing
  initiator_user_id uuid REFERENCES app.app_user (id) ON DELETE SET NULL,
  status            app.workflow_status NOT NULL DEFAULT 'running',
  started_at        timestamptz NOT NULL DEFAULT now(),
  finished_at       timestamptz,
  updated_at        timestamptz NOT NULL DEFAULT now(),
  CHECK ((status IN ('completed', 'failed', 'cancelled')) = (finished_at IS NOT NULL))
);
CREATE INDEX workflow_run_initiator_idx ON app.workflow_run (initiator_user_id, started_at DESC);
CREATE INDEX workflow_run_zone_idx ON app.workflow_run (zone_id, status);

-- Who changed configuration, eligibility, approvals. Written by trigger only.
CREATE TABLE app.audit_log (
  id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  zone_id       uuid,
  actor_user_id uuid,
  actor_role    text NOT NULL,
  table_name    text NOT NULL,
  row_id        text NOT NULL,
  action        text NOT NULL CHECK (action IN ('INSERT', 'UPDATE', 'DELETE')),
  old_row       jsonb,
  new_row       jsonb,
  at            timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX audit_log_zone_idx ON app.audit_log (zone_id, at DESC);
CREATE INDEX audit_log_row_idx ON app.audit_log (table_name, row_id);
CREATE TRIGGER audit_log_append_only BEFORE UPDATE OR DELETE OR TRUNCATE ON app.audit_log
  FOR EACH STATEMENT EXECUTE FUNCTION app.reject_mutation('purgeable');

CREATE FUNCTION app.audit_row() RETURNS trigger
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, app AS $$
DECLARE
  v_row jsonb := to_jsonb(coalesce(NEW, OLD));
BEGIN
  INSERT INTO app.audit_log (zone_id, actor_user_id, actor_role, table_name, row_id, action, old_row, new_row)
  VALUES ((v_row ->> 'zone_id')::uuid, app.ctx_user_id(), app.ctx_role(), TG_TABLE_NAME,
          coalesce(v_row ->> 'id', concat_ws(':', v_row ->> 'user_id', v_row ->> 'zone_id')), TG_OP,
          CASE WHEN TG_OP <> 'INSERT' THEN to_jsonb(OLD) END,
          CASE WHEN TG_OP <> 'DELETE' THEN to_jsonb(NEW) END);
  RETURN NULL;
END $$;

DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['slot_pool', 'zone_policy', 'price_rule', 'agreement_template', 'eligibility',
                           'slot_holding', 'approval_request', 'staff_zone'] LOOP
    EXECUTE format('CREATE TRIGGER %I AFTER INSERT OR UPDATE OR DELETE ON app.%I
                    FOR EACH ROW EXECUTE FUNCTION app.audit_row()', t || '_audit', t);
  END LOOP;
END $$;

-- updated_at maintenance
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['chain', 'zone', 'subzone', 'building', 'slot_pool', 'slot', 'app_user', 'vehicle',
                           'asset', 'eligibility', 'approval_request', 'share_window', 'booking', 'agreement',
                           'voucher', 'payment', 'parking_session', 'overstay_case', 'dispute_ticket',
                           'swap_need', 'swap_proposal', 'workflow_run'] LOOP
    EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE ON app.%I
                    FOR EACH ROW EXECUTE FUNCTION app.set_updated_at()', t || '_updated_at', t);
  END LOOP;
END $$;

-- -----------------------------------------------------------------------------------------------------
-- 18b. Privacy & retention (D-05, D-06, D-14, D-15; PDPL 91/2025/QH15 + Decree 356/2025/ND-CP)
-- -----------------------------------------------------------------------------------------------------
-- Hourly occupancy per slot, derived from LPR sessions by N4 before raw events expire. No plate, no person:
-- the forecast (FR-20) keeps years of history without keeping LPR data longer than 90 days.
CREATE TABLE app.occupancy_hourly (
  slot_id          uuid NOT NULL,
  zone_id          uuid NOT NULL,
  hour_start       timestamptz NOT NULL CHECK (date_trunc('hour', hour_start) = hour_start),
  occupied_minutes smallint NOT NULL CHECK (occupied_minutes BETWEEN 0 AND 60),
  PRIMARY KEY (slot_id, hour_start),
  FOREIGN KEY (slot_id, zone_id) REFERENCES app.slot (id, zone_id) ON DELETE CASCADE
);
CREATE INDEX occupancy_hourly_zone_idx ON app.occupancy_hourly (zone_id, hour_start);

-- Data-subject requests and their legal deadlines (Decree 356/2025 Art. 5: acknowledge in 2 working days,
-- delete in 20 days / 30 with a processor, withdraw consent in 15 days). Kept 5 years as proof (D-15).
CREATE TABLE app.privacy_request (
  id              uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  user_id         uuid NOT NULL REFERENCES app.app_user (id) ON DELETE RESTRICT,
  kind            app.privacy_request_kind NOT NULL,
  status          app.privacy_request_status NOT NULL DEFAULT 'received',
  received_at     timestamptz NOT NULL DEFAULT now(),
  acknowledged_at timestamptz,
  due_at          timestamptz NOT NULL,            -- set by the app from the kind (see 07-operations §3)
  completed_at    timestamptz,
  handled_by      uuid REFERENCES app.app_user (id) ON DELETE RESTRICT,
  note            text,
  CHECK (due_at > received_at AND due_at <= received_at + interval '60 days'),
  CHECK ((status IN ('completed', 'rejected')) = (completed_at IS NOT NULL)),
  CHECK (status = 'received' OR acknowledged_at IS NOT NULL)
);
CREATE UNIQUE INDEX privacy_request_open_uq ON app.privacy_request (user_id, kind) WHERE status IN ('received', 'acknowledged');
CREATE INDEX privacy_request_due_idx ON app.privacy_request (due_at) WHERE status IN ('received', 'acknowledged');

-- Retention per data class (D-05/D-06). Changing a period is a data change, not a migration.
CREATE TABLE app.retention_rule (
  data_class  text PRIMARY KEY CHECK (data_class ~ '^[a-z_]{3,40}$'),
  keep        interval NOT NULL CHECK (keep > interval '0'),
  basis       text NOT NULL,                       -- legal/business reason, cited in 10-decision-log.md
  enforced_by text NOT NULL                        -- function / job / S3 lifecycle doing the purge
);
INSERT INTO app.retention_rule (data_class, keep, basis, enforced_by) VALUES
  ('lpr_event',          '90 days',   'D-05: raw plate reads = location trail; minimisation (PDPL); forecasts use occupancy_hourly', 'app.drop_expired_lpr_partitions'),
  ('parking_session',    '180 days',  'D-05: needed for overstay/N3 claims; then only occupancy_hourly remains', 'app.purge_expired'),
  ('occupancy_hourly',   '3 years',   'D-05: no personal data; covers 3 Tết seasons for N4', 'app.purge_expired'),
  ('dispute_photo',      '1 year',    'D-05: after ticket closure; masked + original objects in S3', 'S3 lifecycle + app.purge_expired (keys)'),
  ('plate_access_log',   '5 years',   'D-06: proof of lawful access; Decree 356 records ≥ 5 years', 'app.purge_expired'),
  ('audit_log',          '5 years',   'D-06: processing records; Decree 356 records ≥ 5 years', 'app.purge_expired'),
  ('privacy_request',    '5 years',   'D-15: proof of handling data-subject requests', 'app.purge_expired'),
  ('ledger_and_money',   '10 years',  'D-06: accounting documents (Law on Accounting 88/2015, Decree 174/2016 Art. 13); ids only, never purged by job', 'manual archive'),
  ('notification',       '180 days',  'D-06: convenience data', 'app.purge_expired'),
  ('outbox_published',   '7 days',    'D-06: replay window for the relay', 'app.purge_expired'),
  ('idempotency_keys',   '30 days',   'D-06: longer than any workflow retry / HITL wait', 'app.purge_expired'),
  ('auth_secret',        '30 days',   'D-06: expired refresh/reset tokens and OTPs', 'app.purge_expired'),
  ('agent_checkpoint',   '30 days',   'D-12: finished LangGraph threads', 'app.purge_agent_checkpoints');

-- Deletes rows past their retention_rule. Run daily by the owner job (not the app role). Returns counts.
CREATE FUNCTION app.purge_expired(p_now timestamptz DEFAULT now())
RETURNS TABLE (data_class text, deleted bigint)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, app AS $$
DECLARE
  k   interval;
  n   bigint;
BEGIN
  PERFORM set_config('parksmart.retention_purge', 'on', true);

  SELECT r.keep INTO k FROM app.retention_rule r WHERE r.data_class = 'notification';
  DELETE FROM app.notification x WHERE x.created_at < p_now - k;                    GET DIAGNOSTICS n = ROW_COUNT;
  data_class := 'notification'; deleted := n; RETURN NEXT;

  SELECT r.keep INTO k FROM app.retention_rule r WHERE r.data_class = 'outbox_published';
  DELETE FROM app.outbox x WHERE x.published_at < p_now - k;                        GET DIAGNOSTICS n = ROW_COUNT;
  data_class := 'outbox_published'; deleted := n; RETURN NEXT;

  SELECT r.keep INTO k FROM app.retention_rule r WHERE r.data_class = 'idempotency_keys';
  DELETE FROM app.idempotency_keys x WHERE x.created_at < p_now - k;                GET DIAGNOSTICS n = ROW_COUNT;
  data_class := 'idempotency_keys'; deleted := n; RETURN NEXT;

  SELECT r.keep INTO k FROM app.retention_rule r WHERE r.data_class = 'auth_secret';
  DELETE FROM app.refresh_token x WHERE x.expires_at < p_now - k;                   GET DIAGNOSTICS n = ROW_COUNT;
  DELETE FROM app.password_reset_token x WHERE x.expires_at < p_now - k;
  DELETE FROM app.otp_challenge x WHERE x.expires_at < p_now - k;
  data_class := 'auth_secret'; deleted := n; RETURN NEXT;

  SELECT r.keep INTO k FROM app.retention_rule r WHERE r.data_class = 'parking_session';
  DELETE FROM app.parking_session x WHERE coalesce(x.exited_at, x.entered_at) < p_now - k;  GET DIAGNOSTICS n = ROW_COUNT;
  data_class := 'parking_session'; deleted := n; RETURN NEXT;

  SELECT r.keep INTO k FROM app.retention_rule r WHERE r.data_class = 'occupancy_hourly';
  DELETE FROM app.occupancy_hourly x WHERE x.hour_start < p_now - k;                GET DIAGNOSTICS n = ROW_COUNT;
  data_class := 'occupancy_hourly'; deleted := n; RETURN NEXT;

  -- Photo keys of tickets closed longer than the photo retention (S3 lifecycle deletes the objects).
  SELECT r.keep INTO k FROM app.retention_rule r WHERE r.data_class = 'dispute_photo';
  DELETE FROM app.dispute_evidence e USING app.dispute_ticket t
   WHERE e.ticket_id = t.id AND e.kind = 'photo' AND t.resolved_at < p_now - k;     GET DIAGNOSTICS n = ROW_COUNT;
  data_class := 'dispute_photo'; deleted := n; RETURN NEXT;

  SELECT r.keep INTO k FROM app.retention_rule r WHERE r.data_class = 'plate_access_log';
  DELETE FROM app.plate_access_log x WHERE x.viewed_at < p_now - k;                 GET DIAGNOSTICS n = ROW_COUNT;
  data_class := 'plate_access_log'; deleted := n; RETURN NEXT;

  SELECT r.keep INTO k FROM app.retention_rule r WHERE r.data_class = 'audit_log';
  DELETE FROM app.audit_log x WHERE x.at < p_now - k;                               GET DIAGNOSTICS n = ROW_COUNT;
  data_class := 'audit_log'; deleted := n; RETURN NEXT;

  SELECT r.keep INTO k FROM app.retention_rule r WHERE r.data_class = 'privacy_request';
  DELETE FROM app.privacy_request x WHERE x.completed_at < p_now - k;               GET DIAGNOSTICS n = ROW_COUNT;
  data_class := 'privacy_request'; deleted := n; RETURN NEXT;

  PERFORM set_config('parksmart.retention_purge', 'off', true);
END $$;

-- Drops whole monthly lpr_event partitions whose newest possible row is older than the retention (D-05).
-- Evidence needed by disputes was copied into dispute_evidence.snapshot when the ticket was built.
CREATE FUNCTION app.drop_expired_lpr_partitions(p_now timestamptz DEFAULT now())
RETURNS SETOF text LANGUAGE plpgsql AS $$
DECLARE
  k    interval;
  r    record;
  hi   timestamptz;
  name text;
BEGIN
  SELECT keep INTO k FROM app.retention_rule WHERE data_class = 'lpr_event';
  FOR r IN SELECT c.oid::regclass AS part, pg_get_expr(c.relpartbound, c.oid) AS bound
           FROM pg_inherits i JOIN pg_class c ON c.oid = i.inhrelid
           WHERE i.inhparent = 'app.lpr_event'::regclass LOOP
    CONTINUE WHEN r.bound = 'DEFAULT';
    hi := substring(r.bound FROM 'TO \(''([^'']+)''\)')::timestamptz;
    IF hi <= p_now - k THEN
      name := r.part::text;                -- capture before DROP: a dropped regclass prints as a bare OID
      EXECUTE format('DROP TABLE %s', name);
      RETURN NEXT name;
    END IF;
  END LOOP;
END $$;

-- Right to erasure (D-14): scrubs personal data, keeps ids so the ledger (ids only, immutable) stays valid.
-- Must finish within the request deadline (Decree 356/2025 Art. 5: 20 days, 30 with a processor).
CREATE FUNCTION app.erase_user(p_user uuid, p_request uuid)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, app AS $$
BEGIN
  IF app.ctx_role() <> 'system' THEN
    RAISE EXCEPTION 'erase_user runs only as a system job' USING ERRCODE = 'insufficient_privilege';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM app.privacy_request r
                 WHERE r.id = p_request AND r.user_id = p_user AND r.kind = 'delete'
                   AND r.status IN ('received', 'acknowledged')) THEN
    RAISE EXCEPTION 'no open delete request % for user %', p_request, p_user USING ERRCODE = 'check_violation';
  END IF;
  -- Refuse while the person still has live obligations (running bookings, open disputes): finish them first.
  IF EXISTS (SELECT 1 FROM app.booking b WHERE (b.renter_user_id = p_user OR b.provider_user_id = p_user)
               AND b.status IN ('held', 'pending_agreement', 'pending_approval', 'confirmed')) THEN
    RAISE EXCEPTION 'user % has live bookings; cancel or complete them first', p_user USING ERRCODE = 'check_violation';
  END IF;

  UPDATE app.app_user SET full_name = '[đã xóa]', phone_e164 = NULL, email = NULL,
         password_hash = '$argon2id$erased', status = 'deleted', deleted_at = now()
   WHERE id = p_user;
  UPDATE app.vehicle SET plate_ciphertext = NULL, plate_hash = NULL, plate_masked = '[đã xóa]', is_active = false
   WHERE user_id = p_user;
  UPDATE app.consent SET withdrawn_at = now() WHERE user_id = p_user AND withdrawn_at IS NULL;
  DELETE FROM app.refresh_token WHERE user_id = p_user;
  DELETE FROM app.password_reset_token WHERE user_id = p_user;
  DELETE FROM app.otp_challenge WHERE user_id = p_user;
  DELETE FROM app.notification WHERE user_id = p_user;
  UPDATE app.swap_need SET note = NULL WHERE user_id = p_user;
  UPDATE app.dispute_ticket t SET description = NULL
   WHERE EXISTS (SELECT 1 FROM app.dispute_party p WHERE p.ticket_id = t.id AND p.user_id = p_user AND p.role = 'reporter');
  UPDATE app.privacy_request SET status = 'completed', completed_at = now(),
         acknowledged_at = coalesce(acknowledged_at, now())
   WHERE id = p_request;
END $$;

-- -----------------------------------------------------------------------------------------------------
-- 18c. Agent schema (LangGraph checkpointer) — check b, D-12
-- -----------------------------------------------------------------------------------------------------
-- The saver creates its own tables (checkpoints, checkpoint_blobs, checkpoint_writes, checkpoint_migrations,
-- all keyed by thread_id) as parksmart_checkpointer. They hold serialized graph state, which RLS cannot inspect.
-- Protection is therefore (1) isolation: the app role has no access to schema agent and the checkpointer role
-- has no access to schema app; (2) content rule: state carries ids, pseudonyms and pseudonymised text only —
-- the pseudonym map is not persisted in clear (encrypted serializer, see 07-operations §3); (3) retention:
-- finished threads are purged after retention_rule 'agent_checkpoint'.
REVOKE ALL ON SCHEMA agent FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE parksmart_checkpointer IN SCHEMA agent
  GRANT SELECT, DELETE ON TABLES TO parksmart_owner;

CREATE FUNCTION app.purge_agent_checkpoints(p_now timestamptz DEFAULT now())
RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, app AS $$
DECLARE
  k     interval;
  t     text;
  n     bigint := 0;
  m     bigint;
BEGIN
  SELECT keep INTO k FROM app.retention_rule WHERE data_class = 'agent_checkpoint';
  FOREACH t IN ARRAY ARRAY['checkpoint_writes', 'checkpoint_blobs', 'checkpoints'] LOOP
    CONTINUE WHEN to_regclass('agent.' || t) IS NULL;      -- tables appear once the saver ran setup()
    EXECUTE format('DELETE FROM agent.%I c WHERE c.thread_id IN (
                      SELECT w.thread_id FROM app.workflow_run w
                      WHERE w.status IN (''completed'', ''failed'', ''cancelled'') AND w.finished_at < $1)', t)
      USING p_now - k;
    GET DIAGNOSTICS m = ROW_COUNT;
    n := n + m;
  END LOOP;
  RETURN n;
END $$;

-- -----------------------------------------------------------------------------------------------------
-- 19. Knowledge base for W7 (RAG over zone/building rules). pgvector required in every real environment.
-- -----------------------------------------------------------------------------------------------------
CREATE TABLE app.knowledge_doc (
  id          uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  zone_id     uuid REFERENCES app.zone (id) ON DELETE RESTRICT,           -- NULL = chain-wide
  building_id uuid REFERENCES app.building (id) ON DELETE RESTRICT,       -- NULL = whole zone
  title       text NOT NULL,
  source_uri  text NOT NULL,
  version     integer NOT NULL DEFAULT 1 CHECK (version > 0),
  is_active   boolean NOT NULL DEFAULT true,
  created_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (source_uri, version)
);

CREATE TABLE app.knowledge_chunk (
  id          uuid PRIMARY KEY DEFAULT app.uuid_v7(),
  doc_id      uuid NOT NULL REFERENCES app.knowledge_doc (id) ON DELETE CASCADE,
  zone_id     uuid,                                -- copied from doc for the retrieval filter
  building_id uuid,
  ordinal     integer NOT NULL CHECK (ordinal >= 0),
  content     text NOT NULL CHECK (btrim(content) <> ''),
  UNIQUE (doc_id, ordinal)
);
CREATE INDEX knowledge_chunk_scope_idx ON app.knowledge_chunk (zone_id, building_id);

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
  FOREACH t IN ARRAY ARRAY['subzone', 'building', 'basement', 'slot', 'gate', 'slot_pool', 'zone_policy',
                           'agreement_template', 'lpr_source'] LOOP
    EXECUTE format('ALTER TABLE app.%I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format($p$CREATE POLICY read_authenticated ON app.%I FOR SELECT
                      USING ((SELECT app.ctx_role()) <> 'anonymous')$p$, t);
    EXECUTE format($p$CREATE POLICY manage_zone ON app.%I FOR ALL
                      USING (app.is_zone_staff(zone_id, '{zone_manager}'))
                      WITH CHECK (app.is_zone_staff(zone_id, '{zone_manager}'))$p$, t);
  END LOOP;
END $$;
-- TH2 scope is a chain-operator decision (PRD §4, FR-26).
CREATE POLICY chain_operator_manage ON app.slot_pool FOR UPDATE
  USING ((SELECT app.ctx_role()) = 'chain_operator' AND slot_type = 'TH2')
  WITH CHECK ((SELECT app.ctx_role()) = 'chain_operator' AND slot_type = 'TH2');

ALTER TABLE app.price_rule ENABLE ROW LEVEL SECURITY;
CREATE POLICY read_authenticated ON app.price_rule FOR SELECT USING ((SELECT app.ctx_role()) <> 'anonymous');
CREATE POLICY manage_zone ON app.price_rule FOR ALL
  USING (EXISTS (SELECT 1 FROM app.zone_policy p WHERE p.id = zone_policy_id AND app.is_zone_staff(p.zone_id, '{zone_manager}')))
  WITH CHECK (EXISTS (SELECT 1 FROM app.zone_policy p WHERE p.id = zone_policy_id AND app.is_zone_staff(p.zone_id, '{zone_manager}')));

-- 20.2 Identity
ALTER TABLE app.app_user ENABLE ROW LEVEL SECURITY;
CREATE POLICY self ON app.app_user FOR ALL
  USING (id = (SELECT app.ctx_user_id())) WITH CHECK (id = (SELECT app.ctx_user_id()));
CREATE POLICY auth_and_system ON app.app_user FOR ALL
  USING ((SELECT app.ctx_role()) IN ('auth', 'system')) WITH CHECK ((SELECT app.ctx_role()) IN ('auth', 'system'));
-- A BQL sees people who hold an entitlement or a booking in their zone (names for tickets and approvals).
CREATE POLICY zone_manager_read ON app.app_user FOR SELECT
  USING ((SELECT app.ctx_role()) = 'zone_manager' AND (
           EXISTS (SELECT 1 FROM app.eligibility e WHERE e.user_id = app_user.id AND e.zone_id = ANY (app.ctx_zone_ids()))
        OR EXISTS (SELECT 1 FROM app.booking b WHERE (b.renter_user_id = app_user.id OR b.provider_user_id = app_user.id)
                                                AND b.zone_id = ANY (app.ctx_zone_ids()))));

DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['staff_zone', 'consent', 'refresh_token', 'password_reset_token', 'otp_challenge',
                           'notification'] LOOP
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

-- 20.5 Ledger, approvals, money
ALTER TABLE app.ledger_entry ENABLE ROW LEVEL SECURITY;
CREATE POLICY zone_staff_read ON app.ledger_entry FOR SELECT USING (app.is_zone_staff(zone_id));

ALTER TABLE app.approval_request ENABLE ROW LEVEL SECURITY;
CREATE POLICY zone_staff ON app.approval_request FOR ALL
  USING (app.is_zone_staff(zone_id)) WITH CHECK (app.is_zone_staff(zone_id));

ALTER TABLE app.payment ENABLE ROW LEVEL SECURITY;
CREATE POLICY payer ON app.payment FOR ALL
  USING (payer_user_id = (SELECT app.ctx_user_id())) WITH CHECK (payer_user_id = (SELECT app.ctx_user_id()));
CREATE POLICY zone_staff ON app.payment FOR ALL
  USING (app.is_zone_staff(zone_id)) WITH CHECK (app.is_zone_staff(zone_id));

ALTER TABLE app.voucher ENABLE ROW LEVEL SECURITY;
CREATE POLICY issuer ON app.voucher FOR ALL
  USING (issuer_user_id = (SELECT app.ctx_user_id())) WITH CHECK (issuer_user_id = (SELECT app.ctx_user_id()));
CREATE POLICY zone_staff ON app.voucher FOR ALL
  USING (app.is_zone_staff(zone_id)) WITH CHECK (app.is_zone_staff(zone_id));
-- A guest looks a voucher up by its unguessable code.
CREATE POLICY issued_read ON app.voucher FOR SELECT
  USING (status = 'issued' AND (SELECT app.ctx_role()) <> 'anonymous');

-- 20.6 Access / LPR: BQL, guards and system jobs of the zone.
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['lpr_event', 'parking_session', 'overstay_case'] LOOP
    EXECUTE format('ALTER TABLE app.%I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format($p$CREATE POLICY zone_staff ON app.%I FOR ALL
                      USING (app.is_zone_staff(zone_id, '{zone_manager,guard,system}'))
                      WITH CHECK (app.is_zone_staff(zone_id, '{zone_manager,guard,system}'))$p$, t);
  END LOOP;
END $$;

ALTER TABLE app.plate_access_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY zone_manager_read ON app.plate_access_log FOR SELECT USING (app.is_zone_staff(zone_id, '{zone_manager}'));

-- 20.7 Disputes
ALTER TABLE app.dispute_ticket ENABLE ROW LEVEL SECURITY;
CREATE POLICY zone_staff ON app.dispute_ticket FOR ALL
  USING (app.is_zone_staff(zone_id)) WITH CHECK (app.is_zone_staff(zone_id));
CREATE POLICY party_read ON app.dispute_ticket FOR SELECT
  USING (EXISTS (SELECT 1 FROM app.dispute_party p WHERE p.ticket_id = dispute_ticket.id AND p.user_id = (SELECT app.ctx_user_id())));

ALTER TABLE app.dispute_party ENABLE ROW LEVEL SECURITY;
CREATE POLICY own_read ON app.dispute_party FOR SELECT USING (user_id = (SELECT app.ctx_user_id()));
CREATE POLICY zone_staff ON app.dispute_party FOR ALL
  USING (app.is_zone_staff(zone_id)) WITH CHECK (app.is_zone_staff(zone_id));

ALTER TABLE app.dispute_evidence ENABLE ROW LEVEL SECURITY;
CREATE POLICY zone_staff ON app.dispute_evidence FOR ALL
  USING (app.is_zone_staff(zone_id)) WITH CHECK (app.is_zone_staff(zone_id));

-- 20.8 Swaps
ALTER TABLE app.swap_need ENABLE ROW LEVEL SECURITY;
CREATE POLICY own ON app.swap_need FOR ALL
  USING (user_id = (SELECT app.ctx_user_id())) WITH CHECK (user_id = (SELECT app.ctx_user_id()));
CREATE POLICY zone_staff ON app.swap_need FOR ALL
  USING (app.is_zone_staff(zone_id)) WITH CHECK (app.is_zone_staff(zone_id));

ALTER TABLE app.swap_proposal ENABLE ROW LEVEL SECURITY;
CREATE POLICY zone_staff ON app.swap_proposal FOR ALL
  USING (app.is_zone_staff(zone_id)) WITH CHECK (app.is_zone_staff(zone_id));
CREATE POLICY party_read ON app.swap_proposal FOR SELECT
  USING (EXISTS (SELECT 1 FROM app.swap_leg l WHERE l.proposal_id = swap_proposal.id
                   AND (SELECT app.ctx_user_id()) IN (l.from_user_id, l.to_user_id)));

ALTER TABLE app.swap_leg ENABLE ROW LEVEL SECURITY;
CREATE POLICY zone_staff ON app.swap_leg FOR ALL
  USING (app.is_zone_staff(zone_id)) WITH CHECK (app.is_zone_staff(zone_id));
CREATE POLICY party_read ON app.swap_leg FOR SELECT
  USING ((SELECT app.ctx_user_id()) IN (from_user_id, to_user_id));

-- 20.9 Reporting & platform
ALTER TABLE app.vacancy_forecast ENABLE ROW LEVEL SECURITY;
CREATE POLICY zone_staff ON app.vacancy_forecast FOR ALL
  USING (app.is_zone_staff(zone_id)) WITH CHECK (app.is_zone_staff(zone_id));
CREATE POLICY holder_read ON app.vacancy_forecast FOR SELECT
  USING (EXISTS (SELECT 1 FROM app.slot_holding h WHERE h.slot_id = vacancy_forecast.slot_id
                   AND h.user_id = (SELECT app.ctx_user_id()) AND h.held_during @> now()));

ALTER TABLE app.kpi_daily ENABLE ROW LEVEL SECURITY;
CREATE POLICY zone_staff ON app.kpi_daily FOR ALL
  USING (app.is_zone_staff(zone_id)) WITH CHECK (app.is_zone_staff(zone_id));
CREATE POLICY chain_operator_read ON app.kpi_daily FOR SELECT USING ((SELECT app.ctx_role()) = 'chain_operator');

ALTER TABLE app.reconciliation_report ENABLE ROW LEVEL SECURITY;
CREATE POLICY zone_staff ON app.reconciliation_report FOR ALL
  USING (app.is_zone_staff(zone_id)) WITH CHECK (app.is_zone_staff(zone_id));

ALTER TABLE app.workflow_run ENABLE ROW LEVEL SECURITY;
CREATE POLICY initiator_read ON app.workflow_run FOR SELECT USING (initiator_user_id = (SELECT app.ctx_user_id()));
CREATE POLICY system_or_zone ON app.workflow_run FOR ALL
  USING ((SELECT app.ctx_role()) = 'system' OR app.is_zone_staff(zone_id, '{zone_manager}'))
  WITH CHECK ((SELECT app.ctx_role()) = 'system' OR initiator_user_id = (SELECT app.ctx_user_id()));

ALTER TABLE app.audit_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY zone_manager_read ON app.audit_log FOR SELECT USING (app.is_zone_staff(zone_id, '{zone_manager}'));

ALTER TABLE app.knowledge_doc ENABLE ROW LEVEL SECURITY;
CREATE POLICY read_authenticated ON app.knowledge_doc FOR SELECT USING ((SELECT app.ctx_role()) <> 'anonymous');
CREATE POLICY manage_zone ON app.knowledge_doc FOR ALL
  USING (app.is_zone_staff(zone_id, '{zone_manager}')) WITH CHECK (app.is_zone_staff(zone_id, '{zone_manager}'));
ALTER TABLE app.knowledge_chunk ENABLE ROW LEVEL SECURITY;
CREATE POLICY read_authenticated ON app.knowledge_chunk FOR SELECT USING ((SELECT app.ctx_role()) <> 'anonymous');
CREATE POLICY manage_zone ON app.knowledge_chunk FOR ALL
  USING (app.is_zone_staff(zone_id, '{zone_manager}')) WITH CHECK (app.is_zone_staff(zone_id, '{zone_manager}'));

ALTER TABLE app.occupancy_hourly ENABLE ROW LEVEL SECURITY;
CREATE POLICY zone_staff ON app.occupancy_hourly FOR ALL
  USING (app.is_zone_staff(zone_id)) WITH CHECK (app.is_zone_staff(zone_id));

ALTER TABLE app.privacy_request ENABLE ROW LEVEL SECURITY;
CREATE POLICY own ON app.privacy_request FOR SELECT USING (user_id = (SELECT app.ctx_user_id()));
CREATE POLICY own_file ON app.privacy_request FOR INSERT
  WITH CHECK (user_id = (SELECT app.ctx_user_id()) AND status = 'received');
CREATE POLICY system ON app.privacy_request FOR ALL
  USING ((SELECT app.ctx_role()) = 'system') WITH CHECK ((SELECT app.ctx_role()) = 'system');

-- Not RLS-protected on purpose (no zone-private data, platform plumbing): chain, zone, size_class, holiday,
-- dispute_category, outbox (ids only), idempotency_keys, retention_rule (read-only), ledger_head (no grants).

-- -----------------------------------------------------------------------------------------------------
-- 21. Grants: least privilege. The app role gets DML, never DDL, TRUNCATE or ownership.
-- -----------------------------------------------------------------------------------------------------
GRANT USAGE ON SCHEMA app TO parksmart_app, parksmart_readonly;
GRANT USAGE, CREATE ON SCHEMA agent TO parksmart_checkpointer;   -- the saver creates its own tables once

GRANT SELECT ON ALL TABLES IN SCHEMA app TO parksmart_app;
GRANT INSERT, UPDATE ON ALL TABLES IN SCHEMA app TO parksmart_app;
GRANT DELETE ON app.staff_zone, app.refresh_token, app.password_reset_token, app.otp_challenge,
                app.idempotency_keys, app.outbox, app.notification, app.knowledge_chunk, app.vacancy_forecast
  TO parksmart_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA app TO parksmart_app;

-- Append-only tables: written only through SECURITY DEFINER functions.
REVOKE INSERT, UPDATE, DELETE ON app.ledger_entry, app.ledger_head, app.plate_access_log, app.audit_log FROM parksmart_app;
REVOKE ALL ON app.ledger_head FROM parksmart_app;

-- Ciphertext / unmasked evidence: not selectable directly; read through app.reveal_* (logged).
REVOKE SELECT ON app.vehicle, app.lpr_event, app.dispute_evidence FROM parksmart_app;
GRANT SELECT (id, user_id, plate_key_version, plate_hash, plate_masked, size_class_code, is_active, created_at, updated_at)
  ON app.vehicle TO parksmart_app;
GRANT SELECT (id, zone_id, source_id, source_event_id, gate_id, direction, occurred_at, received_at, plate_hash,
              plate_masked, ocr_confidence, status, matched_vehicle_id, matched_booking_id, reviewed_by, reviewed_at)
  ON app.lpr_event TO parksmart_app;
GRANT SELECT (id, zone_id, ticket_id, kind, object_key_masked, sha256, lpr_event_id, lpr_occurred_at, ledger_seq, created_at)
  ON app.dispute_evidence TO parksmart_app;

REVOKE ALL ON ALL FUNCTIONS IN SCHEMA app FROM PUBLIC;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA app TO parksmart_app;
REVOKE EXECUTE ON FUNCTION app.ensure_lpr_partitions(integer) FROM parksmart_app;   -- DDL: owner job only
REVOKE EXECUTE ON FUNCTION app.drop_expired_lpr_partitions(timestamptz), app.purge_expired(timestamptz),
                           app.purge_agent_checkpoints(timestamptz) FROM parksmart_app;   -- retention: owner job only
REVOKE INSERT, UPDATE ON app.retention_rule FROM parksmart_app;                            -- changed by migration/owner
GRANT DELETE ON app.occupancy_hourly TO parksmart_app;

-- Read-only role: aggregates only.
GRANT SELECT ON app.kpi_daily, app.zone, app.chain TO parksmart_readonly;
