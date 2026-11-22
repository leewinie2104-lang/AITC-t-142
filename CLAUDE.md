# ParkSmart AI (P-142) — Claude Code

## Project in 60 seconds

- **ParkSmart AI**: parking-space sharing and booking across a chain of urban residential areas, with an
  AI agent (chat + LangGraph workflows) and human approval by the zone management board (BQL).
- **Stack**: Python 3.11 · FastAPI · LangGraph/LangChain 1.x · Pydantic v2 · Postgres (asyncpg, pgvector)
  · Redis (arq). Client (React + Vite) not initialized yet; infra = AWS CLI runbooks in `infra/` (ADR-0012, 0013).
- **Layout**: `server/` backend · `eval/` graded eval harness · `docs/` product, architecture, ADRs ·
  `client/`, `infra/` placeholders · `scripts/` AI-log hooks and doc check.
- **Sources**: `docs/README.md` (doc map) · `docs/07-adr/` (decisions) · `docs/01-product/` (PRD, BR-xx
  rules, backlog).
- **Language**: product docs and user-facing agent replies are Vietnamese; code, new comments, commit
  messages and AI config are English.

## Commands (repo root)

```bash
make install      # pip install -r server/requirements.txt
make run          # API at http://localhost:8000/docs
make check        # lint + typecheck + test (same as CI) — must pass before you say "done"
make typecheck    # mypy
make eval         # regenerates eval/results/report.md (no API key needed)
docker compose up # api + postgres + redis (workers: --profile workers)
```

No `make` on Windows: run the matching line of the `Makefile` directly.

## Configuration map

| What | Where |
|------|-------|
| Core rules (always loaded) | `.claude/rules/core.md` |
| Backend rules (auto-load by path) | `backend.md` (`server/**`) + `backend-agent.md` (agent, LLM, prompts), `backend-data.md` (SQL, migrations), `backend-tests.md` (`server/tests/**`) |
| Client rules (auto-load by path) | `client.md` (`client/**`); split into `client-*.md` when scaffolded |
| Other path rules | `eval.md` (`eval/**`), `adr.md` (`docs/07-adr/**`), `rules-authoring.md` (`.claude/**` config, 60-line limit) |
| Agents | `.claude/agents/`: `architect`, `backend-dev`, `test-writer`, `reviewer`, `eval-engineer`, `docs-keeper` |
| Skills | `.claude/skills/`: `new-usecase`, `new-agent-workflow`, `new-background-job`, `new-migration`, `new-prompt`, `eval-case`, `new-adr`, `pre-pr`, `jira-ticket` |
| Hooks | `.claude/hooks/` (scripts), registered in `.claude/settings.json` |
| Permissions | `.claude/settings.json` |
| Plans | `.claude/plans/` (template: `.claude/plans/TEMPLATE.md`) |
| References | `.claude/references/`: `architecture-cheatsheet.md`, `domain-glossary.md`, `llm-usage.md` |

Personal overrides go in `.claude/settings.local.json` and `CLAUDE.local.md` (git-ignored).
