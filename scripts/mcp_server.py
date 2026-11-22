"""Launch a dev MCP server (Postgres or Redis) with connection details taken from the repo `.env`.

Registered in `.mcp.json` so every dev uses their own `.env` (DATABASE_URL / REDIS_URL, see `.env.example`) and
no secret lands in git. Requires `uv` on PATH and Tailscale up (shared dev DB on the CI EC2, plan 017 / 025).

    uv run --no-project scripts/mcp_server.py postgres   # read-only SQL (postgres-mcp --access-mode=restricted)
    uv run --no-project scripts/mcp_server.py redis      # official Redis MCP server

Secrets are passed through environment variables only, never on the command line or to stdout
(stdout is the MCP stdio channel).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPO_ROOT / ".env"


def load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value
    return values


def setting(name: str, env_file: dict[str, str]) -> str:
    # A value exported in the shell wins over `.env`, like pydantic-settings in the app.
    value = os.environ.get(name) or env_file.get(name, "")
    if not value or "_HERE" in value:
        sys.stderr.write(
            f"mcp_server: {name} is missing or still a placeholder in {ENV_FILE}\n"
        )
        sys.exit(2)
    return value


def postgres_command(env_file: dict[str, str], env: dict[str, str]) -> list[str]:
    url = setting("DATABASE_URL", env_file)
    # SQLAlchemy-style driver suffixes (postgresql+asyncpg://) are not understood by psycopg.
    scheme, sep, rest = url.partition("://")
    env["DATABASE_URI"] = f"{scheme.split('+')[0]}{sep}{rest}"
    # postgres-mcp pins a pglast that left PyPI and breaks on the mcp 2.x SDK: see the overrides file.
    overrides = REPO_ROOT / "scripts" / "mcp_postgres_overrides.txt"
    return [
        "uvx",
        "--python",
        "3.12",
        "--overrides",
        str(overrides),
        "postgres-mcp",
        "--access-mode=restricted",
    ]


def redis_command(env_file: dict[str, str], env: dict[str, str]) -> list[str]:
    parts = urlsplit(setting("REDIS_URL", env_file))
    env["REDIS_HOST"] = parts.hostname or "localhost"
    env["REDIS_PORT"] = str(parts.port or 6379)
    db = (parts.path or "/0").lstrip("/") or "0"
    if not db.isdigit():
        sys.stderr.write(
            f"mcp_server: REDIS_URL must end with a DB index 0-15 (got '/{db}') in {ENV_FILE}\n"
        )
        sys.exit(2)
    env["REDIS_DB"] = db
    env["REDIS_SSL"] = "true" if parts.scheme == "rediss" else "false"
    if parts.username:
        env["REDIS_USERNAME"] = unquote(parts.username)
    if parts.password:
        env["REDIS_PWD"] = unquote(parts.password)
    # Without --url the CLI applies its own --host/--port/--db defaults over REDIS_HOST/PORT/DB, so pass those
    # (not secret) as flags; the password stays in REDIS_PWD, which the CLI does not override.
    return [
        "uvx", "--python", "3.12", "--from", "redis-mcp-server", "redis-mcp-server",
        "--host", env["REDIS_HOST"], "--port", env["REDIS_PORT"], "--db", env["REDIS_DB"],
    ]  # fmt: skip


COMMANDS = {"postgres": postgres_command, "redis": redis_command}


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        sys.stderr.write(f"usage: mcp_server.py {{{'|'.join(COMMANDS)}}}\n")
        return 2
    if shutil.which("uvx") is None:
        sys.stderr.write(
            "mcp_server: uvx not found on PATH; install uv (https://docs.astral.sh/uv/)\n"
        )
        return 2
    env = dict(os.environ)
    cmd = COMMANDS[sys.argv[1]](load_env(ENV_FILE), env)
    # subprocess (not exec) so stdio is inherited the same way on Windows and macOS.
    return subprocess.call(cmd, env=env, cwd=REPO_ROOT)


if __name__ == "__main__":
    sys.exit(main())
