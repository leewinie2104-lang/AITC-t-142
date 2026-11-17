"""SessionStart hook: print a short repo status for the agent's context.

Shows the branch, uncommitted change count and in-progress plans in this tool's `plans/`.
Output goes to stdout, which the agent adds to the session context.
"""

from __future__ import annotations

import re
import subprocess
import sys

from _common import REPO_ROOT, TOOL_DIR

PLANS_DIR = TOOL_DIR / "plans"
_STATUS_RE = re.compile(r"\*\*Status\*\*:\s*\[?([^\]\n]+)", re.IGNORECASE)


def git(*args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, timeout=5, encoding="utf-8"
        )
        return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def open_plans() -> list[str]:
    plans = []
    for path in sorted(PLANS_DIR.glob("[0-9][0-9][0-9]-*.md")):
        match = _STATUS_RE.search(path.read_text(encoding="utf-8", errors="ignore"))
        status = match.group(1).strip() if match else "unknown"
        if not re.match(r"(completed|superseded)", status, re.IGNORECASE):
            plans.append(f"{path.name} ({status})")
    return plans


def main() -> None:
    branch = git("branch", "--show-current") or "(detached)"
    changes = [line for line in git("status", "--porcelain").splitlines() if line]
    lines = [f"[P-142] branch: {branch} · uncommitted files: {len(changes)}"]
    if branch in {"main", "dev"}:
        lines.append(f"[P-142] You are on `{branch}`: create a feature branch before committing.")
    plans = open_plans()
    if plans:
        lines.append(f"[P-142] open plans in {PLANS_DIR.relative_to(REPO_ROOT).as_posix()}/: " + ", ".join(plans))
    print("\n".join(lines))


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 - a broken hook must never stop the agent
        pass
    sys.exit(0)
