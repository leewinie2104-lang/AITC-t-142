---
paths:
  - "server/**"
---

# Backend rules

Applies to everything under `server/`. Core rules (git, secrets, logging hooks, plans) are in `.claude/rules/core.md`.
Background: `docs/05-development/01-server-structure.md` · `docs/10-adr/ADR-0010-backend-modules-agent-workflows-jobs.md` ·
`.claude/references/architecture-cheatsheet.md` · `.claude/references/llm-usage.md`.

## Commands (from `server/`)

`pytest -v` · `ruff check src/ tests/` · `ruff format src/ tests/` · `mypy src/` ·
`uvicorn app.main_api:app --app-dir src --reload --port 8000` ·
`python ../.claude/hooks/check_arch.py --all` (architecture scan).

## Module map (`src/app/`)

| Folder | Backlog | Jobs |
|--------|---------|------|
| `identity/` | M1 accounts | |
| `eligibility/` | M1 eligibility levels L1–L4 | N6 |
| `facility/` | M2 zone / building / vehicle / slot | |
| `policy/` | M3 rules & config — pure rule engine | |
| `sharing/` | M4 sharing | N4 |
| `booking/` | M5 booking | |
| `ledger/` | M6 agreement & append-only hash-chained ledger | |
| `payment/` | M7 payment (VietQR mock) & vouchers | |
| `access/` | M8 LPR & entry/exit | N1, N2 |
| `dispute/` | M10 disputes | N5 |
| `swap/` | M11 swaps | |
| `approval/` | M12 HITL approval queue | |
| `reporting/` | M12 dashboards | N3, N7, N8 |
| `notification/` | M13 notifications | |
| `knowledge/` | RAG over area rules (W7) | |
| `agent/` | M14 chat, W0 supervisor + W1–W7 | `run_workflow`, `resume_workflow` (queue `agent`) |
| `platform/` | shared infra (config, llm, prompts, db, queue, outbox, realtime, observability) — no business logic | |

`main_api.py` / `main_worker.py` are the only composition roots: they build real repositories and wire
ports → use cases → routers / jobs.

## Architecture rules (enforced by `.claude/hooks/check_arch.py`)

1. Every module has `domain/ usecase/ delivery/{rest,jobs}/ infrastructure/postgres/`.
2. **No cross-module imports.** Need another module's data → declare a `Protocol` port in your own
   `domain/ports.py`; the composition root adapts the other module's use case to it.
3. Only `agent/` calls use cases of several modules (never their `infrastructure/` or `delivery/`).
4. `langgraph` is imported only in `graph.py` files and `agent/infrastructure/`.
5. Jobs N1–N8 live in the owning module's `delivery/jobs/`, only detect and emit outbox events, and never
   import `app.platform.llm`; neither does `policy/`.
6. `platform/` never imports business modules.

| Layer | Contains | May import |
|-------|----------|------------|
| `domain/` | `entity.py` (`@dataclass`), `errors.py`, `ports.py` (`typing.Protocol`) | stdlib + own `domain/` |
| `usecase/` | one file per operation: `<Op>Input` DTO + `<Op>` class with `async execute(inp)` | own `domain/`, `platform/` |
| `delivery/rest/` | `router.py`, `schemas.py` (Pydantic v2), domain error → HTTP status | own `usecase/`, `domain/errors` |
| `delivery/jobs/` | arq functions `nX_<name>(ctx, …)`, registered in `main_worker.BgWorkerSettings` | own `usecase/` |
| `infrastructure/postgres/` | `repository.py` implementing ports | own `domain/`, `platform/db` |

## Business & AI rules

- **Rule engine decides, LLM only suggests (BR-14).** `policy/domain` is pure and deterministic; eligibility,
  rent permission, fees and approvals never depend on LLM output.
- Every LLM call goes through `app.platform.llm.client.get_llm(task_type)` (later the `LLMPort`); names
  and plates are pseudonymized before the call and restored after.
- Prompts: `prompts/*.md` with `{{placeholders}}`, loaded via `app.platform.prompts.loader` — never inline.
- All agent user input passes `app/agent/infrastructure/guardrails.py`; LLM output is validated into a Pydantic model.
- HITL (W2, W3, W5, W6): `interrupt()` → `approval` enqueue → BQL approves via REST → `agent.resume_workflow`
  job. Never resume inside the HTTP request. Approver = BQL of the slot's zone (BR-18).
- Ledger is append-only. Plates are masked in dispute tickets (BR-09). No PII in logs, span attributes or
  metric labels; span names `agent.<wN>.<step>` / `<module>.<usecase>`.

## Data

- asyncpg with `$1, $2…` parameters only; never build SQL with f-strings or concatenation.
- Schema changes only through Alembic migrations in `migrations/` (plain SQL, zone RLS — ADR-0005).
- New packages go into `requirements.txt` with a `>=` floor and a short comment; the commented blocks
  (asyncpg, alembic, arq, checkpoint-postgres) are enabled when the first feature needs them.

## Code style

Ruff (`ruff.toml`: py311, line 120, E/F/I/N/W/UP, double quotes) · full type hints · async I/O ·
one use case per file · comments explain *why* and match the surrounding density.

## Tests

- `tests/unit/<module>/test_<usecase>.py`: fake ports (in-memory classes or `AsyncMock`), no DB / LLM / network.
- `tests/unit/agent/`: patch `get_llm`; never call a real model.
- `tests/integration/`: real Postgres (`docker compose up postgres`), marked `@pytest.mark.integration`.
- API tests use the `client` fixture in `tests/conftest.py`; `asyncio_mode = auto`, `pythonpath = src`.
- Rule tables (L1–L4 × open scope × TH1/TH2/TH3) use `@pytest.mark.parametrize` with readable ids.
- Done = `make check` green, `check_arch.py --all` OK, and `make eval` when agent / prompts / guardrails changed.
