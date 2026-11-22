"""Identity REST mapping: domain errors to HTTP status."""

from unittest.mock import AsyncMock, MagicMock

import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.identity.delivery.rest.router import create_identity_router
from app.identity.domain.errors import AccountLockedError, InvalidCredentialsError
from app.platform.auth.dependency import make_current_user
from app.platform.auth.tokens import TokenService
from app.platform.config.settings import Settings


@pytest_asyncio.fixture
async def make_client():
    clients: list[AsyncClient] = []

    async def _make(login_error: Exception) -> AsyncClient:
        login = MagicMock()
        login.execute = AsyncMock(side_effect=login_error)
        tokens = TokenService.from_settings(Settings(_env_file=None, app_env="test"))
        app = FastAPI()
        app.include_router(create_identity_router(login, MagicMock(), make_current_user(tokens)))
        c = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
        clients.append(c)
        return c

    yield _make
    for c in clients:
        await c.aclose()


async def test_me_without_token_is_401_with_bearer_challenge(make_client) -> None:
    client = await make_client(InvalidCredentialsError())

    resp = await client.get("/api/v1/me")

    assert resp.status_code == 401
    assert resp.headers["www-authenticate"] == "Bearer"


async def test_login_locked_account_is_423_with_retry_after(make_client) -> None:
    client = await make_client(AccountLockedError(321))

    resp = await client.post("/api/v1/auth/login", json={"phone": "0901000001", "password": "x"})

    assert resp.status_code == 423
    assert resp.headers["retry-after"] == "321"


async def test_login_invalid_credentials_is_401_generic_body(make_client) -> None:
    client = await make_client(InvalidCredentialsError())

    resp = await client.post("/api/v1/auth/login", json={"phone": "0901000001", "password": "x"})

    assert resp.status_code == 401
    assert resp.json() == {"detail": "invalid_credentials"}
