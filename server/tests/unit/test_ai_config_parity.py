"""Claude Code and Codex each have their own full AI setup; this keeps their content identical.

Each Claude file has a Codex twin. The texts must match after the tool-specific paths below are swapped.
When you change one side, make the same change on the other side.

| Claude Code | Codex |
|---|---|
| `CLAUDE.md` + `.claude/rules/core.md` | `AGENTS.md` |
| `.claude/rules/{backend,eval,client}.md` | `{server,eval,client}/AGENTS.md` |
| `.claude/rules/backend-{agent,data,tests}.md` | `server/{src/app/agent,migrations,tests}/AGENTS.md` |
| `.claude/agents/*.md` | `.codex/agents/*.toml` |
| `.claude/skills/**` | `.agents/skills/**` |
| `.claude/hooks/*.py` | `.codex/hooks/*.py` (byte-identical) |
| `.claude/plans/TEMPLATE.md` | `.codex/plans/TEMPLATE.md` |
| `.claude/references/*.md` | `.codex/references/*.md` |
"""

import tomllib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
CLAUDE = REPO_ROOT / ".claude"
CODEX = REPO_ROOT / ".codex"
CODEX_SKILLS = REPO_ROOT / ".agents" / "skills"

# Claude text -> Codex text. Applied in order, so put longer / more specific strings first.
CLAUDE_TO_CODEX: list[tuple[str, str]] = [
    ("# ParkSmart AI (P-142) — Claude Code", "# ParkSmart AI (P-142) — Codex"),
    (
        "Personal overrides go in `.claude/settings.local.json` and `CLAUDE.local.md` (git-ignored).",
        "Personal settings (model, reasoning effort) go in `~/.codex/config.toml`.",
    ),
    ("registered in `.claude/settings.json`", "registered in `.codex/hooks.json`"),
    (
        "| Permissions | `.claude/settings.json` |",
        "| Permissions | `.codex/config.toml` (sandbox, approvals) and `.codex/rules/project.rules` (command policy) |",
    ),
    (".claude/rules/core.md", "AGENTS.md"),
    (".claude/rules/backend-agent.md", "server/src/app/agent/AGENTS.md"),
    (".claude/rules/backend-data.md", "server/migrations/AGENTS.md"),
    (".claude/rules/backend-tests.md", "server/tests/AGENTS.md"),
    (".claude/rules/backend.md", "server/AGENTS.md"),
    (".claude/rules/eval.md", "eval/AGENTS.md"),
    (".claude/rules/client.md", "client/AGENTS.md"),
    (".claude/hooks", ".codex/hooks"),
    (".claude/plans", ".codex/plans"),
    (".claude/references", ".codex/references"),
    (".claude/skills", ".agents/skills"),
    (".claude/agents", ".codex/agents"),
]
NESTED_RULES = {
    "backend": "server",
    "backend-agent": "server/src/app/agent",
    "backend-data": "server/migrations",
    "backend-tests": "server/tests",
    "eval": "eval",
    "client": "client",
}
EFFORT_BY_MODEL = {"opus": "high", "sonnet": "medium", "haiku": "low"}


def to_codex(text: str) -> str:
    for claude, codex in CLAUDE_TO_CODEX:
        text = text.replace(claude, codex)
    return text


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def split_frontmatter(text: str) -> tuple[dict[str, str], str]:
    head, body = text[4:].split("\n---\n", 1)
    meta = {}
    for line in head.splitlines():
        if ":" in line and not line.startswith(" "):
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()
    return meta, body.lstrip("\n")


def expected_codex_files() -> dict[Path, str]:
    """Every Codex file and the content it must have, derived from the Claude side."""
    files = {
        REPO_ROOT / "AGENTS.md": to_codex(read(REPO_ROOT / "CLAUDE.md") + "\n" + read(CLAUDE / "rules" / "core.md"))
    }
    for rule, folder in NESTED_RULES.items():
        files[REPO_ROOT / folder / "AGENTS.md"] = to_codex(split_frontmatter(read(CLAUDE / "rules" / f"{rule}.md"))[1])
    for src in sorted((CLAUDE / "skills").rglob("*")):
        if src.is_file():
            files[CODEX_SKILLS / src.relative_to(CLAUDE / "skills")] = to_codex(read(src))
    for sub in ("plans/TEMPLATE.md", *(f"references/{p.name}" for p in sorted((CLAUDE / "references").glob("*.md")))):
        files[CODEX / sub] = to_codex(read(CLAUDE / sub))
    for src in sorted((CLAUDE / "hooks").glob("*.py")):
        files[CODEX / "hooks" / src.name] = read(src)
    return files


@pytest.mark.parametrize("path", list(expected_codex_files()), ids=lambda p: p.relative_to(REPO_ROOT).as_posix())
def test_codex_file_matches_claude(path):
    assert path.exists(), f"missing Codex twin: {path.relative_to(REPO_ROOT)}"
    assert read(path) == expected_codex_files()[path]


@pytest.mark.parametrize("src", sorted((CLAUDE / "agents").glob("*.md")), ids=lambda p: p.stem)
def test_codex_agent_matches_claude(src):
    meta, body = split_frontmatter(read(src))
    agent = tomllib.loads(read(CODEX / "agents" / f"{src.stem}.toml"))
    assert agent["name"] == meta["name"]
    assert agent["description"] == meta["description"]
    assert agent.get("model_reasoning_effort") == EFFORT_BY_MODEL[meta["model"]]
    assert agent["developer_instructions"].strip() == to_codex(body).strip()


def test_no_orphan_codex_files():
    expected = set(expected_codex_files())
    actual = {p for p in CODEX_SKILLS.rglob("*") if p.is_file()}
    actual |= {p for sub in ("hooks", "references", "plans") for p in (CODEX / sub).glob("*") if p.is_file()}
    actual = {p for p in actual if p.name not in {".DS_Store", ".gitkeep"} and "__pycache__" not in p.parts}
    agents = {p.stem for p in (CODEX / "agents").glob("*.toml")}
    assert actual - expected == set()
    assert agents == {p.stem for p in (CLAUDE / "agents").glob("*.md")}
