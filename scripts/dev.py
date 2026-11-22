"""Run the API (uvicorn --reload, :8000) and the SPA (Vite, :3000) together, for `make dev`.

Vite proxies /api/v1 to :8000 (client/vite.config.ts), so open http://localhost:3000. Output of both is interleaved
with an [api] / [web] prefix. Ctrl+C, or either process exiting, stops both. Cross-platform: no shell, no `&`.

Usage: python scripts/dev.py [--api-port 8000] [--pnpm pnpm]
"""

from __future__ import annotations

import argparse
import shlex
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _pump(name: str, proc: subprocess.Popen[str]) -> None:
    assert proc.stdout is not None
    for line in proc.stdout:
        sys.stdout.write(f"[{name}] {line}")
        sys.stdout.flush()


def _stop(procs: dict[str, subprocess.Popen[str]]) -> None:
    for proc in procs.values():
        if proc.poll() is None:
            proc.terminate()
    deadline = time.monotonic() + 10
    for proc in procs.values():
        try:
            proc.wait(timeout=max(0.1, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            proc.kill()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api-port", type=int, default=8000)
    parser.add_argument("--pnpm", default="pnpm", help='pnpm command, e.g. "npx pnpm@9" when pnpm is not installed')
    args = parser.parse_args()

    pnpm = shlex.split(args.pnpm)
    resolved = shutil.which(pnpm[0])  # finds pnpm.cmd / npx.cmd on Windows
    if resolved is None:
        print(f"{pnpm[0]} not found: install pnpm (corepack enable) or pass --pnpm 'npx pnpm@9'", file=sys.stderr)
        return 2
    if not (ROOT / "client" / "node_modules").is_dir():
        print("client/node_modules missing: run `make client-install` first", file=sys.stderr)
        return 2

    commands = {
        "api": (
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main_api:app",
                "--app-dir",
                "src",
                "--reload",
                "--host",
                "0.0.0.0",
                "--port",
                str(args.api_port),
            ],
            ROOT / "server",
        ),
        "web": ([resolved, *pnpm[1:], "dev"], ROOT / "client"),
    }
    procs: dict[str, subprocess.Popen[str]] = {}
    for name, (cmd, cwd) in commands.items():
        procs[name] = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        threading.Thread(target=_pump, args=(name, procs[name]), daemon=True).start()
    print(f"[dev] api http://localhost:{args.api_port}/docs · web http://localhost:3000 · Ctrl+C to stop both")

    try:
        while all(proc.poll() is None for proc in procs.values()):
            time.sleep(0.5)
        exited = next(name for name, proc in procs.items() if proc.poll() is not None)
        print(f"[dev] {exited} exited with code {procs[exited].returncode}; stopping the other one")
    except KeyboardInterrupt:
        print("\n[dev] stopping")
    finally:
        _stop(procs)
    return max(proc.returncode or 0 for proc in procs.values())


if __name__ == "__main__":
    sys.exit(main())
