---
paths:
  - "server/**"
---

# Backend rules (core)

Loads for any file under `server/`. Narrower rules load on top of it by path: `.claude/rules/backend-agent.md`
(agent, LLM, prompts) · `.claude/rules/backend-data.md` (SQL, migrations, packages) · `.claude/rules/backend-tests.md`.
Background, read only when needed: `docs/04-development/01-server-structure.md` · ADR-0010 ·
`.claude/references/architecture-cheatsheet.md`.

## Commands (from `server/`)

`pytest -v` · `ruff check src/ tests/` · `ruff format src/ tests/` · `mypy src/` ·
`uvicorn app.main_api:app --app-dir src --reload --port 8000` · `python ../.claude/hooks/check_arch.py --all`.

## Modules (`src/app/`)

`identity` M1 · `eligibility` M1 L1–L4 (N6) · `facility` M2 · `policy` M3 pure rule engine · `sharing` M4 (N4) ·
`booking` M5 · `ledger` M6 agreement + append-only `consent_record` · `payment` M7 VietQR mock + vouchers ·
`access` M8 LPR (N1, N2) · `dispute` M10 (N5) · `swap` M11 · `approval` M12 HITL queue ·
`reporting` M12 dashboards (N3, N7, N8) · `notification` M13 · `knowledge` RAG (W7) · `agent` M14 W0–W7 ·
`platform` shared infra only (config, llm, prompts, db, queue, publish port, realtime, observability).
`main_api.py` / `main_worker.py` are the only composition roots (ports → use cases → routers / jobs).

## Architecture (enforced by `.claude/hooks/check_arch.py`)

1. Every module has `domain/ usecase/ delivery/{rest,jobs}/ infrastructure/postgres/`.
2. No cross-module imports. Need another module's data → a `Protocol` port in your own `domain/ports.py`,
   adapted in the composition root. Only `agent/` calls use cases of several modules.
3. `langgraph` only in `graph.py` files and `agent/infrastructure/`. `platform/` never imports business modules.
4. Jobs N1–N9 live in the owning module's `delivery/jobs/`, only detect and call their module's use case (which
   publishes via the platform publish port, ADR-0011), and never import `app.platform.llm`; neither does `policy/`.

| Layer | Contains | May import |
|-------|----------|------------|
| `domain/` | `entity.py` (`@dataclass`), `errors.py`, `ports.py` (`Protocol`) | stdlib + own `domain/` |
| `usecase/` | one file per op: `<Op>Input` DTO + `<Op>` with `async execute(inp)` | own `domain/`, `platform/` |
| `delivery/rest/` | `router.py`, `schemas.py` (Pydantic v2), domain error → HTTP status | own `usecase/`, `domain/errors` |
| `delivery/jobs/` | arq `nX_<name>(ctx, …)`, registered in `main_worker.BgWorkerSettings` | own `usecase/` |
| `infrastructure/postgres/` | `repository.py` implementing ports | own `domain/`, `platform/db` |

## Business invariants

- **Rule engine decides, LLM only suggests (BR-14).** `policy/domain` is pure and deterministic; eligibility,
  rent permission, fees and approvals never depend on LLM output.
- No PII in logs, span attributes or metric labels. Span names `<module>.<usecase>` / `agent.<wN>.<step>`.

## Code style & done

Ruff (py311, line 120, E/F/I/N/W/UP, double quotes) · full type hints · async I/O · one use case per file ·
comments explain *why*. Done = `make check` green + `check_arch.py --all` OK (+ `make eval` if agent changed).
