"""PreToolUse hook: block dangerous shell commands before they run.

Exit 2 blocks the call and shows the reason to the agent. Mirrors the core rules on
AI logging hooks and secrets.
"""

from __future__ import annotations

import re
import sys

from _common import bash_command, block, read_payload

# Commands that read file contents (bash, cmd and PowerShell spellings).
_READERS = r"(?:cat|less|more|head|tail|bat|type|nl|od|xxd|strings|grep|rg|awk|sed|source|\.|get-content|gc|select-string)"
_SECRET_FILE = r"(?:\.env(?!\.example\b)(?:\.[\w-]+)?|[\w./\\-]*\.pem|[\w./\\-]*credentials?[\w.-]*)"

RULES: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"--no-verify\b"),
        "`--no-verify` is forbidden: git hooks submit the graded AI log. Fix the hook failure instead.",
    ),
    (
        re.compile(r"\bcore\.hooksPath\b|\bgit\s+config\b.*\bhooks\b", re.IGNORECASE),
        "Changing git hook configuration is forbidden (graded AI logging hooks).",
    ),
    (
        re.compile(r"\bgit\s+push\b[^;&|]*(?:\s--force(?!-with-lease)\b|\s-f\b|\s\+\S)"),
        "Force-push is forbidden. Use `--force-with-lease` on your own feature branch only, and only if the user asked.",
    ),
    (
        re.compile(r"\bsudo\b"),
        "`sudo` is not allowed from an agent. Ask the user to run it.",
    ),
    (
        re.compile(
            r"\brm\s+-[a-z]*r[a-z]*\s+(?:-\S+\s+)*(?:/|~|\$HOME|\.\.?(?:/|\s|$)|\*|[A-Za-z]:[\\/])",
            re.IGNORECASE,
        ),
        "Recursive delete of `/`, `~`, `.`, `..`, `*` or a drive root is blocked. Delete specific paths instead.",
    ),
    (
        re.compile(r"\b(?:rd|rmdir)\s+/s\b|\bremove-item\b.*-recurse.*\s[A-Za-z]:[\\/]?\s*$", re.IGNORECASE),
        "Recursive delete on Windows of a broad path is blocked. Delete specific paths instead.",
    ),
    (
        re.compile(r"\.ai-log\b"),
        "`.ai-log/` is managed by the logging hooks and graded. Do not read, move or delete it.",
    ),
    (
        re.compile(rf"(?:^|[\s;&|(])({_READERS})\s+[^;&|]*?(?<![\w.]){_SECRET_FILE}(?:\s|$|[;&|)])", re.IGNORECASE),
        "Reading secret files (`.env`, `*.pem`, credentials) is blocked. Use `.env.example` for variable names.",
    ),
    (
        re.compile(r"(?:^|[;&|]\s*)(?:printenv|env|set)\s*(?:$|[;&|])|\bget-childitem\s+env:", re.IGNORECASE),
        "Dumping all environment variables may leak secrets. Read a specific non-secret variable instead.",
    ),
]


def check(command: str) -> str | None:
    """Return the block reason for `command`, or None if it is allowed."""
    for pattern, reason in RULES:
        if pattern.search(command):
            return reason
    return None


def main() -> None:
    command = bash_command(read_payload())
    if not command:
        return
    reason = check(command)
    if reason:
        block(f"Blocked by the guard_bash hook: {reason}")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001 - a broken hook must never stop the agent
        sys.exit(0)
