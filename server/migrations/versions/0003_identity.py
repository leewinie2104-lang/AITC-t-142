"""identity: app_user, vehicle

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-22

Schema v5 section 4, with RLS (20.2, minus the two policies that read app.booking) and grants (21).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        r"""
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

-- Row-Level Security (schema.sql sections 20.2) and grants (21).
-- Deferred to the booking revision (they read app.booking, created later), see that revision's docstring:
--   CREATE POLICY zone_manager_read ON app.app_user  (needs app.eligibility + app.booking)
--   CREATE POLICY zone_staff_read   ON app.vehicle   (needs app.booking)
ALTER TABLE app.app_user ENABLE ROW LEVEL SECURITY;
CREATE POLICY self ON app.app_user FOR ALL
  USING (id = (SELECT app.ctx_user_id())) WITH CHECK (id = (SELECT app.ctx_user_id()));
CREATE POLICY auth_and_system ON app.app_user FOR ALL
  USING ((SELECT app.ctx_role()) IN ('auth', 'system')) WITH CHECK ((SELECT app.ctx_role()) IN ('auth', 'system'));

ALTER TABLE app.vehicle ENABLE ROW LEVEL SECURITY;
CREATE POLICY own_or_system ON app.vehicle FOR ALL
  USING (user_id = (SELECT app.ctx_user_id()) OR (SELECT app.ctx_role()) = 'system')
  WITH CHECK (user_id = (SELECT app.ctx_user_id()) OR (SELECT app.ctx_role()) = 'system');

-- updated_at maintenance (v5 section 18)
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['app_user', 'vehicle'] LOOP
    EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE ON app.%I
                    FOR EACH ROW EXECUTE FUNCTION app.set_updated_at()', t || '_updated_at', t);
  END LOOP;
END $$;

GRANT SELECT, INSERT, UPDATE ON app.app_user TO parksmart_app;
-- Ciphertext: never selectable (MVP shows masked plates only; the logged reveal functions are deferred).
GRANT INSERT, UPDATE ON app.vehicle TO parksmart_app;
GRANT SELECT (id, user_id, plate_key_version, plate_hash, plate_masked, size_class, is_active, created_at, updated_at)
  ON app.vehicle TO parksmart_app;
"""
    )


def downgrade() -> None:
    op.execute(
        r"""
-- Dropping a table removes its indexes, policies and grants. A later revision's policy that reads these tables must be
-- dropped by that revision's own downgrade (it runs first).
DROP TABLE IF EXISTS app.vehicle;
DROP TABLE IF EXISTS app.app_user;
"""
    )
