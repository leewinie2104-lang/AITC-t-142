#!/usr/bin/env python3
"""Nightly pg_dump of the prod database to S3 (ADR-0012).

Run by parksmart-backup.timer as root. Streams `pg_dump -Fc` from the postgres container straight
to s3://<bucket>/backups/parksmart-<UTC timestamp>.dump; an S3 lifecycle rule deletes it after 7 days.
Restore steps are in infra/lightsail/README.md.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

CONF = Path("/etc/parksmart/deploy.conf")


def read_kv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def main() -> int:
    conf = read_kv(CONF)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    key = f"s3://{conf['RELEASE_BUCKET']}/backups/parksmart-{stamp}.dump"

    # Find the running postgres container by compose labels so no compose file is needed here.
    container = subprocess.run(
        [
            "docker",
            "ps",
            "-q",
            "--filter",
            "label=com.docker.compose.project=parksmart",
            "--filter",
            "label=com.docker.compose.service=postgres",
        ],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    if not container:
        print("postgres container is not running", flush=True)
        return 1

    dump = subprocess.Popen(
        ["docker", "exec", container, "pg_dump", "-U", "parksmart", "-d", "parksmart", "-Fc"],
        stdout=subprocess.PIPE,
    )
    upload = subprocess.run(
        ["aws", "--region", conf["AWS_REGION"], "s3", "cp", "-", key, "--only-show-errors"],
        stdin=dump.stdout,
        check=False,
    )
    if dump.stdout is not None:
        dump.stdout.close()
    dump_rc = dump.wait()
    if dump_rc != 0 or upload.returncode != 0:
        print(f"backup failed: pg_dump={dump_rc} upload={upload.returncode}", flush=True)
        return 1
    print(f"backup uploaded: {key}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
