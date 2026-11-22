"""Fail when the Alembic head and ``docs/03-design/sql/schema.sql`` describe different schemas (SCRUM-205, plan 026).

    python server/scripts/check_schema_drift.py --migrated DSN --reference DSN [--build-reference SQL] [--docker NAME]

``--migrated`` is a database at ``alembic upgrade head``; ``--reference`` is an empty database on the same cluster.
``--build-reference`` first applies the given SQL file to the reference database with ``psql``. Both databases are
dumped with ``pg_dump --schema-only`` (``alembic_version`` excluded), lines that differ between any two dumps
(comments, ``SET``, ``\\restrict`` keys) are dropped, column order inside a table is ignored (see
``_sort_table_bodies``), and a unified diff is printed on drift (exit 1).

``--docker NAME`` runs ``psql`` / ``pg_dump`` inside that container, so their version matches the server and nothing
needs to be installed on the host; the DSNs must then be valid from inside the container (port 5432, not the mapped one).
DSNs may carry a throwaway password: they are passed as arguments and never printed.
"""

from __future__ import annotations

import argparse
import difflib
import subprocess
import sys
from pathlib import Path

# pg_dump output that is not schema: header comments, session settings, the per-dump random \restrict key (pg 16.10+).
NOISE_PREFIXES = ("--", "SET ", "SELECT pg_catalog.set_config(", "\\restrict ", "\\unrestrict ")
MAX_DIFF_LINES = 200


def _tool(docker: str | None, *args: str, interactive: bool = False) -> list[str]:
    if docker is None:
        return list(args)
    return ["docker", "exec", *(["-i"] if interactive else []), docker, *args]


def build_reference(dsn: str, sql_file: Path, docker: str | None) -> None:
    cmd = _tool(docker, "psql", "-d", dsn, "-v", "ON_ERROR_STOP=1", "-q", interactive=True)
    with sql_file.open("rb") as stdin:
        result = subprocess.run(cmd, stdin=stdin, capture_output=True, check=False)
    if result.returncode != 0:
        sys.exit(f"applying {sql_file} failed:\n{result.stderr.decode('utf-8', 'replace')}")


def dump_schema(dsn: str, docker: str | None) -> list[str]:
    cmd = _tool(docker, "pg_dump", "--schema-only", "--exclude-table=public.alembic_version", "-d", dsn)
    result = subprocess.run(cmd, capture_output=True, check=False)
    if result.returncode != 0:
        sys.exit(f"pg_dump failed:\n{result.stderr.decode('utf-8', 'replace')}")
    lines = result.stdout.decode("utf-8").splitlines()
    return _sort_table_bodies([line for line in lines if line.strip() and not line.startswith(NOISE_PREFIXES)])


def _sort_table_bodies(lines: list[str]) -> list[str]:
    """Sort the column / constraint lines inside each CREATE TABLE.

    Column order is not schema drift: ``ALTER TABLE ... ADD COLUMN`` in a migration always appends, while schema.sql
    declares the column where it reads best, and Postgres cannot reorder columns without rebuilding the table.
    Trailing commas are dropped so the item that happens to be last compares equal. A multi-line item (a generated
    column) is split across sorted lines, but identically on both sides, so it still compares correctly.
    """
    out: list[str] = []
    body: list[str] | None = None
    for line in lines:
        if body is None:
            out.append(line)
            if line.startswith("CREATE TABLE ") and line.endswith("("):
                body = []
        elif line.startswith(")"):  # ");" or ") PARTITION BY ..." closes the table
            out.extend(sorted(body))
            out.append(line)
            body = None
        else:
            body.append(line.rstrip(","))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--migrated", required=True, help="DSN of the database at alembic head")
    parser.add_argument("--reference", required=True, help="DSN of the database built from schema.sql")
    parser.add_argument("--build-reference", type=Path, metavar="SQL", help="apply this file to --reference first")
    parser.add_argument("--docker", metavar="CONTAINER", help="run psql / pg_dump inside this container")
    args = parser.parse_args()

    if args.build_reference is not None:
        build_reference(args.reference, args.build_reference, args.docker)

    migrated = dump_schema(args.migrated, args.docker)
    reference = dump_schema(args.reference, args.docker)
    if migrated == reference:
        print(f"schema drift: none ({len(migrated)} DDL lines identical)")
        return 0

    diff = list(difflib.unified_diff(reference, migrated, "schema.sql", "alembic head", lineterm=""))
    print("schema drift: alembic head differs from schema.sql (- schema.sql, + migrations)")
    print("\n".join(diff[:MAX_DIFF_LINES]))
    if len(diff) > MAX_DIFF_LINES:
        print(f"... {len(diff) - MAX_DIFF_LINES} more diff lines")
    print(
        "Fix: add a migration for the change, or update schema.sql to match (docs/06-operations/01-database-operations.md)"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
