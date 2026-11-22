"""Every static SQL string in the repositories must PREPARE against the schema built by the migrations.

Unit tests use fake ports, so a renamed column (``due_at`` -> ``bql_deadline_at`` in v7) or an ambiguous parameter
type only fails at runtime. ``PREPARE`` parses and analyses a statement without running it, which catches unknown
tables / columns / enum literals and parameter type conflicts. Needs ``TEST_DATABASE_URL``; skipped otherwise.
"""

import ast
import os
import re
from pathlib import Path

import asyncpg
import pytest

pytestmark = pytest.mark.integration

DSN = os.environ.get("TEST_DATABASE_URL", "")
if not DSN:
    pytest.skip("TEST_DATABASE_URL not set", allow_module_level=True)

APP_DIR = Path(__file__).resolve().parents[2] / "src" / "app"
SQL_START = re.compile(r"^\s*(WITH|SELECT|INSERT|UPDATE|DELETE)\b", re.IGNORECASE)


def _statements() -> list[tuple[str, str]]:
    """(``path:line``, sql) for each string constant in an infrastructure module that starts like a statement."""
    found = []
    for path in sorted(APP_DIR.glob("*/infrastructure/**/*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and SQL_START.match(node.value):
                found.append((f"{path.relative_to(APP_DIR)}:{node.lineno}", node.value))
    return found


STATEMENTS = _statements()


def test_statements_were_found() -> None:
    assert len(STATEMENTS) > 20, "the SQL scan found too few statements; did the repository layout change?"


@pytest.mark.parametrize(("where", "sql"), STATEMENTS, ids=[w for w, _ in STATEMENTS])
async def test_statement_prepares(where: str, sql: str) -> None:
    conn = await asyncpg.connect(DSN)
    try:
        await conn.prepare(sql)
    except asyncpg.PostgresError as exc:
        pytest.fail(f"{where}: {type(exc).__name__}: {exc}")
    finally:
        await conn.close()
