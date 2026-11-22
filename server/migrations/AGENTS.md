# Backend rules — data, SQL, packages

Loads on top of `server/AGENTS.md`. Skill: `new-migration`. Background: ADR-0005 (RLS per zone).

- asyncpg with `$1, $2…` parameters only; never build SQL with f-strings or concatenation.
- Schema changes only through Alembic migrations in `migrations/` (plain SQL, zone RLS).
- Append-only tables: `consent_record`, `dispute_evidence`, `ai_decision_log` — no UPDATE / DELETE paths.
- Plates are masked in dispute tickets (BR-09).
- Repositories implement the module's own `domain/ports.py`; they never import another module.
- New packages go into `requirements.txt` with a `>=` floor and a short comment. The commented blocks
  (asyncpg, alembic, arq, checkpoint-postgres) are enabled when the first feature needs them.
