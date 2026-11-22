"""Start the shared dev Postgres + Redis on the CI EC2 (plan 017). Run on the box as root: python3 setup.py

Creates .env with random passwords on the first run (chmod 600, never printed), writes the migrator URL into the
GitHub Actions runner's env file, then `docker compose up -d --wait`. Safe to re-run: an existing .env is kept.
"""

import secrets
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENV_FILE = HERE / ".env"
RUNNER_ENV = Path("/home/runner/actions-runner/.env")
KEYS = ("POSTGRES_PASSWORD", "MIGRATOR_PASSWORD", "APP_PASSWORD", "REDIS_PASSWORD")


def ensure_env() -> None:
    if ENV_FILE.exists():
        print(f"keep existing {ENV_FILE}")
        return
    # token_hex is URL-safe, so the values drop straight into DSNs without escaping.
    lines = [f"{key}={secrets.token_hex(24)}" for key in KEYS]
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ENV_FILE.chmod(0o600)
    print(f"created {ENV_FILE} (chmod 600, root only)")


def ensure_runner_env() -> None:
    """Give CI job `migrate-dev-db` the migrator URL through the runner's own env file (no GitHub secret).

    The runner loads this file into every job on start. Every job could already reach the DB through the docker
    group, so this adds no new exposure (ADR-0013). Restart the runner service afterwards to load it.
    """
    if not RUNNER_ENV.parent.is_dir():
        print(f"skip runner env: {RUNNER_ENV.parent} not found")
        return
    values = dict(line.split("=", 1) for line in ENV_FILE.read_text(encoding="utf-8").splitlines() if "=" in line)
    url = f"postgresql://parksmart_migrator:{values['MIGRATOR_PASSWORD']}@localhost:15432/parksmart"
    lines = RUNNER_ENV.read_text(encoding="utf-8").splitlines() if RUNNER_ENV.exists() else []
    lines = [line for line in lines if not line.startswith("MIGRATE_DATABASE_URL=")]
    lines.append(f"MIGRATE_DATABASE_URL={url}")
    RUNNER_ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")
    RUNNER_ENV.chmod(0o600)
    shutil.chown(RUNNER_ENV, user="runner", group="runner")
    print(f"wrote MIGRATE_DATABASE_URL to {RUNNER_ENV} (chmod 600, runner); restart the runner service to load it")


def main() -> int:
    ensure_env()
    ensure_runner_env()
    cmd = ["docker", "compose", "-f", str(HERE / "docker-compose.devdb.yml"), "up", "-d", "--wait"]
    return subprocess.run(cmd, cwd=HERE, check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
