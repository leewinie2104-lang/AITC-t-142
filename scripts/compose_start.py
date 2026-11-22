"""Start existing docker compose containers one by one, with a pause between starts.

Used by `make start`. Only services whose container already exists in this compose project are started
(created earlier by `make up`); services never created — e.g. a profile that was not enabled — are skipped.
Containers already running are skipped and do not cost a pause. Order follows `depends_on`, so postgres
and redis come up before api and workers.

Usage: python scripts/compose_start.py [--interval 30] [--profile NAME ...] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time


def compose(profiles: list[str], *args: str) -> str:
    cmd = ["docker", "compose"]
    for p in profiles:
        cmd += ["--profile", p]
    cmd += list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        sys.exit(f"Lỗi khi chạy `{' '.join(cmd)}`:\n{result.stderr.strip()}")
    return result.stdout


# Services with a web UI: name -> (label, path). The host port is read from compose `ports`.
WEB_UIS = {
    "api": ("API (Swagger)", "/docs"),
    "pgadmin": ("pgAdmin", ""),
    "redisinsight": ("Redis Insight", ""),
}


def load_services(profiles: list[str]) -> dict:
    return json.loads(compose(profiles, "config", "--format", "json"))["services"]


def service_order(services: dict) -> list[str]:
    """Topological order of services by depends_on; ties keep alphabetical order for stable output."""
    deps = {name: set((svc.get("depends_on") or {}).keys()) for name, svc in services.items()}
    order: list[str] = []
    while deps:
        ready = sorted(name for name, d in deps.items() if not d - set(order))
        if not ready:  # cycle; compose itself rejects these, but never loop forever
            ready = sorted(deps)
        for name in ready:
            order.append(name)
            del deps[name]
    return order


def container_states(profiles: list[str]) -> dict[str, str]:
    """Service -> container state ("running", "exited", ...) for containers that exist."""
    out = compose(profiles, "ps", "--all", "--format", "json").strip()
    if not out:
        return {}
    # Older compose prints one JSON array, newer prints one JSON object per line.
    rows = json.loads(out) if out.startswith("[") else [json.loads(line) for line in out.splitlines() if line]
    return {row["Service"]: row["State"] for row in rows}


def print_links(profiles: list[str], services: dict) -> None:
    """Print a clickable URL for every running service that has a web UI."""
    states = container_states(profiles)
    links = []
    for name, (label, path) in WEB_UIS.items():
        ports = services.get(name, {}).get("ports") or []
        if states.get(name) != "running" or not ports or not ports[0].get("published"):
            continue
        links.append((label, f"http://localhost:{ports[0]['published']}{path}"))
    if links:
        print("\nMở trên trình duyệt:")
        for label, url in links:
            print(f"  {label:<14} {url}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--interval", type=float, default=30, help="giây chờ giữa hai lần start (mặc định 30)")
    parser.add_argument("--profile", action="append", default=[], help="profile compose cần xét, lặp lại được")
    parser.add_argument("--dry-run", action="store_true", help="chỉ in kế hoạch, không start")
    args = parser.parse_args()

    services = load_services(args.profile)
    states = container_states(args.profile)
    plan = [s for s in service_order(services) if s in states]
    if not plan:
        print("Chưa có container nào trong project. Chạy `make up` trước.")
        return

    to_start = [s for s in plan if states[s] != "running"]
    for s in plan:
        if states[s] == "running":
            print(f"  = {s}: đang chạy, bỏ qua")
    if not to_start:
        print("Mọi container đã chạy.")
        print_links(args.profile, services)
        return

    print(f"Sẽ start {len(to_start)} container, cách nhau {args.interval:g}s: {', '.join(to_start)}")
    try:
        for i, service in enumerate(to_start):
            if i:
                print(f"  ... chờ {args.interval:g}s")
                if not args.dry_run:
                    time.sleep(args.interval)
            print(f"  > [{i + 1}/{len(to_start)}] start {service}")
            if not args.dry_run:
                compose(args.profile, "start", service)
    except KeyboardInterrupt:
        sys.exit("\nĐã dừng giữa chừng; container đã start vẫn chạy.")
    print("Xong.")
    if not args.dry_run:
        print_links(args.profile, services)


if __name__ == "__main__":
    main()
