# AI agent setup (Claude Code + Codex)

Claude Code and Codex each have their **own complete setup**, and neither imports from the other. Each piece of content is
written in both places with the same text; only tool-specific paths differ.
`server/tests/unit/test_ai_config_parity.py` fails if the two sides drift apart.

## Side by side

| Component | Claude Code | Codex |
|-----------|-------------|-------|
| Overview + commands + config map | `CLAUDE.md` | top of `AGENTS.md` |
| Core rules (always apply) | `.claude/rules/core.md` | rest of `AGENTS.md` |
| Backend rules | `.claude/rules/backend.md` (`paths: server/**`) | `server/AGENTS.md` |
| Eval rules | `.claude/rules/eval.md` (`paths: eval/**`) | `eval/AGENTS.md` |
| Client rules | `.claude/rules/client.md` (`paths: client/**`) | `client/AGENTS.md` |
| Agents (6) | `.claude/agents/<name>.md` | `.codex/agents/<name>.toml` |
| Skills (8) | `.claude/skills/<name>/SKILL.md` | `.agents/skills/<name>/SKILL.md` |
| Hook scripts | `.claude/hooks/*.py` | `.codex/hooks/*.py` (byte-identical) |
| Hook registration | `.claude/settings.json` → `hooks` | `.codex/hooks.json` |
| Permissions | `.claude/settings.json` → `permissions` | `.codex/config.toml` + `.codex/rules/project.rules` |
| Plans | `.claude/plans/` + `TEMPLATE.md` | `.codex/plans/` + `TEMPLATE.md` |
| References | `.claude/references/*.md` | `.codex/references/*.md` |
| Personal settings | `.claude/settings.local.json`, `CLAUDE.local.md` | `~/.codex/config.toml` |

Notes:
- Codex has no folder for prose rules (`.codex/rules/` is its command-policy format), so its rules
  live in `AGENTS.md` files. Codex loads `AGENTS.md` from the repo root down to the current folder.
  The root file tells it to read `server/AGENTS.md` etc. before working there.
- `.agents/skills/` is the skills location Codex documents. `.agents/` also holds Antigravity's
  `hooks.json`, `rules/` and `workflows/`; leave those untouched.

### Agent format

| Field | Claude (`.md` frontmatter) | Codex (`.toml`) |
|-------|----------------------------|-----------------|
| Name | `name` | `name` |
| When to use | `description` | `description` |
| Strength | `model: opus / sonnet / haiku` | `model_reasoning_effort: high / medium / low` |
| Tools | `tools:` list (no Edit/Write = read-only) | Not configurable per agent; the read-only rule is stated in the instructions |
| Instructions | Markdown body | `developer_instructions` (same text) |

## Editing rule

Change both sides in the same commit. The map from Claude paths to Codex paths lives in
`CLAUDE_TO_CODEX` in the parity test. Run `cd server && pytest tests/unit/test_ai_config_parity.py`
to see any mismatch.

## Hooks

| Hook | Event | What it does | Blocks? |
|------|-------|--------------|---------|
| `scripts/log_hook.py` | UserPromptSubmit (+ Stop for Codex) | Writes the graded prompt log to `.ai-log/` | never. **Do not remove** |
| `session_context.py` | SessionStart | Prints branch, dirty-file count and open plans | no |
| `guard_bash.py` | PreToolUse `Bash` | Blocks `--no-verify`, force-push, `sudo`, broad `rm -rf`, reading `.env`/`*.pem`, `.ai-log/`, env dumps | yes (exit 2) |
| `format_python.py` | PostToolUse edits | `ruff check --fix` + `ruff format` on edited `.py` | no |
| `check_arch.py` | PostToolUse edits | ADR-0010 import rules for `server/src/app/`; `--all` scans the whole app | reports back (exit 2) |

Hooks run through `scripts/_pyrun.sh` / `scripts/_pyrun.cmd`. These launchers prefer `.venv` and exit 0
if no Python is found.

## Per-OS setup

### macOS
```bash
python3.11 -m venv .venv && source .venv/bin/activate
make install
bash scripts/setup_hooks.sh
```

### Windows
- Install **Git for Windows**. Claude Code runs hooks through Git Bash.
- Install Python 3.11 and create the venv in the repo root:
  ```powershell
  py -3.11 -m venv .venv
  .venv\Scripts\Activate.ps1
  pip install -r server/requirements.txt
  powershell -ExecutionPolicy Bypass -File scripts/setup_hooks.ps1
  ```
- `make` is optional: run the Makefile commands directly (`cd server; pytest -v`).
- Codex on Windows uses `commandWindows` from `.codex/hooks.json`.
- `.gitattributes` keeps `.sh`/`.py` as LF and `.cmd`/`.ps1` as CRLF.

### Codex
- Trust the project once so `.codex/config.toml`, hooks and rules load.
- Check the command policy: `codex execpolicy check --pretty --rules .codex/rules/project.rules -- git push --force`.

### Claude Code
- `/agents`, `/hooks`, `/permissions` and `/memory` show what is loaded. Invoke skills with `/new-usecase` etc.
