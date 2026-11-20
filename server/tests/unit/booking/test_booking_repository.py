from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import asyncpg
import pytest

from app.booking.domain.exceptions import (
    DuplicateIdempotencyKeyError,
    SlotAlreadyHeldError,
)
from app.booking.infrastructure.booking_repository import BookingRepository


def _dt(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 11, 20, hour, minute, tzinfo=UTC)


@pytest.fixture
def repo() -> BookingRepository:
    return BookingRepository()


@pytest.fixture
def mock_conn() -> AsyncMock:
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="UPDATE 2")
    return conn


@pytest.mark.asyncio
async def test_hold_slot_atomic_success(repo: BookingRepository, mock_conn: AsyncMock):
    booking_id = uuid4()
    slot_id = uuid4()
    zone_id = uuid4()
    renter_id = uuid4()
    vehicle_id = uuid4()
    now_utc = _dt(10, 0)

    # Mock fetchrow returning newly created row
    mock_conn.fetchrow.return_value = {
        "id": booking_id,
        "ref_no": 101,
        "status": "held",
        "hold_expires_at": now_utc + timedelta(minutes=10),
        "created_at": now_utc,
    }

    result = await repo.hold_slot_atomic(
        conn=mock_conn,
        booking_id=booking_id,
        zone_id=zone_id,
        slot_id=slot_id,
        renter_user_id=renter_id,
        vehicle_id=vehicle_id,
        period_start=_dt(10, 0),
        period_end=_dt(16, 0),
        eligibility_level="L1",
        price_vnd=50_000,
        idempotency_key="thread_1:step_1",
    )

    # Verify sweep was called
    mock_conn.execute.assert_called_once()
    assert "UPDATE app.booking" in mock_conn.execute.call_args[0][0]
    assert mock_conn.execute.call_args[0][1] == slot_id

    # Verify insert was called
    mock_conn.fetchrow.assert_called_once()
    assert result.id == booking_id
    assert result.status == "held"
    assert result.ref_no == 101


@pytest.mark.asyncio
async def test_hold_slot_atomic_catches_exclusion_violation(repo: BookingRepository, mock_conn: AsyncMock):
    """Giả lập trường hợp 2 request giữ cùng 1 slot -> Postgres ném 23P01."""
    slot_id = uuid4()

    # Tạo exception asyncpg ExclusionViolationError (mã 23P01)
    mock_conn.fetchrow.side_effect = asyncpg.exceptions.ExclusionViolationError(
        "conflicting key value violates exclusion constraint 'booking_no_overlap'"
    )

    with pytest.raises(SlotAlreadyHeldError) as exc_info:
        await repo.hold_slot_atomic(
            conn=mock_conn,
            booking_id=uuid4(),
            zone_id=uuid4(),
            slot_id=slot_id,
            renter_user_id=uuid4(),
            vehicle_id=uuid4(),
            period_start=_dt(10, 0),
            period_end=_dt(16, 0),
            eligibility_level="L1",
            price_vnd=50_000,
            idempotency_key="thread_2:step_1",
        )

    assert exc_info.value.slot_id == slot_id
    assert "already has an overlapping reservation" in str(exc_info.value)


@pytest.mark.asyncio
async def test_hold_slot_atomic_catches_duplicate_idempotency_key(repo: BookingRepository, mock_conn: AsyncMock):
    """Giả lập request bị bấm 2 lần với cùng 1 idempotency_key -> Postgres ném 23505."""
    key = "idem_req_abc_123"

    mock_conn.fetchrow.side_effect = asyncpg.exceptions.UniqueViolationError(
        f"duplicate key value violates unique constraint 'app_booking_idempotency_key_key' DETAIL: Key (idempotency_key)=({key}) already exists."
    )

    with pytest.raises(DuplicateIdempotencyKeyError) as exc_info:
        await repo.hold_slot_atomic(
            conn=mock_conn,
            booking_id=uuid4(),
            zone_id=uuid4(),
            slot_id=uuid4(),
            renter_user_id=uuid4(),
            vehicle_id=uuid4(),
            period_start=_dt(10, 0),
            period_end=_dt(16, 0),
            eligibility_level="L1",
            price_vnd=50_000,
            idempotency_key=key,
        )

    assert exc_info.value.key == key
    assert key in str(exc_info.value)
