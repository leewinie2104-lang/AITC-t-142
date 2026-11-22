"""eligibility: asset, eligibility, slot_holding

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-22

Schema v5 section 5, with RLS (20.3) and grants (21). app.eligibility_level_at (section 10) is NOT here.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        r"""
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

-- Row-Level Security (schema.sql section 20.3).
ALTER TABLE app.eligibility ENABLE ROW LEVEL SECURITY;
CREATE POLICY zone_staff ON app.eligibility FOR ALL
  USING (app.is_zone_staff(zone_id)) WITH CHECK (app.is_zone_staff(zone_id));
CREATE POLICY holder_read ON app.eligibility FOR SELECT USING (user_id = (SELECT app.ctx_user_id()));
-- A user may file a claim for themselves; only the zone's BQL can verify it (status stays pending).
CREATE POLICY holder_claim ON app.eligibility FOR INSERT
  WITH CHECK (user_id = (SELECT app.ctx_user_id()) AND status = 'pending');

-- asset's holder_read policy reads eligibility, so it comes after that table.
ALTER TABLE app.asset ENABLE ROW LEVEL SECURITY;
CREATE POLICY zone_staff ON app.asset FOR ALL
  USING (app.is_zone_staff(zone_id)) WITH CHECK (app.is_zone_staff(zone_id));
CREATE POLICY holder_read ON app.asset FOR SELECT
  USING (EXISTS (SELECT 1 FROM app.eligibility e WHERE e.asset_id = asset.id AND e.user_id = (SELECT app.ctx_user_id())));

ALTER TABLE app.slot_holding ENABLE ROW LEVEL SECURITY;
CREATE POLICY zone_staff ON app.slot_holding FOR ALL
  USING (app.is_zone_staff(zone_id)) WITH CHECK (app.is_zone_staff(zone_id));
CREATE POLICY holder_read ON app.slot_holding FOR SELECT USING (user_id = (SELECT app.ctx_user_id()));

-- Grants (schema.sql section 21).
-- updated_at maintenance (v5 section 18)
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['asset', 'eligibility'] LOOP
    EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE ON app.%I
                    FOR EACH ROW EXECUTE FUNCTION app.set_updated_at()', t || '_updated_at', t);
  END LOOP;
END $$;

GRANT SELECT, INSERT, UPDATE ON app.asset, app.eligibility, app.slot_holding TO parksmart_app;
"""
    )


def downgrade() -> None:
    op.execute(
        r"""
-- Reverse order. The policy "zone_manager_read" on app.app_user (added by the booking revision) reads app.eligibility;
-- that revision's downgrade drops it before this one runs.
DROP POLICY IF EXISTS holder_read ON app.asset;
DROP TABLE IF EXISTS app.slot_holding;
DROP TABLE IF EXISTS app.eligibility;
DROP TABLE IF EXISTS app.asset;
"""
    )
