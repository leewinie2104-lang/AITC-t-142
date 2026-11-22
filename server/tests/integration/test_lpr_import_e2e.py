"""Full HTTP path of the N1 gate-log import against a real Postgres (SCRUM-109).

Needs ``TEST_DATABASE_URL`` (app role, RLS active), ``SEED_DEMO_PASSWORD`` and the same ``PLATE_ENC_KEY`` /
``PLATE_HASH_KEY`` the demo seed used, with the seed run on the same local day (the demo day is tomorrow).
Facts are read with ``TEST_ADMIN_DATABASE_URL`` (falls back to the app DSN, which is a superuser in CI).
"""

import io
import os
from collections.abc import AsyncIterator
from datetime import datetime, timedelta

import asyncpg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main_api import create_app
from app.platform.config.settings import Settings
from app.platform.db.session import close_db_pool, init_db_pool
from demo_seed.data import ICT
from demo_seed.ids import demo_id
from demo_seed.lpr_csv import build_rows, write_csv

pytestmark = pytest.mark.integration

DSN = os.environ.get("TEST_DATABASE_URL", "")
ADMIN_DSN = os.environ.get("TEST_ADMIN_DATABASE_URL", DSN)
PASSWORD = os.environ.get("SEED_DEMO_PASSWORD", "")
ENC_KEY = os.environ.get("PLATE_ENC_KEY", "")
HASH_KEY = os.environ.get("PLATE_HASH_KEY", "")
if not (DSN and PASSWORD and ENC_KEY and HASH_KEY):
    pytest.skip(
        "TEST_DATABASE_URL, SEED_DEMO_PASSWORD, PLATE_ENC_KEY, PLATE_HASH_KEY required", allow_module_level=True
    )

URL = "/api/v1/dev/lpr-events/import"


async def _reset_gate_state() -> None:
    """Make the test rerunnable on one seeded DB: forget earlier imports and the check-in/out they caused."""
    conn = await asyncpg.connect(ADMIN_DSN)
    try:
        async with conn.transaction():
            await conn.execute("DELETE FROM app.lpr_event WHERE source_code LIKE 'cam-%'")
            await conn.execute(
                "UPDATE app.booking SET checked_in_at = NULL, checked_out_at = NULL WHERE id = $1",
                demo_id("booking", "b_today"),
            )
            await conn.execute(
                "UPDATE app.share_window SET owner_exited_at = NULL WHERE id = ANY($1::uuid[])",
                [demo_id("share_window", k) for k in ("a_today", "c_today")],
            )
    finally:
        await conn.close()


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    settings = Settings(
        _env_file=None, app_env="test", database_url=DSN, plate_enc_key=ENC_KEY, plate_hash_key=HASH_KEY
    )
    await _reset_gate_state()
    app = create_app(settings)
    await init_db_pool(DSN)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        try:
            yield c
        finally:
            await close_db_pool()


async def _facts() -> dict[str, datetime | None]:
    conn = await asyncpg.connect(ADMIN_DSN)
    try:
        b = await conn.fetchrow(
            "SELECT checked_in_at, checked_out_at FROM app.booking WHERE id = $1", demo_id("booking", "b_today")
        )
        win = {
            k: await conn.fetchval(
                "SELECT owner_exited_at FROM app.share_window WHERE id = $1", demo_id("share_window", k)
            )
            for k in ("a_today", "c_today")
        }
    finally:
        await conn.close()
    return {"in": b["checked_in_at"], "out": b["checked_out_at"], **win}


async def test_bql_a_imports_demo_day_then_reimport_is_all_duplicates(client) -> None:
    day = datetime.now(ICT).date() + timedelta(days=1)
    rows = build_rows(day)
    rows_a = [r for r in rows if r["zone_code"] == "A"]
    one_b = next(r for r in rows if r["zone_code"] == "B")
    buf = io.StringIO()
    write_csv(rows_a + [one_b], buf)
    csv_text = buf.getvalue()

    login = await client.post("/api/v1/auth/login", json={"phone": "+84902000001", "password": PASSWORD})
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}", "Content-Type": "text/csv"}

    first = await client.post(URL, content=csv_text.encode(), headers=headers)

    assert first.status_code == 200, first.text
    rep = first.json()
    assert rep["received"] == len(rows_a) + 1
    assert rep["inserted"] > 0 and rep["duplicate"] == 1 and rep["pending_review"] > 0
    assert [r["reason"] for r in rep["rejected"]] == ["zone not permitted for caller"]  # BQL A may not import zone B
    facts = await _facts()
    assert facts["in"] is not None and facts["out"] is not None  # b_today: checked in and out
    assert facts["c_today"] is not None  # anh_c drove out of his slot at 08:05
    assert facts["a_today"] is None  # chi_a's car never leaves in the pilot timeline

    second = await client.post(URL, content=csv_text.encode(), headers=headers)

    rep2 = second.json()
    assert second.status_code == 200
    assert rep2["inserted"] == 0 and rep2["duplicate"] == len(rows_a)
    assert await _facts() == facts
