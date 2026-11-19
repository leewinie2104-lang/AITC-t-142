---
name: new-migration
description: Create a ParkSmart database migration (Alembic with plain SQL, Postgres + pgvector, RLS per zone — ADR-0005) in server/migrations, plus the matching asyncpg repository change. Use whenever a table, column, index, policy or view is added or changed.
---

# New migration

Read ADR-0005 (`docs/10-adr/ADR-0005-rds-postgres-asyncpg-rls-alembic-sql.md`) first.

## Rules
- Plain SQL via `op.execute("""...""")` in both `upgrade()` and `downgrade()`; no ORM models, no autogenerate.
- One migration per logical change; filename `NNNN_<module>_<change>.py` (revision id = `NNNN`).
- Table names prefixed by module when ambiguous (`booking_hold`, `consent_record`).
- Every zone-owned table has `zone_id` NOT NULL, an index on it, `ENABLE ROW LEVEL SECURITY` and a policy
  using the session setting the API sets per request (see ADR-0005).
- Store licence plates encrypted / hashed as decided for M2; never plain PII in new columns without a note.
- Append-only tables (`consent_record`, `ai_decision_log`): statement trigger `app.reject_mutation()`, app role gets `INSERT` + `SELECT` only.
- `timestamptz` for times, `uuid` ids, explicit `ON DELETE` behaviour.

## Steps
1. If Alembic is not set up yet: uncomment `asyncpg` and `alembic` in `server/requirements.txt` (ask the
   user first), create `server/alembic.ini` + `server/migrations/env.py` reading `DATABASE_URL` from settings.
2. Write the migration with `upgrade` and a working `downgrade`.
3. Update/create `<module>/infrastructure/postgres/repository.py` (`$n` params only).
4. Run against local Postgres: `docker compose up -d postgres`, then `cd server && alembic upgrade head`,
   `alembic downgrade -1`, `alembic upgrade head`.
5. Add/adjust integration tests in `server/tests/integration/` (RLS: a user of zone A cannot read zone B).
