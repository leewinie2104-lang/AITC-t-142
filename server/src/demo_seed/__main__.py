"""Entry point: ``python -m demo_seed [--dry-run]`` (PYTHONPATH must contain ``server/src``; see README).

Runs only when SEED_DEMO=true, so a production deploy can never seed by accident. Safe to re-run.
Logs counts only: no plates, phones or passwords (BR-09).
"""

import argparse
import asyncio
import sys

import asyncpg
from argon2 import PasswordHasher

from app.platform.config.settings import get_settings
from app.platform.crypto.plate_cipher import PlateCipher, PlateCryptoError
from app.platform.db.session import redact_dsn

from .data import build_demo_data
from .writer import Report, write_demo_data


class _DryRunRollbackError(Exception):
    """Raised inside the transaction to roll it back after reporting."""


def _print_report(report: Report) -> None:
    for table, counts in report.items():
        print(
            f"  {table:<15} inserted={counts['inserted']:<3} updated={counts['updated']:<3} "
            f"unchanged={counts['unchanged']:<3}"
        )


async def run(dry_run: bool) -> int:
    settings = get_settings()
    if not settings.seed_demo:
        print("demo seed skipped: SEED_DEMO is not true")
        return 0
    if not settings.seed_demo_password:
        print("SEED_DEMO_PASSWORD must be set (see .env.example)", file=sys.stderr)
        return 2
    try:
        cipher = PlateCipher.from_settings(settings)
    except PlateCryptoError as exc:
        print(f"plate keys: {exc}", file=sys.stderr)
        return 2

    data = build_demo_data()
    # One hash for all accounts: they share a password, and argon2id is deliberately slow.
    password_hash = PasswordHasher().hash(settings.seed_demo_password)

    print(f"seeding {redact_dsn(settings.database_url)}{' (dry run, will roll back)' if dry_run else ''}")
    conn = await asyncpg.connect(settings.database_url)
    try:
        report: Report = {}
        try:
            async with conn.transaction():
                report = await write_demo_data(conn, data, cipher, password_hash)
                if dry_run:
                    raise _DryRunRollbackError
        except _DryRunRollbackError:
            pass
        except (asyncpg.UndefinedTableError, asyncpg.InvalidSchemaNameError):
            print("schema not found: run the migrations first (cd server && alembic upgrade head)", file=sys.stderr)
            return 1
        _print_report(report)
    finally:
        await conn.close()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="demo_seed", description="Seed the 3-zone demo dataset (idempotent).")
    parser.add_argument("--dry-run", action="store_true", help="write inside a transaction, print counts, roll back")
    args = parser.parse_args()
    sys.exit(asyncio.run(run(args.dry_run)))


if __name__ == "__main__":
    main()
