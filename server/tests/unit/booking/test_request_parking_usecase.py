from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.booking.domain.exceptions import SlotAlreadyHeldError
from app.booking.domain.models import (
    HeldBookingRecord,
    ParkingRequestRecord,
    RequestOutcome,
)
from app.booking.domain.ports import CandidateSlotDTO
from app.booking.usecase.request_parking import (
    RequestParkingCommand,
    RequestParkingUseCase,
)


def _dt(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 11, 20, hour, minute, tzinfo=UTC)


@pytest.fixture
def mock_booking_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.get_request_by_idempotency_key.return_value = None
    repo.create_parking_request.return_value = None
    return repo


@pytest.fixture
def mock_candidate_finder() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def use_case(mock_booking_repo: AsyncMock, mock_candidate_finder: AsyncMock) -> RequestParkingUseCase:
    return RequestParkingUseCase(
        booking_repo=mock_booking_repo,
        candidate_finder=mock_candidate_finder,
    )


@pytest.fixture
def base_cmd() -> RequestParkingCommand:
    return RequestParkingCommand(
        zone_id=uuid4(),
        building_id=uuid4(),
        requester_user_id=uuid4(),
        vehicle_id=uuid4(),
        vehicle_size="M",
        period_start=_dt(9, 0),
        period_end=_dt(17, 0),
        computed_level="L1",
        idempotency_key="thread_1:step_req_parking",
    )


@pytest.mark.asyncio
async def test_request_parking_happy_path(
    use_case: RequestParkingUseCase,
    mock_booking_repo: AsyncMock,
    mock_candidate_finder: AsyncMock,
    base_cmd: RequestParkingCommand,
):
    slot_id = uuid4()
    candidate = CandidateSlotDTO(
        slot_id=slot_id,
        zone_id=base_cmd.zone_id,
        building_id=base_cmd.building_id,
        slot_type="TH1",
        size_class="L",
        share_window_id=uuid4(),
        provider_user_id=uuid4(),
        price_vnd=50_000,
    )
    mock_candidate_finder.find_candidates.return_value = [candidate]

    expected_booking = HeldBookingRecord(
        id=uuid4(),
        ref_no=501,
        status="held",
        hold_expires_at=_dt(9, 10),
        created_at=_dt(9, 0),
    )
    mock_booking_repo.hold_slot_atomic.return_value = expected_booking

    conn = AsyncMock()
    result = await use_case.execute(conn, base_cmd)

    assert result.outcome == RequestOutcome.matched
    assert result.booking == expected_booking
    mock_booking_repo.create_parking_request.assert_called_once()
    assert mock_booking_repo.create_parking_request.call_args.kwargs["outcome"] == RequestOutcome.matched


@pytest.mark.asyncio
async def test_request_parking_concurrency_fallback(
    use_case: RequestParkingUseCase,
    mock_booking_repo: AsyncMock,
    mock_candidate_finder: AsyncMock,
    base_cmd: RequestParkingCommand,
):
    """Khi ứng viên 1 bị giữ cùng lúc (23P01), use case tự động fallback sang ứng viên 2."""
    cand1 = CandidateSlotDTO(
        slot_id=uuid4(),
        zone_id=base_cmd.zone_id,
        building_id=base_cmd.building_id,
        slot_type="TH1",
        size_class="M",
        share_window_id=uuid4(),
        provider_user_id=uuid4(),
        price_vnd=50_000,
    )
    cand2 = CandidateSlotDTO(
        slot_id=uuid4(),
        zone_id=base_cmd.zone_id,
        building_id=base_cmd.building_id,
        slot_type="TH1",
        size_class="L",
        share_window_id=uuid4(),
        provider_user_id=uuid4(),
        price_vnd=50_000,
    )
    mock_candidate_finder.find_candidates.return_value = [cand1, cand2]

    # Cand 1 bị ném SlotAlreadyHeldError, Cand 2 thành công
    expected_booking = HeldBookingRecord(
        id=uuid4(),
        ref_no=502,
        status="held",
        hold_expires_at=_dt(9, 10),
        created_at=_dt(9, 0),
    )
    mock_booking_repo.hold_slot_atomic.side_effect = [
        SlotAlreadyHeldError(slot_id=cand1.slot_id),
        expected_booking,
    ]

    conn = AsyncMock()
    result = await use_case.execute(conn, base_cmd)

    assert result.outcome == RequestOutcome.matched
    assert result.booking == expected_booking
    assert mock_booking_repo.hold_slot_atomic.call_count == 2


@pytest.mark.asyncio
async def test_request_parking_no_match(
    use_case: RequestParkingUseCase,
    mock_booking_repo: AsyncMock,
    mock_candidate_finder: AsyncMock,
    base_cmd: RequestParkingCommand,
):
    mock_candidate_finder.find_candidates.return_value = []

    conn = AsyncMock()
    result = await use_case.execute(conn, base_cmd)

    assert result.outcome == RequestOutcome.no_match
    assert result.booking is None
    mock_booking_repo.create_parking_request.assert_called_once()
    assert mock_booking_repo.create_parking_request.call_args.kwargs["outcome"] == RequestOutcome.no_match


@pytest.mark.asyncio
async def test_request_parking_idempotent_replay(
    use_case: RequestParkingUseCase,
    mock_booking_repo: AsyncMock,
    mock_candidate_finder: AsyncMock,
    base_cmd: RequestParkingCommand,
):
    request_id = uuid4()
    mock_booking_repo.get_request_by_idempotency_key.return_value = ParkingRequestRecord(
        id=request_id,
        zone_id=base_cmd.zone_id,
        building_id=base_cmd.building_id,
        requester_user_id=base_cmd.requester_user_id,
        vehicle_id=base_cmd.vehicle_id,
        period_start=base_cmd.period_start,
        period_end=base_cmd.period_end,
        computed_level=base_cmd.computed_level,
        outcome=RequestOutcome.matched,
        block_reason=None,
        channel=base_cmd.channel,
        idempotency_key=base_cmd.idempotency_key,
        created_at=_dt(8, 0),
    )
    mock_booking_repo.get_booking_by_request_id.return_value = HeldBookingRecord(
        id=uuid4(),
        ref_no=777,
        status="held",
        hold_expires_at=_dt(8, 10),
        created_at=_dt(8, 0),
    )

    conn = AsyncMock()
    result = await use_case.execute(conn, base_cmd)

    # Replay -> Không tìm kiếm lại và không tạo giữ chỗ mới
    mock_candidate_finder.find_candidates.assert_not_called()
    mock_booking_repo.hold_slot_atomic.assert_not_called()
    assert result.outcome == RequestOutcome.matched
    assert result.booking is not None
    assert result.booking.ref_no == 777
    assert "Idempotent replay" in result.message
