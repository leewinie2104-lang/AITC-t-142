---
paths:
  - ".claude/rules/**"
  - ".claude/skills/**"
  - ".claude/agents/**"
  - "CLAUDE.md"
---

# Writing rules, skills and agents (lazy load)

Context is loaded in three tiers. Put each rule in the cheapest tier that still triggers when it is needed:

| Tier | Loads | Use for |
|------|-------|---------|
| `CLAUDE.md`, rules without `paths` | every session | project map and invariants only (`core.md`) |
| rules with `paths:` frontmatter | when a matching file is read or edited | conventions for one area (`server/**`, `client/**`) |
| skills (`.claude/skills/<name>/SKILL.md`) | when the task matches the `description` | workflows not tied to files (Jira, PR, ADR) |
| references (`.claude/references/`) | only when a rule links to them | background, tables, long examples |

## Rules

- A new rule file gets `paths:` unless it truly applies to every task. Prefer narrow globs
  (`server/tests/**`) over broad ones, and layer narrow files on top of a core file (`backend.md` + `backend-*.md`).
- One concern per file; name it `<area>.md` or `<area>-<topic>.md`. Do not repeat what another rule says; link to it.
- Link to docs, ADRs and references instead of copying them.
- **Size limit: 60 lines per rule file** (frontmatter included). If a new or edited rule, skill or agent file is
  over 60 lines, delegate to the `docs-keeper` agent to review it and cut the load: remove duplicates, move
  background to `.claude/references/`, or split it into narrower path-scoped files. Do not finish until it is ≤ 60 lines.
- After adding, moving or splitting a rule, update the table in `CLAUDE.md` and `docs/08-ai/01-agent-setup.md`,
  and any agent or skill that names the old file.
