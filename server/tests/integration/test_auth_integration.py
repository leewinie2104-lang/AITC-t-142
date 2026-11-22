"""Login + GET /me use cases against a real Postgres holding the schema and the demo seed (SCRUM-86).

Needs ``TEST_DATABASE_URL`` and ``SEED_DEMO_PASSWORD`` (the password the DB was seeded with). Everything runs in one
transaction as the non-owner role ``parksmart_app`` (RLS enforced) and is rolled back.
"""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

import asyncpg
import pytest
import pytest_asyncio
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.eligibility.infrastructure.postgres.repository import PostgresEligibilityRepository
from app.identity.domain.errors import AccountLockedError, InvalidCredentialsError
from app.identity.infrastructure.postgres.repository import PostgresUserRepository
from app.identity.usecase.get_me import GetMe, GetMeInput
from app.identity.usecase.login import Login, LoginInput
from app.platform.auth.tokens import TokenService
from app.platform.db.session import _apply_rls_context

pytestmark = pytest.mark.integration

DSN = os.environ.get("TEST_DATABASE_URL", "")
if not DSN:
    pytest.skip("TEST_DATABASE_URL not set", allow_module_level=True)

PASSWORD = os.environ.get("SEED_DEMO_PASSWORD", "")
LAN_PHONE = "0901000001"  # +84901000001


@pytest.fixture(scope="module")
def tokens() -> TokenService:
    key = ec.generate_private_key(ec.SECP256R1())
    private = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    public = (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    return TokenService(private, public, ttl_minutes=15)


@pytest_asyncio.fixture
async def conn() -> AsyncIterator[asyncpg.Connection]:
    if not PASSWORD:
        pytest.skip("SEED_DEMO_PASSWORD not set")
    c = await asyncpg.connect(DSN)
    tx = c.transaction()
    await tx.start()
    try:
        if not await c.fetchval("SELECT 1 FROM pg_roles WHERE rolname = 'parksmart_app'"):
            pytest.skip("role parksmart_app not present")
        if not await c.fetchval("SELECT 1 FROM app.app_user WHERE phone_e164 = '+84901000001'"):
            pytest.skip("demo seed not loaded")
        await c.execute("SET LOCAL ROLE parksmart_app")
        yield c
    finally:
        await tx.rollback()
        await c.close()


def _uow_on(conn: asyncpg.Connection):
    """Same RLS context as unit_of_work, but on the test's single rolled-back transaction."""

    @asynccontextmanager
    async def uow(user_id: UUID | None = None, role: str = "resident", zone_ids: list[UUID] | None = None) -> Any:
        await _apply_rls_context(conn, user_id, role, zone_ids)
        yield conn

    return uow


async def test_login_as_seeded_lan_then_get_me_returns_her_zone_a_eligibility(conn, tokens) -> None:
    uow = _uow_on(conn)
    result = await Login(PostgresUserRepository(), tokens, uow=uow).execute(LoginInput(LAN_PHONE, PASSWORD))
    claims = tokens.verify(result.access_token)
    user_id = UUID(str(claims["sub"]))

    me = await GetMe(PostgresUserRepository(), PostgresEligibilityRepository(), uow=uow).execute(
        GetMeInput(user_id, str(claims["role"]), [])
    )

    zone_a = await conn.fetchval("SELECT id FROM app.zone WHERE code = 'A'")
    assert me.user.phone_e164 == "+84901000001"
    assert any(e.zone_id == zone_a and e.active for e in me.eligibilities)


async def test_fifth_wrong_password_locks_account_even_for_the_correct_password(conn, tokens) -> None:
    login = Login(PostgresUserRepository(), tokens, uow=_uow_on(conn))

    for _ in range(5):
        with pytest.raises(InvalidCredentialsError):
            await login.execute(LoginInput(LAN_PHONE, "definitely-wrong"))

    locked = await conn.fetchval("SELECT locked_until > now() FROM app.app_user WHERE phone_e164 = '+84901000001'")
    assert locked is True
    with pytest.raises(AccountLockedError):
        await login.execute(LoginInput(LAN_PHONE, PASSWORD))
