"""Login use case (SCRUM-86) with an in-memory repo and a real TokenService."""

from contextlib import asynccontextmanager
from dataclasses import replace
from typing import Any
from uuid import UUID, uuid4

import pytest
from argon2 import PasswordHasher
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.identity.domain.entity import LoginRecord
from app.identity.domain.errors import AccountLockedError, InvalidCredentialsError, InvalidPhoneError
from app.identity.domain.phone import normalize_phone
from app.identity.usecase.login import Login, LoginInput
from app.platform.auth.tokens import TokenService

PASSWORD = "correct-horse-battery"
PHONE = "+84901000001"


@pytest.fixture(scope="module")
def password_hash() -> str:
    return PasswordHasher().hash(PASSWORD)


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


class FakeRepo:
    def __init__(self, rec: LoginRecord | None) -> None:
        self.rec = rec
        self.failed: list[UUID] = []
        self.reset: list[UUID] = []

    async def find_for_login(self, conn: Any, phone_e164: str) -> LoginRecord | None:
        return self.rec if self.rec and phone_e164 == PHONE else None

    async def record_failed_login(self, conn: Any, user_id: UUID) -> None:
        self.failed.append(user_id)

    async def reset_failed_logins(self, conn: Any, user_id: UUID) -> None:
        self.reset.append(user_id)

    async def get_user(self, conn: Any, user_id: UUID) -> None:  # not used by login
        return None


@asynccontextmanager
async def _noop_uow(**_: Any):
    yield object()


def _record(password_hash: str, **overrides: Any) -> LoginRecord:
    base = LoginRecord(
        id=uuid4(),
        password_hash=password_hash,
        role="resident",
        status="active",
        staff_zone_id=None,
        failed_logins=0,
        lock_seconds=None,
    )
    return replace(base, **overrides)


def _login(repo: FakeRepo, tokens: TokenService) -> Login:
    return Login(repo, tokens, uow=_noop_uow)


async def test_success_returns_token_with_role_and_staff_zone_and_resets_counter(password_hash, tokens) -> None:
    zone = uuid4()
    rec = _record(password_hash, role="bql_staff", staff_zone_id=zone, failed_logins=3)
    repo = FakeRepo(rec)

    result = await _login(repo, tokens).execute(LoginInput(PHONE, PASSWORD))

    claims = tokens.verify(result.access_token)
    assert claims["sub"] == str(rec.id)
    assert claims["role"] == "bql_staff"
    assert claims["zone_ids"] == [str(zone)]
    assert result.expires_in == 15 * 60
    assert repo.reset == [rec.id]
    assert repo.failed == []


async def test_wrong_password_records_failed_login(password_hash, tokens) -> None:
    rec = _record(password_hash)
    repo = FakeRepo(rec)

    with pytest.raises(InvalidCredentialsError):
        await _login(repo, tokens).execute(LoginInput(PHONE, "nope"))

    assert repo.failed == [rec.id]


async def test_locked_account_is_rejected_without_checking_password(password_hash, tokens) -> None:
    rec = _record(password_hash, lock_seconds=600, failed_logins=5)
    repo = FakeRepo(rec)

    with pytest.raises(AccountLockedError) as exc:
        await _login(repo, tokens).execute(LoginInput(PHONE, PASSWORD))  # even the correct password

    assert exc.value.retry_after_seconds == 600
    assert repo.failed == [] and repo.reset == []


async def test_unknown_phone_gives_same_error_as_wrong_password(password_hash, tokens) -> None:
    repo = FakeRepo(_record(password_hash))

    with pytest.raises(InvalidCredentialsError):
        await _login(repo, tokens).execute(LoginInput("0999999999", PASSWORD))

    assert repo.failed == []


@pytest.mark.parametrize("status", ["suspended", "pending"])
async def test_inactive_account_with_correct_password_gets_no_token(password_hash, tokens, status) -> None:
    repo = FakeRepo(_record(password_hash, status=status))

    with pytest.raises(InvalidCredentialsError):
        await _login(repo, tokens).execute(LoginInput(PHONE, PASSWORD))


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("0901000001", "+84901000001"), ("+84 901-000.001", "+84901000001")],
    ids=["national-format", "separators-stripped"],
)
def test_normalize_phone_to_e164(raw: str, expected: str) -> None:
    assert normalize_phone(raw) == expected


def test_normalize_phone_rejects_garbage() -> None:
    with pytest.raises(InvalidPhoneError):
        normalize_phone("abc")
