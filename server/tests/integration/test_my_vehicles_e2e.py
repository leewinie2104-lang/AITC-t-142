"""Full HTTP path: login then GET /me/vehicles against a real Postgres (SCRUM-88).

Needs ``TEST_DATABASE_URL`` and ``SEED_DEMO_PASSWORD``. Connects as the DB user in the URL (RLS is covered by
test_my_vehicles_integration.py).
"""

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main_api import create_app
from app.platform.config.settings import Settings
from app.platform.db.session import close_db_pool, init_db_pool

pytestmark = pytest.mark.integration

DSN = os.environ.get("TEST_DATABASE_URL", "")
PASSWORD = os.environ.get("SEED_DEMO_PASSWORD", "")
if not DSN or not PASSWORD:
    pytest.skip("TEST_DATABASE_URL and SEED_DEMO_PASSWORD required", allow_module_level=True)


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    app = create_app(Settings(_env_file=None, app_env="test", database_url=DSN))
    # The global pool reads get_settings() (env), not the Settings passed to create_app, so point it at the test DB.
    await init_db_pool(DSN)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        try:
            yield c
        finally:
            await close_db_pool()  # the pool is a process global; do not leak it into other tests


async def test_login_then_list_my_vehicles_returns_masked_plates_only(client) -> None:
    login = await client.post("/api/v1/auth/login", json={"phone": "+84901000002", "password": PASSWORD})
    assert login.status_code == 200
    token = login.json()["access_token"]

    resp = await client.get("/api/v1/me/vehicles", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    assert sorted(v["plate_masked"] for v in resp.json()) == ["29C-•••.99", "30A-•••.22"]
    assert "30A22222" not in resp.text
    assert "29C99999" not in resp.text
