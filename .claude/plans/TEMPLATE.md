# Plan NNN: <Task title>

- **Status**: Pending Approval | In Progress | Completed | Superseded
- **Date**: YYYY-MM-DD · **Owner**: <name>
- **Agents / skills**: e.g. architect → backend-dev (new-usecase) → test-writer → reviewer
- **Refs**: BR-xx, US-xx, AC-xx, ADR-00xx, backlog item

## 1. Context
Why this change, what problem, intended outcome (2–4 lines).

## 2. Scope
- **In**: …
- **Out**: … (Nên có / Tương lai items not done here)
- **Modules / layers**: e.g. `booking` (domain, usecase, delivery/rest, infrastructure), `agent/w1`
- **DB / prompts / eval impact**: migration? new prompt? eval cases?

## 3. Steps
- [ ] 1. … — `server/src/app/<module>/domain/…`
- [ ] 2. … — `…/usecase/<op>.py`
- [ ] 3. … — `…/delivery/rest/router.py`
- [ ] 4. Tests — `server/tests/unit/<module>/…`
- [ ] 5. Eval cases — `eval/datasets/…` (if agent behaviour changes)
- [ ] 6. Docs — `docs/README.md` / ADR (if needed)

## 4. Verification
- [ ] `make check`
- [ ] `python .claude/hooks/check_arch.py --all`
- [ ] `make eval` (agent / prompt / guardrail changes)
- [ ] Manual: `make run` → `http://localhost:8000/docs` → <endpoint / scenario>

## 5. Completion summary
- **Completed**: YYYY-MM-DD · **Files**: …
- **Notes / follow-ups**: …
