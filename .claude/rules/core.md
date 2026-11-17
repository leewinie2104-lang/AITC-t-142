# Core rules

## Invariants

1. **Code wins over docs.** If they disagree, follow the code and flag the doc.
2. **Clean Architecture per ADR-0010; the rule engine decides and the LLM only suggests (BR-14).** The full
   list is in `.claude/rules/backend.md`. Read it before any change under `server/`.
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
1. Copy `.claude/plans/TEMPLATE.md` to `.claude/plans/NNN-short-slug.md`, using the next free number.
2. Get approval.
3. Implement, tick the steps and set **Status**.

Small fixes need no plan.

## Agents and skills

- Delegate only to the agents in `.claude/agents/`, and pick the one whose description matches the task.
- Use a skill from `.claude/skills/` whenever its description matches the task.
- References in `.claude/references/` are loaded on demand. Do not copy them into answers.

## Precedence

These project rules override generic rules inherited from parent folders or personal config written for
other stacks (e.g. Go conventions, `go test`, `internal/<domain>/`).
