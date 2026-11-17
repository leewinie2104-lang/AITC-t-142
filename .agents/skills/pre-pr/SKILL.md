---
name: pre-pr
description: Final checks before opening a ParkSmart pull request — lint, tests, architecture scan, eval when relevant, secret scan, plan status, Conventional Commit message and PR description from .github/PULL_REQUEST_TEMPLATE.md. Use when the user says the work is done or asks to prepare a commit/PR.
---

# Pre-PR checklist

Run from repo root and report each result. Do not commit or push unless the user asks.

1. `git status` and `git diff dev...HEAD --stat` — confirm only intended files changed; branch is not `dev`/`main`.
2. `make lint` and `make test` (Windows without make: `cd server && ruff check src/ tests/ && pytest -v`).
3. `python .codex/hooks/check_arch.py --all`.
4. If `server/src/app/agent/`, `server/prompts/` or guardrails changed: `make eval` and report pass rate.
5. If docs changed: `python scripts/check_docs.py`.
6. Secret / PII scan of the diff: no API keys, tokens, `.env` values, real names or plates; `.env.example`
   has names only.
7. AI logging hooks untouched (`scripts/log_*.py`, `.ai-log/`, hook entries in tool configs).
8. Plan in `.codex/plans/` (if any): all steps ticked, Status `Completed`, summary filled.
9. Propose a Conventional Commit message (English): `type(scope): summary` — scope = module or area
   (`booking`, `agent`, `eval`, `docs`, `ci`).
10. Draft the PR body following `.github/PULL_REQUEST_TEMPLATE.md` (what changed, type, checklist), base `dev`.
