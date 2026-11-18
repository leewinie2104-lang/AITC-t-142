# ParkSmart AI (P-142) — Codex

## Project in 60 seconds

- **ParkSmart AI**: parking-space sharing and booking across a chain of urban residential areas, with an
  AI agent (chat + LangGraph workflows) and human approval by the zone management board (BQL).
- **Stack**: Python 3.11 · FastAPI · LangGraph/LangChain 1.x · Pydantic v2 · Postgres (asyncpg, pgvector)
  · Redis (arq). Client (React + Vite) and infra (Terraform) are not initialized yet.
- **Layout**: `server/` backend · `eval/` graded eval harness · `docs/` product, architecture, ADRs ·
  `client/`, `infra/` placeholders · `scripts/` AI-log hooks and doc check.
- **Sources**: `docs/README.md` (doc map) · `docs/10-adr/` (decisions) · `docs/01-product/` (PRD, BR-xx
  rules, backlog).
- **Language**: product docs and user-facing agent replies are Vietnamese; code, new comments, commit
  messages and AI config are English.

## Commands (repo root)

```bash
make install      # pip install -r server/requirements.txt
make run          # API at http://localhost:8000/docs
make check        # lint + test — must pass before you say "done"
make typecheck    # mypy
make eval         # regenerates eval/results/report.md (no API key needed)
docker compose up # api + postgres + redis (workers: --profile workers)
```

No `make` on Windows: run the matching line of the `Makefile` directly.

## Configuration map

| What | Where |
|------|-------|
| Core rules (always apply) | `AGENTS.md` |
| Backend rules — read before changing anything under `server/` | `server/AGENTS.md` |
| Eval rules — read before changing anything under `eval/` | `eval/AGENTS.md` |
| Client rules — read before changing anything under `client/` | `client/AGENTS.md` |
| Agents | `.codex/agents/`: `architect`, `backend-dev`, `test-writer`, `reviewer`, `eval-engineer`, `docs-keeper` |
| Skills | `.agents/skills/`: `new-usecase`, `new-agent-workflow`, `new-background-job`, `new-migration`, `new-prompt`, `eval-case`, `new-adr`, `pre-pr` |
| Hooks | `.codex/hooks/` (scripts), registered in `.codex/hooks.json` |
| Permissions | `.codex/config.toml` (sandbox, approvals) and `.codex/rules/project.rules` (command policy) |
| Plans | `.codex/plans/` (template: `.codex/plans/TEMPLATE.md`) |
| References | `.codex/references/`: `architecture-cheatsheet.md`, `domain-glossary.md`, `llm-usage.md` |

Personal settings (model, reasoning effort) go in `~/.codex/config.toml`.

# Core rules

## Invariants

1. **Code wins over docs.** If they disagree, follow the code and flag the doc.
2. **Clean Architecture per ADR-0010; the rule engine decides and the LLM only suggests (BR-14).** The full
   list is in `server/AGENTS.md`. Read it before any change under `server/`.
3. **AI logging hooks are graded.** Never remove or disable the `scripts/log_*.py` entries in `.claude/`,
   `.codex/`, `.cursor/`, `.gemini/`, `.agents/`, `.github/hooks/`. Never touch `.ai-log/`. Never use `--no-verify`.
4. **Secrets**: never read or print `.env`, `*.pem` or credentials. Use `.env.example` for variable names.
5. `docs/guide/` is the organizers' guidebook (CODEOWNERS-protected). Do not edit it.
6. New empty folders get a `.gitkeep`.
7. If a hook blocks you, fix the cause. Never work around it.

## Git

- Branch off `dev` (`feat/…`, `fix/…`, `docs/…`, `chore/…`). PRs target `dev`; `main` is release.
- Conventional Commits in English, with the module or area as scope: `feat(booking): add hold-slot use case`.
- Commit or push only when the user asks. Never force-push shared branches.

## Cross-platform (the team uses macOS and Windows)

- Scripts and hooks are Python only. Launch them via `scripts/_pyrun.sh` (bash / Git Bash) or
  `scripts/_pyrun.cmd` (cmd / PowerShell). No bash-only or PowerShell-only logic.
- Use `pathlib` and `encoding="utf-8"` for file I/O. No hard-coded path separators, no GNU/BSD-only flags.
- Line endings come from `.gitattributes` (LF for code, CRLF for `.cmd` / `.ps1` / `.bat`).

## Plans

Non-trivial work (a feature, workflow, migration or cross-cutting refactor) starts with a plan:
1. Copy `.codex/plans/TEMPLATE.md` to `.codex/plans/NNN-short-slug.md`, using the next free number.
2. Get approval.
3. Implement, tick the steps and set **Status**.

Small fixes need no plan.

## Agents and skills

- Delegate only to the agents in `.codex/agents/`, and pick the one whose description matches the task.
- Use a skill from `.agents/skills/` whenever its description matches the task.
- References in `.codex/references/` are loaded on demand. Do not copy them into answers.

## Precedence

These project rules override generic rules inherited from parent folders or personal config written for
other stacks (e.g. Go conventions, `go test`, `internal/<domain>/`).
