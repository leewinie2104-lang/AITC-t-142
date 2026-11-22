"""Schema v7 at head on a real Postgres: RLS zone isolation, append-only logs, least privilege (ADR-0005, schema §20-§21).

Needs ``TEST_DATABASE_URL`` (a superuser or owner connection that may ``SET ROLE parksmart_app``); skipped otherwise.
The demo rows come from ``demo_seed.write_demo_data`` and are written by the owner connection, so RLS does not apply to
the fixture. Every probe runs as ``parksmart_app`` under the context set by the production ``unit_of_work`` inside a
savepoint that is rolled back, and the whole test is rolled back: the database is left unchanged.
"""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

import asyncpg
import pytest
import pytest_asyncio
from argon2 import PasswordHasher

from app.platform.crypto.plate_cipher import PlateCipher
from app.platform.db.session import unit_of_work
from demo_seed.data import build_demo_data
from demo_seed.ids import demo_id
from demo_seed.writer import write_demo_data

pytestmark = pytest.mark.integration

DSN = os.environ.get("TEST_DATABASE_URL", "")
if not DSN:
    pytest.skip("TEST_DATABASE_URL not set", allow_module_level=True)

_DATA = build_demo_data()
ZONE_A: UUID = next(z.id for z in _DATA.zones if z.code == "A")
ZONE_B: UUID = next(z.id for z in _DATA.zones if z.code == "B")
ZONE_C: UUID = next(z.id for z in _DATA.zones if z.code == "C")
LAN: UUID = _DATA.user("lan").id

# Zone-owned tables readable only by the zone's staff (zone_staff policies, schema §20.1 / §20.3), each with a
# foreign zone that actually holds rows in the demo seed (slot_holding has none in zone B).
FOREIGN_ZONE_BY_TABLE = {
    "asset": ZONE_B,
    "eligibility": ZONE_B,
    "slot_holding": ZONE_C,
    "bql_registry_import": ZONE_B,
}
ZONE_SCOPED_TABLES = list(FOREIGN_ZONE_BY_TABLE)
# Holder-scoped tables: a resident sees the rows of the user_id in the session (holder_read, schema §20.3).
HOLDER_SCOPED_TABLES = ["eligibility", "slot_holding"]


@pytest_asyncio.fixture
async def conn() -> AsyncIterator[asyncpg.Connection]:
    """Owner connection inside a transaction: demo rows + one registry line per zone, all rolled back at the end."""
    c = await asyncpg.connect(DSN)
    tx = c.transaction()
    await tx.start()
    try:
        if await c.fetchval("SELECT to_regclass('app.bql_registry_import') IS NULL"):
            pytest.fail("schema is not at head: app.bql_registry_import is missing (run alembic upgrade head)")
        cipher = PlateCipher(enc_key=os.urandom(32), hash_key=os.urandom(32), key_version=1)
        await write_demo_data(c, _DATA, cipher, PasswordHasher().hash("rls-probe-password"))
        for code, zone_id in (("A", ZONE_A), ("B", ZONE_B)):
            await c.execute(
                "INSERT INTO app.bql_registry_import (zone_id, batch_id, line_no, role, full_name, unit_code)"
                " VALUES ($1, $2, 1, 'resident', $3, $4)",
                zone_id,
                demo_id("rls-probe-batch", code),
                f"Probe {code}",
                f"RLS-{code}",
            )
        yield c
    finally:
        await tx.rollback()
        await c.close()


@asynccontextmanager
async def as_app(
    conn: asyncpg.Connection,
    *,
    role: str,
    user_id: UUID | None = None,
    zone_ids: list[UUID] | None = None,
) -> AsyncIterator[asyncpg.Connection]:
    """Run the block as parksmart_app with the RLS context of the production unit_of_work; roll back afterwards.

    ``role=""`` sets no context at all (fail-closed check). The savepoint also reverts ``SET LOCAL ROLE``.
    """
    sp = conn.transaction()
    await sp.start()
    try:
        await conn.execute("SET LOCAL ROLE parksmart_app")
        # The seed fixture's set_config(..., true) lasts for the whole outer transaction, so reset every setting
        # first: an absent context must mean "no access", not whatever the owner wrote earlier.
        await conn.execute(
            "SELECT set_config('app.user_id', '', true), set_config('app.role', '', true),"
            " set_config('app.zone_ids', '', true)"
        )
        async with unit_of_work(conn, user_id=user_id, role=role, zone_ids=zone_ids) as uow_conn:
            yield uow_conn
    finally:
        await sp.rollback()


async def _count(c: asyncpg.Connection, table: str, where: str, *args: object) -> int:
    # `table` and `where` come from the constants in this module, never from user input.
    return int(await c.fetchval(f"SELECT count(*) FROM app.{table} WHERE {where}", *args))


# ---------------------------------------------------------------------------------------------------------------------
# Zone isolation (RLS, schema §20)
# ---------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("table", ZONE_SCOPED_TABLES)
async def test_zone_a_bql_cannot_read_other_zone_rows(conn, table) -> None:
    """ADR-0005: a zone_manager of zone A sees no row of the foreign zone. Positive controls: rows exist, A is visible."""
    foreign = FOREIGN_ZONE_BY_TABLE[table]
    assert await _count(conn, table, "zone_id = $1", foreign) > 0
    async with as_app(conn, role="zone_manager", zone_ids=[ZONE_A]) as c:
        assert await _count(c, table, "zone_id = $1", foreign) == 0
        assert await _count(c, table, "zone_id = $1", ZONE_A) > 0


@pytest.mark.parametrize("table", HOLDER_SCOPED_TABLES)
async def test_resident_of_zone_a_sees_only_own_holdings(conn, table) -> None:
    """A resident (lan, zone A) reads her own eligibility / holdings; other holders in the foreign zone stay invisible."""
    foreign = FOREIGN_ZONE_BY_TABLE[table]
    assert await _count(conn, table, "zone_id = $1 AND user_id <> $2", foreign, LAN) > 0
    async with as_app(conn, role="resident", user_id=LAN) as c:
        assert await _count(c, table, "zone_id = $1 AND user_id <> $2", foreign, LAN) == 0
        assert await _count(c, table, "user_id = $1", LAN) > 0


@pytest.mark.parametrize("table", ZONE_SCOPED_TABLES)
async def test_session_without_rls_context_reads_nothing(conn, table) -> None:
    """Missing app.role / app.zone_ids resolve to no access, never to all access (schema §0 context functions)."""
    async with as_app(conn, role="") as c:
        assert await _count(c, table, "zone_id IN ($1, $2)", ZONE_A, ZONE_B) == 0


async def test_user_reads_only_own_consent_rows(conn) -> None:
    """consent_record `own` policy (schema §20.9): a resident sees her consent evidence and nobody else's."""
    async with as_app(conn, role="resident", user_id=LAN) as c:
        assert await _count(c, "consent_record", "user_id = $1", LAN) >= 1
        assert await _count(c, "consent_record", "user_id <> $1", LAN) == 0


@pytest.mark.parametrize(
    "table",
    ["consent_record", "ai_decision_log", "bql_registry_import", "asset", "eligibility", "slot_holding", "vehicle"],
)
async def test_rls_is_enabled_on_personal_and_zone_tables(conn, table) -> None:
    assert await conn.fetchval("SELECT relrowsecurity FROM pg_class WHERE oid = to_regclass($1)", f"app.{table}")


async def test_app_role_is_nobypassrls_and_owns_no_table(conn) -> None:
    assert await conn.fetchval("SELECT rolbypassrls FROM pg_roles WHERE rolname = 'parksmart_app'") is False
    assert await _owned_by_app_role(conn) == 0


async def _owned_by_app_role(conn: asyncpg.Connection) -> int:
    return int(
        await conn.fetchval("SELECT count(*) FROM pg_tables WHERE schemaname = 'app' AND tableowner = 'parksmart_app'")
    )


async def test_app_role_cannot_read_plate_ciphertext(conn) -> None:
    """Plates (BR-09, ADR-0005): ciphertext is never selectable by the app role; only masked plate columns are."""
    for statement in ("SELECT plate_ciphertext FROM app.vehicle", "SELECT * FROM app.vehicle"):
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            async with as_app(conn, role="system") as c:
                await c.execute(statement)


# ---------------------------------------------------------------------------------------------------------------------
# Append-only evidence (BR-09, FR-09): consent_record, ai_decision_log
# ---------------------------------------------------------------------------------------------------------------------

APPEND_ONLY_WRITES = [
    pytest.param("UPDATE app.consent_record SET terms_version = 'v2'", id="consent_record-update"),
    pytest.param("DELETE FROM app.consent_record", id="consent_record-delete"),
    pytest.param("TRUNCATE app.consent_record", id="consent_record-truncate"),
    pytest.param("UPDATE app.ai_decision_log SET step = 'tampered'", id="ai_decision_log-update"),
    pytest.param("DELETE FROM app.ai_decision_log", id="ai_decision_log-delete"),
    pytest.param("TRUNCATE app.ai_decision_log", id="ai_decision_log-truncate"),
]


@pytest.mark.parametrize("statement", APPEND_ONLY_WRITES)
async def test_app_role_cannot_update_delete_or_truncate_append_only_tables(conn, statement) -> None:
    """Grant layer (schema §21): even under the `system` context whose RLS policy allows everything, the app role
    has no UPDATE / DELETE / TRUNCATE on the append-only tables."""
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        async with as_app(conn, role="system") as c:
            await c.execute(statement)


# consent_record TRUNCATE is refused by the FK from parking_request.gps_consent_id before the trigger runs, so the
# trigger probe covers UPDATE / DELETE / TRUNCATE on ai_decision_log and UPDATE / DELETE on consent_record.
TRIGGER_WRITES = [w for w in APPEND_ONLY_WRITES if w.id != "consent_record-truncate"]


@pytest.mark.parametrize("statement", TRIGGER_WRITES)
async def test_owner_is_also_stopped_by_append_only_trigger(conn, statement) -> None:
    """Trigger layer (schema reject_mutation): the owner connection cannot mutate the append-only tables either."""
    sp = conn.transaction()
    await sp.start()
    try:
        with pytest.raises(asyncpg.InsufficientPrivilegeError, match="append-only"):
            await conn.execute(statement)
    finally:
        await sp.rollback()


# ---------------------------------------------------------------------------------------------------------------------
# No DDL for the app role (schema §21: DML only, never DDL, TRUNCATE or ownership)
# ---------------------------------------------------------------------------------------------------------------------

DDL_STATEMENTS = [
    pytest.param("CREATE TABLE app.rls_probe (id int)", id="create-table"),
    pytest.param("CREATE SCHEMA rls_probe", id="create-schema"),
    pytest.param("CREATE INDEX rls_probe_idx ON app.zone (name)", id="create-index"),
    pytest.param("ALTER TABLE app.zone ADD COLUMN rls_probe text", id="alter-table"),
    pytest.param("DROP TABLE app.zone", id="drop-table"),
    pytest.param("TRUNCATE app.asset", id="truncate-table"),
    pytest.param("CREATE FUNCTION app.rls_probe() RETURNS int LANGUAGE sql AS 'SELECT 1'", id="create-function"),
    pytest.param("ALTER TABLE app.consent_record DISABLE ROW LEVEL SECURITY", id="disable-rls"),
]


@pytest.mark.parametrize("statement", DDL_STATEMENTS)
async def test_app_role_cannot_run_ddl_even_with_system_context(conn, statement) -> None:
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        async with as_app(conn, role="system") as c:
            await c.execute(statement)
