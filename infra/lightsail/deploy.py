#!/usr/bin/env python3
"""Pull-based deploy for the ParkSmart Lightsail host (ADR-0012).

Run by parksmart-deploy.timer every 2 minutes, as root. Each run:
  1. Find the `sha-…` tag that ECR's `main` tag points to. Same as the running tag (or a tag that
     already failed) -> exit 0.
  2. Download s3://<bucket>/releases/<tag>.tgz (compose file, Caddyfile, these scripts) into
     /opt/parksmart/releases/<tag>/.
  3. docker login, pull, run `alembic upgrade head` if the image has alembic, `up -d --wait`.
  4. Health check https://<SITE_ADDRESS>/api/v1/health. On failure, mark the tag failed and
     start the previous tag again.
  5. On success, install the scripts and systemd units from the release (self-update).

Migrations are forward-only: a rollback restarts the previous image but does not undo them.
Config: /etc/parksmart/deploy.conf (KEY=VALUE). AWS credentials come from the SSM hybrid
activation (root's shared credentials file), never from a stored access key.
"""

from __future__ import annotations

import fcntl
import filecmp
import json
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path("/opt/parksmart")
CONF = Path("/etc/parksmart/deploy.conf")
RELEASES = ROOT / "releases"
STATE = ROOT / "state"
DEPLOY_ENV = ROOT / "deploy.env"
BIN = ROOT / "bin"
SYSTEMD = Path("/etc/systemd/system")
KEEP_RELEASES = 5
HEALTH_TRIES = 20
HEALTH_WAIT_S = 6


def log(msg: str) -> None:
    print(msg, flush=True)


def run(*args: str, input_text: str | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    log("+ " + " ".join(args))
    return subprocess.run(args, input=input_text, text=True, capture_output=True, check=check)


def read_kv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def read_state(name: str) -> str:
    path = STATE / name
    return path.read_text(encoding="utf-8").strip() if path.exists() else ""


def write_state(name: str, value: str) -> None:
    (STATE / name).write_text(value + "\n", encoding="utf-8")


class Deployer:
    def __init__(self, conf: dict[str, str]) -> None:
        self.region = conf["AWS_REGION"]
        self.registry = conf["ECR_REGISTRY"]
        self.repository = conf["ECR_REPOSITORY"]
        self.bucket = conf["RELEASE_BUCKET"]

    def aws(self, *args: str) -> str:
        return run("aws", "--region", self.region, *args).stdout

    def target_tag(self) -> str:
        """The sha-… tag sharing a digest with `main`, or '' if `main` does not exist yet."""
        try:
            out = self.aws(
                "ecr",
                "describe-images",
                "--repository-name",
                self.repository,
                "--image-ids",
                "imageTag=main",
                "--query",
                "imageDetails[0].imageTags",
                "--output",
                "json",
            )
        except subprocess.CalledProcessError as exc:
            if "ImageNotFoundException" in exc.stderr:
                return ""
            raise
        tags = [t for t in json.loads(out) or [] if t.startswith("sha-")]
        if not tags:
            raise RuntimeError("tag main has no sha-… tag next to it")
        return tags[0]

    def fetch_release(self, tag: str) -> Path:
        target = RELEASES / tag
        if (target / "docker-compose.prod.yml").exists():
            return target
        archive = RELEASES / f"{tag}.tgz"
        self.aws("s3", "cp", f"s3://{self.bucket}/releases/{tag}.tgz", str(archive))
        target.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive) as tar:
            tar.extractall(target, filter="data")
        archive.unlink()
        return target

    def compose(self, release: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return run(
            "docker",
            "compose",
            "-p",
            "parksmart",
            "--project-directory",
            str(ROOT),
            "--env-file",
            str(ROOT / ".env"),
            "--env-file",
            str(DEPLOY_ENV),
            "-f",
            str(release / "docker-compose.prod.yml"),
            *args,
            check=check,
        )

    def start(self, tag: str, release: Path) -> None:
        DEPLOY_ENV.write_text(
            f"IMAGE={self.registry}/{self.repository}:{tag}\nRELEASE_DIR={release}\n", encoding="utf-8"
        )
        password = self.aws("ecr", "get-login-password")
        run("docker", "login", "--username", "AWS", "--password-stdin", self.registry, input_text=password)
        self.compose(release, "pull", "--quiet")
        migrate = (
            "if command -v alembic >/dev/null 2>&1 && [ -f alembic.ini ]; "
            "then alembic upgrade head; else echo 'no alembic in image, skip migrations'; fi"
        )
        self.compose(release, "up", "-d", "--wait", "--wait-timeout", "120", "postgres", "redis")
        self.compose(release, "run", "--rm", "--no-deps", "api", "sh", "-c", migrate)
        self.compose(release, "up", "-d", "--wait", "--wait-timeout", "180", "--remove-orphans")

    def healthy(self, site: str) -> bool:
        url = f"https://{site}/api/v1/health"
        for _ in range(HEALTH_TRIES):
            try:
                with urllib.request.urlopen(url, timeout=5) as resp:
                    if resp.status == 200:
                        log(f"health OK: {url}")
                        return True
            except (urllib.error.URLError, OSError) as exc:
                log(f"health not ready: {exc}")
            time.sleep(HEALTH_WAIT_S)
        return False


def self_update(release: Path) -> None:
    """Install the release's own scripts and units so the next run uses them."""
    changed_units = False
    for name in ("deploy.py", "backup.py"):
        src, dst = release / name, BIN / name
        if src.exists() and (not dst.exists() or not filecmp.cmp(src, dst, shallow=False)):
            shutil.copy2(src, dst)
            dst.chmod(0o755)
    for src in (release / "systemd").glob("parksmart-*"):
        dst = SYSTEMD / src.name
        if not dst.exists() or not filecmp.cmp(src, dst, shallow=False):
            shutil.copy2(src, dst)
            changed_units = True
    if changed_units:
        run("systemctl", "daemon-reload")


def prune(current: str, previous: str) -> None:
    keep = {current, previous}
    dirs = sorted((p for p in RELEASES.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in dirs[KEEP_RELEASES:]:
        if old.name not in keep:
            shutil.rmtree(old)
    run("docker", "image", "prune", "-f", check=False)


def main() -> int:
    for path in (RELEASES, STATE, BIN):
        path.mkdir(parents=True, exist_ok=True)
    lock = (STATE / "deploy.lock").open("w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log("another deploy is running")
        return 0

    deployer = Deployer(read_kv(CONF))
    site = read_kv(ROOT / ".env").get("SITE_ADDRESS", "")
    if not site:
        log("SITE_ADDRESS missing in /opt/parksmart/.env; fill .env first")
        return 1

    tag = deployer.target_tag()
    current = read_state("current")
    failed = read_state("failed").split()
    if not tag or tag == current or tag in failed:
        return 0

    log(f"deploying {tag} (current: {current or 'none'})")
    release = deployer.fetch_release(tag)
    try:
        deployer.start(tag, release)
        ok = deployer.healthy(site)
    except subprocess.CalledProcessError as exc:
        log(f"command failed: {exc.stderr.strip()[-2000:]}")
        ok = False

    if ok:
        write_state("previous", current)
        write_state("current", tag)
        self_update(release)
        prune(tag, current)
        log(f"deployed {tag}")
        return 0

    write_state("failed", " ".join([*failed[-9:], tag]))
    log(f"deploy {tag} failed; rolling back to {current or 'nothing'}")
    if current:
        deployer.start(current, RELEASES / current)
        if not deployer.healthy(site):
            log("rollback is unhealthy too; check `journalctl -u parksmart-deploy`")
    return 1


if __name__ == "__main__":
    sys.exit(main())
