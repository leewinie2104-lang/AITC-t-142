"""AI decision log (append-only)

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-22
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# SQL copied from docs/03-design/sql/schema.sql (v5); RLS and grants live in the same revision as the table (ADR-0005).


def upgrade() -> None:
    op.execute("""
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

-- RLS (v5 section 20.9)
-- Users never read the AI decision log; the BQL reads its own zone; the agent worker (system) writes and reads.
ALTER TABLE app.ai_decision_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY zone_manager_read ON app.ai_decision_log FOR SELECT USING (app.is_zone_staff(zone_id, '{zone_manager}'));
CREATE POLICY system_all ON app.ai_decision_log FOR ALL
  USING ((SELECT app.ctx_role()) = 'system') WITH CHECK ((SELECT app.ctx_role()) = 'system');

-- Grants (v5 section 21): append-only, INSERT + SELECT only.
GRANT SELECT, INSERT ON app.ai_decision_log TO parksmart_app;
REVOKE UPDATE, DELETE, TRUNCATE ON app.ai_decision_log FROM parksmart_app;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA app TO parksmart_app;
""")


def downgrade() -> None:
    op.execute("""
DROP TABLE app.ai_decision_log;
""")
