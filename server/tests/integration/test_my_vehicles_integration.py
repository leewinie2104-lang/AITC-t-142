"""ListMyVehicles repository against real Postgres with RLS (SCRUM-88).

Needs ``TEST_DATABASE_URL`` (schema + demo seed loaded). One rolled-back transaction, queries run as the non-owner
role ``parksmart_app``.
"""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

import asyncpg
import pytest
import pytest_asyncio

from app.facility.infrastructure.postgres.repository import PostgresVehicleRepository
from app.facility.usecase.list_my_vehicles import ListMyVehicles, ListMyVehiclesInput
from app.platform.db.session import _apply_rls_context
from demo_seed.ids import demo_id

pytestmark = pytest.mark.integration

DSN = os.environ.get("TEST_DATABASE_URL", "")
if not DSN:
    pytest.skip("TEST_DATABASE_URL not set", allow_module_level=True)

BINH = demo_id("user", "binh")
KHACH = demo_id("user", "khach")


@pytest_asyncio.fixture
async def conn() -> AsyncIterator[asyncpg.Connection]:
    c = await asyncpg.connect(DSN)
    tx = c.transaction()
    await tx.start()
    try:
        if not await c.fetchval("SELECT 1 FROM pg_roles WHERE rolname = 'parksmart_app'"):
            pytest.skip("role parksmart_app not present")
        if not await c.fetchval("SELECT 1 FROM app.vehicle WHERE user_id = $1", BINH):
            pytest.skip("demo seed not loaded")
        yield c
    finally:
        await tx.rollback()
        await c.close()


def _list_use_case(conn: asyncpg.Connection) -> ListMyVehicles:
    @asynccontextmanager
    async def uow(user_id: UUID | None = None, role: str = "resident", zone_ids: list[UUID] | None = None) -> Any:
        await _apply_rls_context(conn, user_id, role, zone_ids)
        yield conn

    return ListMyVehicles(PostgresVehicleRepository(), uow=uow)


async def test_resident_sees_own_two_vehicles_masked_and_ordered(conn) -> None:
    await conn.execute("SET LOCAL ROLE parksmart_app")

    vehicles = await _list_use_case(conn).execute(ListMyVehiclesInput(BINH, "resident", []))

    assert sorted(v.plate_masked for v in vehicles) == ["29C-•••.99", "30A-•••.22"]
    keys = [(v.created_at, v.id) for v in vehicles]
    assert keys == sorted(keys)


async def test_soft_deleted_vehicle_is_hidden(conn) -> None:
    await conn.execute(
        "UPDATE app.vehicle SET is_active = false WHERE id = "
        "(SELECT id FROM app.vehicle WHERE user_id = $1 ORDER BY id LIMIT 1)",
        BINH,
    )
    await conn.execute("SET LOCAL ROLE parksmart_app")

    vehicles = await _list_use_case(conn).execute(ListMyVehiclesInput(BINH, "resident", []))

    assert len(vehicles) == 1


async def test_owner_filter_holds_when_rls_lets_every_row_through(conn) -> None:
    await conn.execute("SET LOCAL ROLE parksmart_app")

    vehicles = await _list_use_case(conn).execute(ListMyVehiclesInput(KHACH, "system", []))

    assert [v.plate_masked for v in vehicles] == ["29H-•••.66"]
