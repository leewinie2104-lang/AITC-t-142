"""Tests for the agent hooks in .claude/hooks/ and .codex/hooks/ (run as subprocesses, like the tools do)."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOK_DIRS = [REPO_ROOT / ".claude" / "hooks", REPO_ROOT / ".codex" / "hooks"]
APP = REPO_ROOT / "server" / "src" / "app"


@pytest.fixture(params=HOOK_DIRS, ids=lambda p: p.parent.name)
def hooks_dir(request):
    return request.param


@pytest.fixture
def run_hook(hooks_dir):
    return lambda name, payload, *args: _run(hooks_dir / name, payload, *args)


def _run(script: Path, payload: dict | str, *args: str) -> subprocess.CompletedProcess:
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(
        [sys.executable, str(script), *args],
        input=stdin,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
    )


def bash(command: str) -> dict:
    return {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": command}}


@pytest.mark.parametrize(
    "command",
    [
        "git commit -m 'x' --no-verify",
        "git push --force origin dev",
        "git push -f",
        "sudo rm file",
        "rm -rf /",
        "rm -rf ~/",
        "rm -rf ..",
        "cat .env",
        "head -n 5 .env.local",
        "Get-Content .env",
        "cat global-bundle.pem",
        "ls .ai-log",
        "git config core.hooksPath /dev/null",
        "printenv",
    ],
)
def test_guard_blocks_dangerous_commands(command, run_hook):
    proc = run_hook("guard_bash.py", bash(command))
    assert proc.returncode == 2, proc.stderr
    assert "Blocked" in proc.stderr


@pytest.mark.parametrize(
    "command",
    [
        "make test",
        "cd server && pytest -v",
        "cat .env.example",
        "cp .env.example .env",
        "git push --force-with-lease origin feat/x",
        "git push origin feat/x",
        "rm -rf server/.pytest_cache",
        "printenv APP_ENV",
    ],
)
def test_guard_allows_normal_commands(command, run_hook):
    proc = run_hook("guard_bash.py", bash(command))
    assert proc.returncode == 0, proc.stderr


@pytest.mark.parametrize("payload", ["", "not json", {"tool_name": "Bash"}])
def test_hooks_never_crash_on_bad_input(payload, run_hook):
    for name in ("guard_bash.py", "format_python.py", "check_arch.py", "session_context.py"):
        assert run_hook(name, payload).returncode == 0


@pytest.fixture
def module_file():
    """A throwaway file inside a business module, removed after the test."""
    created: list[Path] = []

    def make(rel: str, source: str) -> Path:
        path = APP / rel
        dirs = [p for p in [path.parent, *path.parent.parents] if p != APP and APP in p.parents and not p.exists()]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
        created.extend([path, *dirs])
        return path

    yield make
    for path in created:
        if path.is_file():
            path.unlink()
    for path in sorted((p for p in created if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        path.rmdir()


def edit(path: Path) -> dict:
    return {"hook_event_name": "PostToolUse", "tool_name": "Edit", "tool_input": {"file_path": str(path)}}


@pytest.mark.parametrize(
    ("rel", "source", "message"),
    [
        ("booking/usecase/_t_cross.py", "from app.sharing.domain.ports import X\n", "must not import other modules"),
        ("booking/domain/_t_dom.py", "import pydantic\n", "domain/ may import only"),
        ("booking/usecase/_t_infra.py", "from app.booking.infrastructure.postgres import repo\n", "not on infrastructure"),
        ("booking/usecase/_t_lg.py", "import langgraph\n", "langgraph is allowed only"),
        ("access/delivery/jobs/_t_job.py", "from app.platform.llm.client import get_llm\n", "must not call the LLM"),
        ("agent/usecase/_t_agent.py", "from app.booking.infrastructure.postgres import repo\n", "agent/ may use"),
    ],
)
def test_check_arch_reports_violations(module_file, rel, source, message, run_hook):
    proc = run_hook("check_arch.py", edit(module_file(rel, source)))
    assert proc.returncode == 2
    assert message in proc.stderr


@pytest.mark.parametrize(
    ("rel", "source"),
    [
        ("booking/usecase/_t_ok.py", "from app.booking.domain.ports import X\nfrom app.platform.config import settings\n"),
        ("booking/domain/_t_ok.py", "from dataclasses import dataclass\nfrom app.booking.domain.errors import E\n"),
        ("agent/usecase/_t_ok.py", "from app.booking.usecase.hold_slot import HoldSlot\n"),
        ("agent/workflows/w1_request/graph.py", "import langgraph\n"),
    ],
)
def test_check_arch_allows_valid_imports(module_file, rel, source, run_hook):
    proc = run_hook("check_arch.py", edit(module_file(rel, source)))
    assert proc.returncode == 0, proc.stderr


def test_check_arch_codex_apply_patch_payload(module_file, run_hook):
    path = module_file("booking/usecase/_t_patch.py", "from app.sharing.usecase import x\n")
    patch = f"*** Begin Patch\n*** Update File: {path.relative_to(REPO_ROOT).as_posix()}\n@@\n*** End Patch"
    payload = {"tool_name": "apply_patch", "cwd": str(REPO_ROOT), "tool_input": {"command": patch}}
    assert run_hook("check_arch.py", payload).returncode == 2


def test_check_arch_full_scan_is_clean(run_hook):
    proc = run_hook("check_arch.py", "", "--all")
    assert proc.returncode == 0, proc.stdout


def test_session_context_prints_branch(run_hook):
    proc = run_hook("session_context.py", {"hook_event_name": "SessionStart"})
    assert proc.returncode == 0
    assert "[P-142] branch:" in proc.stdout
