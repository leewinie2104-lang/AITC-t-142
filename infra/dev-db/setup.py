"""Start the shared dev Postgres + Redis on the CI EC2 (plan 017). Run on the box as root: python3 setup.py

Creates .env with random passwords on the first run (chmod 600, never printed), then
`docker compose up -d --wait`. Safe to re-run: an existing .env is kept.
"""

import secrets
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENV_FILE = HERE / ".env"
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


def main() -> int:
    ensure_env()
    cmd = ["docker", "compose", "-f", str(HERE / "docker-compose.devdb.yml"), "up", "-d", "--wait"]
    return subprocess.run(cmd, cwd=HERE, check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
