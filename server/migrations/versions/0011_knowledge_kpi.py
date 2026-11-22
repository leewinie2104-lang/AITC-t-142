"""Knowledge base (pgvector) and KPI view

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-22
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# SQL copied from docs/03-design/sql/schema.sql (v5); RLS and grants live in the same revision as the table (ADR-0005).


def upgrade() -> None:
    op.execute("""
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

-- RLS (v5 section 20.9)
ALTER TABLE app.knowledge_chunk ENABLE ROW LEVEL SECURITY;
CREATE POLICY read_authenticated ON app.knowledge_chunk FOR SELECT USING ((SELECT app.ctx_role()) <> 'anonymous');
CREATE POLICY manage_zone ON app.knowledge_chunk FOR ALL
  USING (app.is_zone_staff(zone_id, '{zone_manager}')) WITH CHECK (app.is_zone_staff(zone_id, '{zone_manager}'));

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
), fee AS (      -- overstay fees actually paid (waived ones are 'cancelled' and drop out), VND
  SELECT p.zone_id, (p.paid_at AT TIME ZONE vz.timezone)::date AS day, sum(p.amount_vnd)::bigint AS overstay_fees
  FROM app.payment p
  JOIN visible_zone vz ON vz.zone_id = p.zone_id
  WHERE p.kind = 'overstay_fee' AND p.status = 'paid_simulated'
  GROUP BY p.zone_id, (p.paid_at AT TIME ZONE vz.timezone)::date
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

-- Grants (v5 section 21)
GRANT SELECT, INSERT, UPDATE, DELETE ON app.knowledge_chunk TO parksmart_app;
-- The view is read-only for everybody.
REVOKE INSERT, UPDATE ON app.kpi_daily_v FROM parksmart_app;
GRANT SELECT ON app.kpi_daily_v TO parksmart_app, parksmart_readonly;
GRANT SELECT ON app.zone TO parksmart_readonly;
""")


def downgrade() -> None:
    op.execute("""
REVOKE SELECT ON app.zone FROM parksmart_readonly;
DROP VIEW app.kpi_daily_v;
DROP TABLE app.knowledge_chunk;
""")
