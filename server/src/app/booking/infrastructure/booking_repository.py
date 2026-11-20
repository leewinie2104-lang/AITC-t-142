"""Booking and Holding Repository (M5).

Triển khai giao dịch giữ chỗ nguyên tử chống double-booking
thông qua PostgreSQL EXCLUDE constraint (23P01) và READ COMMITTED.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import asyncpg

from app.booking.domain.exceptions import (
    DuplicateIdempotencyKeyError,
    SlotAlreadyHeldError,
)
from app.booking.domain.models import HeldBookingRecord

logger = logging.getLogger(__name__)


class BookingRepository:
    """Repository quản lý các thao tác trên bảng app.booking."""

    async def sweep_expired_holds(self, conn: Any, slot_id: UUID) -> int:
        """Hết hạn các giữ chỗ cũ của ô đỗ nếu đã quá hạn hold_expires_at."""
        query = """
            UPDATE app.booking
            SET status = 'expired', updated_at = now()
            WHERE slot_id = $1
              AND status = 'held'
              AND hold_expires_at < now();
        """
        result = await conn.execute(query, slot_id)
        try:
            return int(result.split()[-1])
        except (ValueError, IndexError):
            return 0

    async def hold_slot_atomic(
        self,
        conn: Any,
        booking_id: UUID,
        zone_id: UUID,
        slot_id: UUID,
        renter_user_id: UUID,
        vehicle_id: UUID,
        period_start: datetime,
        period_end: datetime,
        eligibility_level: str,
        price_vnd: int,
        idempotency_key: str,
        share_window_id: UUID | None = None,
        provider_user_id: UUID | None = None,
        hold_duration: timedelta = timedelta(minutes=10),
    ) -> HeldBookingRecord:
        """Thực hiện giữ chỗ nguyên tử trên app.booking.

        1. Quét các hold cũ đã hết hạn của ô (UPDATE status='expired').
        2. Insert booking mới với status='held'.
        3. Bắt lỗi ExclusionViolationError (23P01) -> ném SlotAlreadyHeldError.
        """
        # Bước 1: Quét dọn hold hết hạn
        await self.sweep_expired_holds(conn, slot_id)

        now_utc = datetime.now(UTC)
        hold_expires_at = now_utc + hold_duration

        insert_sql = """
            INSERT INTO app.booking (
                id, zone_id, slot_id, share_window_id, provider_user_id,
                renter_user_id, vehicle_id, period, eligibility_level,
                price_vnd, status, hold_expires_at, idempotency_key
            ) VALUES (
                $1, $2, $3, $4, $5,
                $6, $7, tstzrange($8, $9, '[)'), $10,
                $11, 'held', $12, $13
            )
            RETURNING id, ref_no, status, hold_expires_at, created_at;
        """

        try:
            row = await conn.fetchrow(
                insert_sql,
                booking_id,
                zone_id,
                slot_id,
                share_window_id,
                provider_user_id,
                renter_user_id,
                vehicle_id,
                period_start,
                period_end,
                eligibility_level,
                price_vnd,
                hold_expires_at,
                idempotency_key,
            )
            if row is None:
                raise RuntimeError("Failed to insert booking record, returning none")

            return HeldBookingRecord(
                id=row["id"],
                ref_no=row["ref_no"],
                status=row["status"],
                hold_expires_at=row["hold_expires_at"],
                created_at=row["created_at"],
            )

        except asyncpg.exceptions.ExclusionViolationError as exc:
            # Mã lỗi 23P01 từ PostgreSQL constraint booking_no_overlap
            logger.warning(
                "Slot %s already has conflicting reservation in [%s, %s]: %s",
                slot_id,
                period_start,
                period_end,
                exc,
            )
            raise SlotAlreadyHeldError(slot_id=slot_id) from exc

        except asyncpg.exceptions.UniqueViolationError as exc:
            # Mã lỗi 23505: idempotent hoặc ref_no
            if "idempotency_key" in str(exc):
                logger.info("Idempotency key '%s' duplicated", idempotency_key)
                raise DuplicateIdempotencyKeyError(key=idempotency_key) from exc
            raise
