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
from app.booking.domain.models import HeldBookingRecord, ParkingRequestRecord, RequestOutcome

logger = logging.getLogger(__name__)


def _to_parking_request_record(row: Any) -> ParkingRequestRecord:
    data = dict(row)
    data["outcome"] = RequestOutcome(data["outcome"])
    return ParkingRequestRecord(**data)


def _to_held_booking_record(row: Any) -> HeldBookingRecord:
    return HeldBookingRecord(**dict(row))


class BookingRepository:
    """Repository quản lý các thao tác trên bảng app.booking và app.parking_request."""

    async def create_parking_request(
        self,
        conn: Any,
        request_id: UUID,
        zone_id: UUID,
        building_id: UUID,
        requester_user_id: UUID,
        vehicle_id: UUID,
        period_start: datetime,
        period_end: datetime,
        computed_level: str,
        outcome: RequestOutcome,
        idempotency_key: str,
        channel: str = "app",
        block_reason: str | None = None,
    ) -> ParkingRequestRecord:
        """Ghi nhận yêu cầu đỗ xe vào app.parking_request."""
        insert_sql = """
            INSERT INTO app.parking_request (
                id, zone_id, building_id, requester_user_id, vehicle_id,
                requested_period, computed_level, outcome, block_reason,
                channel, idempotency_key
            ) VALUES (
                $1, $2, $3, $4, $5,
                tstzrange($6, $7, '[)'), $8, $9, $10,
                $11, $12
            )
            RETURNING id, zone_id, building_id, requester_user_id, vehicle_id,
                      lower(requested_period) as period_start,
                      upper(requested_period) as period_end,
                      computed_level, outcome, block_reason, channel,
                      idempotency_key, created_at;
        """
        try:
            row = await conn.fetchrow(
                insert_sql,
                request_id,
                zone_id,
                building_id,
                requester_user_id,
                vehicle_id,
                period_start,
                period_end,
                computed_level,
                outcome.value,
                block_reason,
                channel,
                idempotency_key,
            )
            return _to_parking_request_record(row)
        except asyncpg.exceptions.UniqueViolationError as exc:
            if "idempotency_key" in str(exc):
                raise DuplicateIdempotencyKeyError(key=idempotency_key) from exc
            raise

    async def get_request_by_idempotency_key(self, conn: Any, idempotency_key: str) -> ParkingRequestRecord | None:
        """Tìm parking_request theo idempotency_key để phục vụ replay idempotency."""
        query = """
            SELECT id, zone_id, building_id, requester_user_id, vehicle_id,
                   lower(requested_period) as period_start,
                   upper(requested_period) as period_end,
                   computed_level, outcome, block_reason, channel,
                   idempotency_key, created_at
            FROM app.parking_request
            WHERE idempotency_key = $1;
        """
        row = await conn.fetchrow(query, idempotency_key)
        return _to_parking_request_record(row) if row else None

    async def get_booking_by_request_id(self, conn: Any, request_id: UUID) -> HeldBookingRecord | None:
        """Lấy booking gắn liền với parking_request_id."""
        query = """
            SELECT id, ref_no, status, hold_expires_at, created_at
            FROM app.booking
            WHERE request_id = $1;
        """
        row = await conn.fetchrow(query, request_id)
        return _to_held_booking_record(row) if row else None

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
        request_id: UUID | None = None,
        share_window_id: UUID | None = None,
        provider_user_id: UUID | None = None,
        hold_duration: timedelta = timedelta(minutes=10),
    ) -> HeldBookingRecord:
        """Thực hiện giữ chỗ nguyên tử trên app.booking.

        1. Quét các hold cũ đã hết hạn của ô (UPDATE status='expired').
        2. Insert booking mới với status='held'.
        3. Bắt lỗi ExclusionViolationError (23P01) -> ném SlotAlreadyHeldError.
        """
        await self.sweep_expired_holds(conn, slot_id)

        now_utc = datetime.now(UTC)
        hold_expires_at = now_utc + hold_duration

        insert_sql = """
            INSERT INTO app.booking (
                id, zone_id, slot_id, request_id, share_window_id, provider_user_id,
                renter_user_id, vehicle_id, period, eligibility_level,
                price_vnd, status, hold_expires_at, idempotency_key
            ) VALUES (
                $1, $2, $3, $4, $5, $6,
                $7, $8, tstzrange($9, $10, '[)'), $11,
                $12, 'held', $13, $14
            )
            RETURNING id, ref_no, status, hold_expires_at, created_at;
        """

        try:
            row = await conn.fetchrow(
                insert_sql,
                booking_id,
                zone_id,
                slot_id,
                request_id,
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
            return _to_held_booking_record(row)

        except asyncpg.exceptions.ExclusionViolationError as exc:
            logger.warning(
                "Slot %s already has conflicting reservation in [%s, %s]: %s",
                slot_id,
                period_start,
                period_end,
                exc,
            )
            raise SlotAlreadyHeldError(slot_id=slot_id) from exc

        except asyncpg.exceptions.UniqueViolationError as exc:
            if "idempotency_key" in str(exc):
                logger.info("Idempotency key '%s' duplicated", idempotency_key)
                raise DuplicateIdempotencyKeyError(key=idempotency_key) from exc
            raise
