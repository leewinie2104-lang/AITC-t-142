"""Login with phone + password (SCRUM-86). Failure counting follows 05-concurrency §8."""

import asyncio
import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.identity.domain.errors import AccountLockedError, InvalidCredentialsError, InvalidPhoneError
from app.identity.domain.phone import normalize_phone
from app.identity.domain.ports import TokenIssuer, UserRepository
from app.platform.db.session import unit_of_work

logger = logging.getLogger(__name__)

_hasher = PasswordHasher()
# Verified against when the phone is unknown, so unknown and wrong-password answers take the same time.
_DUMMY_HASH = _hasher.hash("parksmart-dummy-password")


@dataclass(frozen=True)
class LoginInput:
    phone: str
    password: str


@dataclass(frozen=True)
class LoginResult:
    access_token: str
    expires_in: int


async def _password_matches(password_hash: str, password: str) -> bool:
    # argon2 costs ~50 ms of CPU: keep it off the event loop.
    try:
        return await asyncio.to_thread(_hasher.verify, password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


class Login:
    def __init__(
        self,
        repo: UserRepository,
        tokens: TokenIssuer,
        uow: Callable[..., AbstractAsyncContextManager[Any]] = unit_of_work,
    ) -> None:
        self._repo = repo
        self._tokens = tokens
        self._uow = uow

    async def execute(self, inp: LoginInput) -> LoginResult:
        try:
            phone = normalize_phone(inp.phone)
        except InvalidPhoneError:
            await _password_matches(_DUMMY_HASH, inp.password)
            raise InvalidCredentialsError from None

        # Outcomes are raised after the block: raising inside would roll back the failed-login counter.
        locked_for: int | None = None
        result: LoginResult | None = None
        user_id: UUID | None = None
        async with self._uow(role="auth") as conn:
            rec = await self._repo.find_for_login(conn, phone)
            if rec is None:
                await _password_matches(_DUMMY_HASH, inp.password)
            else:
                user_id = rec.id
                if rec.lock_seconds:
                    locked_for = rec.lock_seconds
                elif not await _password_matches(rec.password_hash, inp.password):
                    await self._repo.record_failed_login(conn, rec.id)
                elif rec.status == "active":
                    if rec.failed_logins:
                        await self._repo.reset_failed_logins(conn, rec.id)
                    zone_ids = [rec.staff_zone_id] if rec.staff_zone_id else []
                    token, expires_in = self._tokens.issue(rec.id, rec.role, zone_ids)
                    result = LoginResult(access_token=token, expires_in=expires_in)

        if locked_for:
            logger.info("login rejected: account locked user=%s", user_id)
            raise AccountLockedError(locked_for)
        if result is None:
            logger.info("login failed user=%s", user_id or "unknown")
            raise InvalidCredentialsError
        logger.info("login ok user=%s", user_id)
        return result
