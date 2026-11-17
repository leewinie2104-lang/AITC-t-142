"""Helpers for the hooks in this folder.

Both tools send a JSON payload on stdin with `tool_name` and `tool_input`. Hooks
must never crash the agent: on any unexpected error they exit 0 silently.
Launch through `scripts/_pyrun.sh` (bash / Git Bash) or `scripts/_pyrun.cmd` (Windows).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parent
TOOL_DIR = HOOKS_DIR.parent  # .claude/ or .codex/
REPO_ROOT = TOOL_DIR.parent

# Codex `apply_patch` puts the patch text in tool_input.command / input.
_PATCH_FILE_RE = re.compile(r"^\*\*\* (?:Add|Update) File: (.+)$", re.MULTILINE)


def read_payload() -> dict:
    """Read the hook JSON from stdin; return {} if empty or invalid."""
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except (ValueError, OSError):
        return {}


def tool_input(payload: dict) -> dict:
    value = payload.get("tool_input") or {}
    return value if isinstance(value, dict) else {"command": str(value)}


def bash_command(payload: dict) -> str:
    """The shell command of a Bash / shell tool call, or ''."""
    command = tool_input(payload).get("command", "")
    if isinstance(command, list):  # Codex may send argv
        command = " ".join(str(part) for part in command)
    return str(command)


def edited_files(payload: dict) -> list[Path]:
    """Absolute paths of files touched by an Edit / Write / MultiEdit / apply_patch call."""
    inp = tool_input(payload)
    raw: list[str] = []
    for key in ("file_path", "path", "notebook_path"):
        if isinstance(inp.get(key), str):
            raw.append(inp[key])
    for key in ("command", "input", "patch"):
        text = inp.get(key)
        if isinstance(text, list):
            text = "\n".join(str(part) for part in text)
        if isinstance(text, str) and "*** " in text:
            raw.extend(match.strip() for match in _PATCH_FILE_RE.findall(text))

    cwd = Path(payload.get("cwd") or REPO_ROOT)
    paths = []
    for item in raw:
        path = Path(item)
        paths.append((path if path.is_absolute() else cwd / path).resolve())
    return paths


def relative_to_repo(path: Path) -> Path | None:
    """Repo-relative path, or None if the file is outside the repo."""
    try:
        return path.resolve().relative_to(REPO_ROOT)
    except ValueError:
        return None


def block(reason: str) -> None:
    """Block the tool call / report a problem back to the agent (exit code 2 + stderr)."""
    sys.stderr.write(reason.rstrip() + "\n")
    sys.exit(2)
