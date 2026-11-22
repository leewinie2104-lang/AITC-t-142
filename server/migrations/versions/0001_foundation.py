"""foundation: schemas, extensions, roles, enums, helper functions

Revision ID: 0001
Revises:
Create Date: 2026-11-22

Schema v5 sections 0-2 (+ the table-independent grants of section 21).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        r"""
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
CREATE TYPE app.request_outcome    AS ENUM ('matched', 'redirected_th3', 'redirected_public', 'blocked', 'no_match');
CREATE TYPE app.booking_status     AS ENUM ('held', 'pending_agreement', 'pending_approval', 'confirmed',
                                            'completed', 'relocated', 'cancelled', 'expired', 'rejected');
CREATE TYPE app.agreement_status   AS ENUM ('pending_confirmation', 'pending_approval', 'effective',
                                            'rejected', 'expired', 'cancelled');
-- v5: 'dispute_decision' (W5: the BQL decides a dispute, subject_id = dispute_case.id); 'swap' returns with M11.
CREATE TYPE app.approval_kind      AS ENUM ('agreement_over_threshold', 'early_return_escalation', 'dispute_decision');
CREATE TYPE app.approval_status    AS ENUM ('pending', 'approved', 'rejected', 'expired', 'cancelled');
-- v4: enum ledger_entry_type removed with the ledger (docs/03-design/08-deferred-tables.md).
-- relocation_th3: renter pays the TH3 price for the relocated period; early_return_refund: unused share time
-- refunded to the renter (D-09). payment.direction tells charges from refunds.
-- v5: overstay_fee (W4, FR-12) is a CHARGE to the renter, computed by the rule engine at exit (checked_out_at set; trigger
-- payment_overstay_guard). Payee rule, no payee column (VietQR mock, A-05): the fee goes to the provider
-- (booking.provider_user_id), or to the zone for a TH3 booking (provider_user_id IS NULL).
CREATE TYPE app.payment_kind       AS ENUM ('share_booking', 'th3_visit', 'relocation_th3', 'early_return_refund', 'overstay_fee');
CREATE TYPE app.payment_status     AS ENUM ('pending', 'paid_simulated', 'failed', 'cancelled');
CREATE TYPE app.gate_direction     AS ENUM ('in', 'out');
CREATE TYPE app.lpr_status         AS ENUM ('accepted', 'pending_review', 'confirmed_manual', 'unreadable');
-- v4: agent_thread / recovery_case / consent_record / ai_decision_log (plan 002 section 3.2).
CREATE TYPE app.workflow_code      AS ENUM ('W0', 'W1', 'W2', 'W3', 'W4', 'W5', 'W6', 'W7');
CREATE TYPE app.thread_status      AS ENUM ('active', 'awaiting_user', 'awaiting_manager', 'completed', 'failed');
CREATE TYPE app.recovery_trigger   AS ENUM ('owner_early_return');
CREATE TYPE app.recovery_status    AS ENUM ('open', 'options_ready', 'awaiting_consent', 'resolved', 'escalated', 'cancelled');
CREATE TYPE app.consent_action     AS ENUM ('registration_terms', 'plate_processing', 'agreement_confirm', 'accept_relocation');
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

-- Grants that do not depend on tables (schema.sql section 21). Tables are granted in the revision that creates them.
GRANT USAGE ON SCHEMA app TO parksmart_app, parksmart_readonly;
GRANT USAGE, CREATE ON SCHEMA agent TO parksmart_checkpointer;   -- the saver creates its own tables once
ALTER DEFAULT PRIVILEGES FOR ROLE parksmart_checkpointer IN SCHEMA agent
  GRANT SELECT, DELETE ON TABLES TO parksmart_owner;   -- schema.sql section 18c
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA app FROM PUBLIC;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA app TO parksmart_app;
"""
    )


def downgrade() -> None:
    op.execute(
        r"""
-- Reverse order of upgrade. Roles are cluster-wide and may serve other databases: never dropped here, and their
-- ALTER ROLE ... SET defaults are left as they are. Extensions are dropped (fails, harmlessly, if something else uses them).
-- Schemas are dropped without CASCADE: a non-empty schema (e.g. agent.* checkpointer tables, or tables from a later
-- revision) makes the downgrade fail instead of silently destroying data.
DROP FUNCTION IF EXISTS app.set_updated_at();
DROP FUNCTION IF EXISTS app.is_finite_range(tstzrange);
DROP FUNCTION IF EXISTS app.scope_max_level(app.open_scope);
DROP FUNCTION IF EXISTS app.is_zone_staff(uuid, text[]);
DROP FUNCTION IF EXISTS app.ctx_zone_ids();
DROP FUNCTION IF EXISTS app.ctx_role();
DROP FUNCTION IF EXISTS app.ctx_user_id();
DROP FUNCTION IF EXISTS app.uuid_v7();

DROP TYPE IF EXISTS app.evidence_kind;
DROP TYPE IF EXISTS app.dispute_status;
DROP TYPE IF EXISTS app.dispute_category;
DROP TYPE IF EXISTS app.ai_outcome;
DROP TYPE IF EXISTS app.ai_risk_level;
DROP TYPE IF EXISTS app.consent_decision;
DROP TYPE IF EXISTS app.consent_action;
DROP TYPE IF EXISTS app.recovery_status;
DROP TYPE IF EXISTS app.recovery_trigger;
DROP TYPE IF EXISTS app.thread_status;
DROP TYPE IF EXISTS app.workflow_code;
DROP TYPE IF EXISTS app.lpr_status;
DROP TYPE IF EXISTS app.gate_direction;
DROP TYPE IF EXISTS app.payment_status;
DROP TYPE IF EXISTS app.payment_kind;
DROP TYPE IF EXISTS app.approval_status;
DROP TYPE IF EXISTS app.approval_kind;
DROP TYPE IF EXISTS app.agreement_status;
DROP TYPE IF EXISTS app.booking_status;
DROP TYPE IF EXISTS app.request_outcome;
DROP TYPE IF EXISTS app.share_status;
DROP TYPE IF EXISTS app.holding_kind;
DROP TYPE IF EXISTS app.eligibility_status;
DROP TYPE IF EXISTS app.eligibility_role;
DROP TYPE IF EXISTS app.asset_kind;
DROP TYPE IF EXISTS app.building_kind;
DROP TYPE IF EXISTS app.user_status;
DROP TYPE IF EXISTS app.user_role;
DROP TYPE IF EXISTS app.slot_operational_status;
DROP TYPE IF EXISTS app.size_class;
DROP TYPE IF EXISTS app.eligibility_level;
DROP TYPE IF EXISTS app.open_scope;
DROP TYPE IF EXISTS app.slot_type;

DROP EXTENSION IF EXISTS pgcrypto;
DROP EXTENSION IF EXISTS btree_gist;
ALTER DEFAULT PRIVILEGES FOR ROLE parksmart_checkpointer IN SCHEMA agent
  REVOKE SELECT, DELETE ON TABLES FROM parksmart_owner;
DROP SCHEMA IF EXISTS agent;
DROP SCHEMA IF EXISTS app;
"""
    )
