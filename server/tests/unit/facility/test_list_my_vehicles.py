"""GET /api/v1/me/vehicles: auth gate and response shape (SCRUM-88, BR-09)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.facility.delivery.rest.router import create_facility_router
from app.facility.domain.entity import VehicleView
from app.platform.auth.dependency import make_current_user
from app.platform.auth.tokens import TokenService
from app.platform.config.settings import Settings


@pytest_asyncio.fixture
async def tokens_and_client():
    tokens = TokenService.from_settings(Settings(_env_file=None, app_env="test"))
    use_case = MagicMock()
    use_case.execute = AsyncMock(
        return_value=[VehicleView(id=uuid4(), plate_masked="30A-•••.22", size_class="M", created_at=datetime.now(UTC))]
    )
    app = FastAPI()
    app.include_router(create_facility_router(use_case, make_current_user(tokens)))
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    yield tokens, client
    await client.aclose()


async def test_my_vehicles_without_token_is_401(tokens_and_client) -> None:
    _, client = tokens_and_client

    resp = await client.get("/api/v1/me/vehicles")

    assert resp.status_code == 401


async def test_my_vehicles_exposes_only_masked_fields_br09(tokens_and_client) -> None:
    tokens, client = tokens_and_client
    token, _ = tokens.issue(uuid4(), "resident", [])

    resp = await client.get("/api/v1/me/vehicles", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert set(items[0]) == {"id", "plate_masked", "size_class", "created_at"}
