"""PostToolUse hook: ruff-format and auto-fix Python files the agent just edited.

Only touches `*.py` under `server/`, `eval/` or `scripts/`. Never blocks: remaining
lint errors are printed as a warning so the agent can fix them.
"""

from __future__ import annotations

import shutil
import subprocess
import sys

from _common import REPO_ROOT, edited_files, read_payload, relative_to_repo

SCOPES = ("server", "eval", "scripts")
RUFF_CONFIG = REPO_ROOT / "server" / "ruff.toml"


def ruff_cmd() -> list[str] | None:
    """Prefer ruff from the current interpreter (project venv), then PATH."""
    try:
        import ruff  # noqa: F401

        return [sys.executable, "-m", "ruff"]
    except ImportError:
        exe = shutil.which("ruff")
        return [exe] if exe else None


def main() -> None:
    files = []
    for path in edited_files(read_payload()):
        rel = relative_to_repo(path)
        if rel and rel.suffix == ".py" and rel.parts[0] in SCOPES and path.exists():
            files.append(str(path))
    if not files:
        return
    ruff = ruff_cmd()
    if ruff is None:
        sys.stderr.write("format_python: ruff not installed (run `make install`); skipped.\n")
        return

    config = ["--config", str(RUFF_CONFIG)]
    run = {"cwd": REPO_ROOT, "capture_output": True, "text": True, "timeout": 30}
    subprocess.run([*ruff, "check", "--fix", "--quiet", *config, *files], **run)
    subprocess.run([*ruff, "format", "--quiet", *config, *files], **run)
    remaining = subprocess.run([*ruff, "check", "--quiet", *config, *files], **run)
    if remaining.returncode != 0:
        sys.stderr.write("ruff issues left after auto-fix:\n" + remaining.stdout[-2000:])


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 - a broken hook must never stop the agent
        pass
    sys.exit(0)
