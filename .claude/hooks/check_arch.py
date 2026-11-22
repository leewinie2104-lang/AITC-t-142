"""Architecture guard for `server/src/app/` (ADR-0010 import rules).

Two modes:
- Hook (PostToolUse after Edit/Write): checks the edited files; exit 2 + stderr sends the
  violations back to the agent so it fixes them.
- CLI: run this file with `--all` to scan the whole app (exit 1 on violations).

Rules:
1. A business module never imports another business module (use `domain/ports.py`).
2. `domain/` imports only the stdlib and its own `domain/`.
3. `usecase/` never imports `infrastructure/` or `delivery/`.
4. `langgraph` only in `graph.py` files and `agent/infrastructure/`.
5. Background jobs (`delivery/jobs/`) and `policy/` never import `app.platform.llm`.
6. `platform/` never imports business modules or `agent/`.
7. `agent/` may call other modules' `usecase`/`domain`, never their `infrastructure`/`delivery`.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

from _common import REPO_ROOT, edited_files, read_payload, relative_to_repo

APP_DIR = REPO_ROOT / "server" / "src" / "app"
SHARED = {"platform"}


def _imports(tree: ast.AST) -> list[tuple[int, str]]:
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.append((node.lineno, node.module))
    return found


def check_file(path: Path) -> list[str]:
    """Return human-readable violations for one file under `server/src/app/`."""
    try:
        rel = path.resolve().relative_to(APP_DIR)
    except ValueError:
        return []
    # Top-level files (main_api.py, main_worker.py) are composition roots: they may wire anything.
    if path.suffix != ".py" or not path.exists() or len(rel.parts) == 1:
        return []

    owner = rel.parts[0]
    layer = rel.parts[1] if len(rel.parts) > 2 else ""
    in_jobs = len(rel.parts) > 3 and rel.parts[1:3] == ("delivery", "jobs")
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return []

    errors = []
    shown = relative_to_repo(path) or path
    for lineno, name in _imports(tree):
        top = name.split(".")[0]
        parts = name.split(".")
        where = f"{shown.as_posix()}:{lineno} imports `{name}`"

        if top == "langgraph" and rel.name != "graph.py" and rel.parts[:2] != ("agent", "infrastructure"):
            errors.append(f"{where}: langgraph is allowed only in graph.py and agent/infrastructure/.")

        if layer == "domain" and top not in sys.stdlib_module_names and top != "__future__":
            if not (len(parts) >= 3 and parts[:3] == ["app", owner, "domain"]):
                errors.append(f"{where}: domain/ may import only the stdlib and its own domain/.")
                continue

        if top != "app" or len(parts) < 2:
            continue
        target = parts[1]
        target_layer = parts[2] if len(parts) > 2 else ""

        if (in_jobs or owner == "policy") and name.startswith("app.platform.llm"):
            errors.append(f"{where}: background jobs and the rule engine must not call the LLM (BR-14).")
        if layer == "usecase" and target == owner and target_layer in {"infrastructure", "delivery"}:
            errors.append(f"{where}: usecase/ depends on domain ports, not on {target_layer}/.")
        if owner == "platform" and target not in SHARED:
            errors.append(f"{where}: platform/ must not depend on business modules.")
        elif owner == "agent":
            if target not in SHARED | {"agent"} and target_layer in {"infrastructure", "delivery"}:
                errors.append(f"{where}: agent/ may use other modules' usecase/domain only; wiring is done in main_*.py.")
        elif owner != "platform" and target not in SHARED | {owner}:
            errors.append(f"{where}: modules must not import other modules — declare a port in domain/ports.py.")
    return errors


def scan_all() -> list[str]:
    errors = []
    for path in sorted(APP_DIR.rglob("*.py")):
        errors.extend(check_file(path))
    return errors


def main() -> int:
    if "--all" in sys.argv:
        errors = scan_all()
        print("\n".join(errors) if errors else "check_arch: OK")
        return 1 if errors else 0

    errors = []
    for path in edited_files(read_payload()):
        errors.extend(check_file(path))
    if errors:
        sys.stderr.write("Architecture violations (ADR-0010):\n" + "\n".join(f"- {e}" for e in errors) + "\n")
        return 2
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except Exception:  # noqa: BLE001 - a broken hook must never stop the agent
        code = 0
    sys.exit(code)
