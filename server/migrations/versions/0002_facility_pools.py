"""facility and pools: zone, building, slot_pool, slot

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-22

Schema v5 section 3, with its RLS (20.1) and grants (21).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        r"""
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
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (zone_id, code),
  UNIQUE (id, zone_id)
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

-- Row-Level Security (schema.sql section 20.1): reference / configuration tables.
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['building', 'slot', 'slot_pool'] LOOP
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
-- zone is not RLS-protected on purpose (no zone-private data).

-- Grants (schema.sql section 21): DML for the app role, aggregates-only read for the read-only role.
-- updated_at maintenance (v5 section 18)
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['zone', 'building', 'slot_pool', 'slot'] LOOP
    EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE ON app.%I
                    FOR EACH ROW EXECUTE FUNCTION app.set_updated_at()', t || '_updated_at', t);
  END LOOP;
END $$;

GRANT SELECT, INSERT, UPDATE ON app.zone, app.building, app.slot_pool, app.slot TO parksmart_app;
GRANT SELECT ON app.zone TO parksmart_readonly;
"""
    )


def downgrade() -> None:
    op.execute(
        r"""
-- Dropping a table removes its indexes, policies, grants and triggers.
DROP TABLE IF EXISTS app.slot;
DROP TABLE IF EXISTS app.slot_pool;
DROP TABLE IF EXISTS app.building;
DROP TABLE IF EXISTS app.zone;
"""
    )
