"""Access REST: auth, role gate, header check, pass-through, and no dev import route in production (SCRUM-109)."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
import pytest_asyncio
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.access.delivery.rest.router import HEADER, create_access_router
from app.access.domain.entity import IngestReport, Rejection
from app.main_api import create_app
from app.platform.auth.dependency import make_current_user
from app.platform.auth.tokens import TokenService
from app.platform.config.settings import Settings

URL = "/api/v1/dev/lpr-events/import"
GOOD_CSV = ",".join(HEADER) + "\ncam-a-in,e1,A,G1,in,2026-05-01T08:00:00+07:00,30A-123.45,0.95\n"
ZONE = uuid4()


@pytest_asyncio.fixture
async def ctx():
    tokens = TokenService.from_settings(Settings(_env_file=None, app_env="test"))
    ingest = MagicMock()
    ingest.execute = AsyncMock(return_value=IngestReport(received=1, inserted=1, rejected=[Rejection(2, "x")]))
    app = FastAPI()
    app.include_router(create_access_router(ingest, make_current_user(tokens)))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c, tokens, ingest


def _auth(tokens: TokenService, role: str) -> dict[str, str]:
    token, _ = tokens.issue(uuid4(), role, [ZONE])
    return {"Authorization": f"Bearer {token}", "Content-Type": "text/csv"}


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer garbage"}], ids=["no-token", "bad-token"])
async def test_import_without_valid_token_is_401(ctx, headers) -> None:
    c, _, ingest = ctx

    resp = await c.post(URL, content=GOOD_CSV, headers=headers)

    assert resp.status_code == 401
    ingest.execute.assert_not_awaited()


async def test_resident_cannot_import_403(ctx) -> None:
    c, tokens, ingest = ctx

    resp = await c.post(URL, content=GOOD_CSV, headers=_auth(tokens, "resident"))

    assert resp.status_code == 403
    ingest.execute.assert_not_awaited()


async def test_wrong_csv_header_is_422(ctx) -> None:
    c, tokens, _ = ctx

    resp = await c.post(URL, content="a,b,c\n1,2,3\n", headers=_auth(tokens, "zone_manager"))

    assert resp.status_code == 422 and resp.json()["detail"] == "bad_header"


async def test_zone_manager_report_passes_through_limited_to_own_zones(ctx) -> None:
    c, tokens, ingest = ctx

    resp = await c.post(URL, content=GOOD_CSV, headers=_auth(tokens, "zone_manager"))

    assert resp.status_code == 200
    assert resp.json()["inserted"] == 1 and resp.json()["rejected"][0]["line"] == 2
    inp = ingest.execute.await_args.args[0]
    assert inp.allowed_zone_ids == [ZONE] and inp.rows[0].line == 2


async def test_production_app_has_no_dev_lpr_import_route() -> None:
    key = ec.generate_private_key(ec.SECP256R1())
    private = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    public = (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )

    app = create_app(Settings(_env_file=None, app_env="production", jwt_private_key=private, jwt_public_key=public))

    assert URL not in {getattr(r, "path", "") for r in app.routes}
