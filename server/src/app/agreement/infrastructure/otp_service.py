"""OTP service implementation (Redis with InMemory fallback) cho Agreement module (M6).

Tuân thủ Clean Architecture và triết lý Ponytail:
- Cung cấp InMemoryOtpService: cực nhẹ, không dependencies ngoài, an toàn cho unit test và dev local.
- Cung cấp RedisOtpService: dùng Redis khi có cấu hình; nếu Redis không khả dụng sẽ tự động fallback sang memory.
"""

import json
import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from app.agreement.domain.exceptions import (
    InvalidOtpError,
    OtpExpiredError,
    OtpMaxAttemptsExceededError,
)
from app.agreement.domain.ports import OtpServicePort

logger = logging.getLogger(__name__)

MAX_OTP_ATTEMPTS = 5
DEFAULT_OTP_TTL_SECONDS = 1800  # 30 phút (khớp confirm_deadline D-16)


@dataclass
class _OtpEntry:
    code: str
    expires_at: datetime
    attempts: int = 0
    max_attempts: int = MAX_OTP_ATTEMPTS


class InMemoryOtpService(OtpServicePort):
    """Bộ nhớ đệm OTP in-memory phục vụ unit test và fallback khi không có Redis."""

    def __init__(self) -> None:
        self._store: dict[str, _OtpEntry] = {}

    def _make_key(self, agreement_id: UUID, user_id: UUID) -> str:
        return f"otp:agreement:{agreement_id}:{user_id}"

    async def issue_otp(self, agreement_id: UUID, user_id: UUID, ttl_seconds: int = DEFAULT_OTP_TTL_SECONDS) -> str:
        # Tạo mã 6 chữ số ngẫu nhiên an toàn mật mã học
        code = f"{secrets.randbelow(900000) + 100000:06d}"
        expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
        key = self._make_key(agreement_id, user_id)
        self._store[key] = _OtpEntry(code=code, expires_at=expires_at, attempts=0)
        logger.info("Issued OTP for agreement_id=%s, user_id=%s (TTL: %ss)", agreement_id, user_id, ttl_seconds)
        return code

    async def verify_otp(self, agreement_id: UUID, user_id: UUID, code: str) -> bool:
        key = self._make_key(agreement_id, user_id)
        entry = self._store.get(key)
        now = datetime.now(UTC)

        if entry is None or now > entry.expires_at:
            if key in self._store:
                del self._store[key]
            raise OtpExpiredError("OTP has expired or was not requested.")

        if entry.attempts >= entry.max_attempts:
            del self._store[key]
            raise OtpMaxAttemptsExceededError(entry.max_attempts)

        if entry.code != code.strip():
            entry.attempts += 1
            remaining = entry.max_attempts - entry.attempts
            logger.warning(
                "Invalid OTP entered for key=%s (attempt %s/%s)",
                key,
                entry.attempts,
                entry.max_attempts,
            )
            if remaining <= 0:
                del self._store[key]
                raise OtpMaxAttemptsExceededError(entry.max_attempts)
            raise InvalidOtpError(f"Invalid OTP code. {remaining} attempt(s) remaining.")

        # Mã hợp lệ: xóa OTP khỏi kho lưu trữ (chống replay OTP)
        del self._store[key]
        logger.info("Successfully verified and consumed OTP for agreement_id=%s, user_id=%s", agreement_id, user_id)
        return True

    async def invalidate_otp(self, agreement_id: UUID, user_id: UUID) -> None:
        key = self._make_key(agreement_id, user_id)
        self._store.pop(key, None)


class RedisOtpService(OtpServicePort):
    """Triển khai OTP qua Redis với tự động fallback sang memory khi Redis offline."""

    def __init__(self, redis_url: str = "redis://localhost:6379/0") -> None:
        self.redis_url = redis_url
        self._memory_fallback = InMemoryOtpService()
        self._redis_client: Any = None
        self._is_redis_available: bool | None = None

    def _make_key(self, agreement_id: UUID, user_id: UUID) -> str:
        return f"otp:agreement:{agreement_id}:{user_id}"

    async def _get_client(self) -> Any:
        if self._is_redis_available is False:
            return None

        if self._redis_client is None:
            try:
                import redis.asyncio as aioredis

                self._redis_client = aioredis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=2.0,
                )
                await self._redis_client.ping()
                self._is_redis_available = True
                logger.info("Connected to Redis at %s for OTP service.", self.redis_url)
            except Exception as e:
                logger.warning("Redis is not available (%s). Using InMemoryOtpService fallback.", e)
                self._is_redis_available = False
                self._redis_client = None

        return self._redis_client

    async def issue_otp(self, agreement_id: UUID, user_id: UUID, ttl_seconds: int = DEFAULT_OTP_TTL_SECONDS) -> str:
        client = await self._get_client()
        if client is None:
            return await self._memory_fallback.issue_otp(agreement_id, user_id, ttl_seconds)

        code = f"{secrets.randbelow(900000) + 100000:06d}"
        key = self._make_key(agreement_id, user_id)
        data = json.dumps({"code": code, "attempts": 0, "max_attempts": MAX_OTP_ATTEMPTS})
        await client.set(key, data, ex=ttl_seconds)
        logger.info("Issued Redis OTP for agreement_id=%s, user_id=%s (TTL: %ss)", agreement_id, user_id, ttl_seconds)
        return code

    async def verify_otp(self, agreement_id: UUID, user_id: UUID, code: str) -> bool:
        client = await self._get_client()
        if client is None:
            return await self._memory_fallback.verify_otp(agreement_id, user_id, code)

        key = self._make_key(agreement_id, user_id)
        val = await client.get(key)
        if not val:
            raise OtpExpiredError("OTP has expired or was not requested.")

        payload = json.loads(val)
        attempts = payload.get("attempts", 0)
        max_attempts = payload.get("max_attempts", MAX_OTP_ATTEMPTS)

        if attempts >= max_attempts:
            await client.delete(key)
            raise OtpMaxAttemptsExceededError(max_attempts)

        if payload.get("code") != code.strip():
            attempts += 1
            payload["attempts"] = attempts
            remaining = max_attempts - attempts
            ttl = await client.ttl(key)
            if ttl > 0:
                await client.set(key, json.dumps(payload), ex=ttl)
            if remaining <= 0:
                await client.delete(key)
                raise OtpMaxAttemptsExceededError(max_attempts)
            raise InvalidOtpError(f"Invalid OTP code. {remaining} attempt(s) remaining.")

        # Mã đúng: xóa để chống replay
        await client.delete(key)
        logger.info("Successfully verified Redis OTP for agreement_id=%s, user_id=%s", agreement_id, user_id)
        return True

    async def invalidate_otp(self, agreement_id: UUID, user_id: UUID) -> None:
        client = await self._get_client()
        if client is None:
            await self._memory_fallback.invalidate_otp(agreement_id, user_id)
            return
        key = self._make_key(agreement_id, user_id)
        await client.delete(key)
