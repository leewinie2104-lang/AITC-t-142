"""Stress Test: Kiểm thử đối kháng đồng thời (Concurrency & Race Conditions).

Mục tiêu kiểm thử chuẩn Production:
1. Độc quyền ô đỗ: 10 coroutines tranh chấp 1 ô duy nhất -> đúng 1 người giữ thành công, 9 người còn lại nhận no_match an toàn.
2. Dynamic Fallback: 5 coroutines tranh chấp 3 ô -> 3 người giữ 3 ô khác nhau, 2 người nhận no_match.
3. Idempotency Spam: 5 coroutines cùng gửi 1 idempotency_key -> cùng trả về 1 kết quả duy nhất, không tạo dữ liệu trùng.
4. Expired Hold Sweeper: Sau khi hold cũ hết hạn, slot được tái sử dụng thành công cho yêu cầu tiếp theo.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.booking.domain.exceptions import (
    DuplicateIdempotencyKeyError,
    SlotAlreadyHeldError,
)
from app.booking.domain.models import (
    HeldBookingRecord,
    ParkingRequestRecord,
    RequestOutcome,
)
from app.booking.domain.ports import BookingRepositoryPort, CandidateSlotDTO
from app.booking.usecase.request_parking import (
    RequestParkingCommand,
    RequestParkingResult,
    RequestParkingUseCase,
)


def _dt(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 11, 20, hour, minute, tzinfo=UTC)


class SimulatedPostgresBookingRepository(BookingRepositoryPort):
    """Mô phỏng chính xác hành vi của PostgreSQL với EXCLUDE USING gist."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        # Lưu trữ các booking đang hoạt động: slot_id -> list of (period_start, period_end, status, hold_expires_at, record)
        self.bookings: list[dict[str, Any]] = []
        self.requests_by_idem: dict[str, ParkingRequestRecord] = []
        self.requests_by_id: dict[UUID, ParkingRequestRecord] = {}
        self.booking_by_request: dict[UUID, HeldBookingRecord] = {}
        self.ref_counter = 1000

    async def get_request_by_idempotency_key(self, conn: Any, idempotency_key: str) -> ParkingRequestRecord | None:
        async with self._lock:
            for req in self.requests_by_id.values():
                if req.idempotency_key == idempotency_key:
                    return req
            return None

    async def get_booking_by_request_id(self, conn: Any, request_id: UUID) -> HeldBookingRecord | None:
        async with self._lock:
            return self.booking_by_request.get(request_id)

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
        async with self._lock:
            for req in self.requests_by_id.values():
                if req.idempotency_key == idempotency_key:
                    raise DuplicateIdempotencyKeyError(key=idempotency_key)

            rec = ParkingRequestRecord(
                id=request_id,
                zone_id=zone_id,
                building_id=building_id,
                requester_user_id=requester_user_id,
                vehicle_id=vehicle_id,
                period_start=period_start,
                period_end=period_end,
                computed_level=computed_level,
                outcome=outcome,
                block_reason=block_reason,
                channel=channel,
                idempotency_key=idempotency_key,
                created_at=datetime.now(UTC),
            )
            self.requests_by_id[request_id] = rec
            return rec

    async def sweep_expired_holds(self, conn: Any, slot_id: UUID) -> int:
        count = 0
        now_utc = datetime.now(UTC)
        for b in self.bookings:
            if b["slot_id"] == slot_id and b["status"] == "held" and b["hold_expires_at"] < now_utc:
                b["status"] = "expired"
                count += 1
        return count

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
        # Giả lập độ trễ mạng/I/O để tối đa hóa cơ hội race condition
        await asyncio.sleep(0.005)

        async with self._lock:
            await self.sweep_expired_holds(conn, slot_id)

            # Kiểm tra EXCLUDE USING gist (slot_id WITH =, period WITH &&)
            for b in self.bookings:
                if b["slot_id"] == slot_id and b["status"] in ("held", "confirmed"):
                    # Check overlap [period_start, period_end) && [b.start, b.end)
                    if max(period_start, b["start"]) < min(period_end, b["end"]):
                        # Ném lỗi mô phỏng mã lỗi 23P01 của PostgreSQL
                        raise SlotAlreadyHeldError(slot_id=slot_id)

            self.ref_counter += 1
            now_utc = datetime.now(UTC)
            rec = HeldBookingRecord(
                id=booking_id,
                ref_no=self.ref_counter,
                status="held",
                hold_expires_at=now_utc + hold_duration,
                created_at=now_utc,
            )

            self.bookings.append(
                {
                    "id": booking_id,
                    "slot_id": slot_id,
                    "start": period_start,
                    "end": period_end,
                    "status": "held",
                    "hold_expires_at": now_utc + hold_duration,
                    "record": rec,
                }
            )

            if request_id:
                self.booking_by_request[request_id] = rec

            return rec


class StaticCandidateFinder:
    """Mock Candidate Finder trả về danh sách ứng viên cố định."""

    def __init__(self, candidates: list[CandidateSlotDTO]) -> None:
        self.candidates = candidates

    async def find_candidates(
        self,
        conn: Any,
        zone_id: UUID,
        period_start: datetime,
        period_end: datetime,
        vehicle_size: str,
        allowed_scopes: list[str],
        limit: int = 10,
    ) -> list[CandidateSlotDTO]:
        return self.candidates[:limit]


# =========================================================================
# KỊCH BẢN 1: 10 Coroutines cùng tranh chấp 1 Slot duy nhất
# =========================================================================
@pytest.mark.asyncio
async def test_concurrency_single_slot_hotspot():
    zone_id = uuid4()
    building_id = uuid4()
    single_slot_id = uuid4()

    candidate = CandidateSlotDTO(
        slot_id=single_slot_id,
        zone_id=zone_id,
        building_id=building_id,
        slot_type="TH1",
        size_class="M",
        share_window_id=uuid4(),
        provider_user_id=uuid4(),
        price_vnd=50_000,
    )

    repo = SimulatedPostgresBookingRepository()
    finder = StaticCandidateFinder([candidate])
    use_case = RequestParkingUseCase(booking_repo=repo, candidate_finder=finder)

    async def _send_request(idx: int) -> RequestParkingResult:
        cmd = RequestParkingCommand(
            zone_id=zone_id,
            building_id=building_id,
            requester_user_id=uuid4(),
            vehicle_id=uuid4(),
            vehicle_size="M",
            period_start=_dt(9, 0),
            period_end=_dt(17, 0),
            computed_level="L1",
            idempotency_key=f"user_{idx}:step_1",
        )
        return await use_case.execute(conn=None, cmd=cmd)

    # Bắn đồng thời 10 coroutines
    tasks = [_send_request(i) for i in range(10)]
    results: list[RequestParkingResult] = await asyncio.gather(*tasks)

    matched = [r for r in results if r.outcome == RequestOutcome.matched]
    no_match = [r for r in results if r.outcome == RequestOutcome.no_match]

    # Kiểm tra bất biến: ĐÚNG 1 người giữ thành công, 9 người thất bại an toàn
    assert len(matched) == 1
    assert len(no_match) == 9
    assert matched[0].booking is not None

    # Trong DB chỉ có đúng 1 booking được tạo cho slot này
    active_bookings = [b for b in repo.bookings if b["status"] == "held"]
    assert len(active_bookings) == 1
    assert active_bookings[0]["slot_id"] == single_slot_id


# =========================================================================
# KỊCH BẢN 2: Dynamic Concurrency Fallback (5 requests tranh chấp 3 slots)
# =========================================================================
@pytest.mark.asyncio
async def test_concurrency_dynamic_fallback_multiple_slots():
    zone_id = uuid4()
    building_id = uuid4()

    # 3 slots ứng viên
    candidates = [
        CandidateSlotDTO(
            slot_id=uuid4(),
            zone_id=zone_id,
            building_id=building_id,
            slot_type="TH1",
            size_class="M",
            share_window_id=uuid4(),
            provider_user_id=uuid4(),
            price_vnd=50_000,
        )
        for _ in range(3)
    ]

    repo = SimulatedPostgresBookingRepository()
    finder = StaticCandidateFinder(candidates)
    use_case = RequestParkingUseCase(booking_repo=repo, candidate_finder=finder)

    async def _send_request(idx: int) -> RequestParkingResult:
        cmd = RequestParkingCommand(
            zone_id=zone_id,
            building_id=building_id,
            requester_user_id=uuid4(),
            vehicle_id=uuid4(),
            vehicle_size="M",
            period_start=_dt(10, 0),
            period_end=_dt(16, 0),
            computed_level="L1",
            idempotency_key=f"renter_{idx}:step_req",
        )
        return await use_case.execute(conn=None, cmd=cmd)

    # 5 người gửi yêu cầu cùng lúc cho 3 slots
    tasks = [_send_request(i) for i in range(5)]
    results: list[RequestParkingResult] = await asyncio.gather(*tasks)

    matched = [r for r in results if r.outcome == RequestOutcome.matched]
    no_match = [r for r in results if r.outcome == RequestOutcome.no_match]

    # Đúng 3 người nhận được 3 slot khác nhau
    assert len(matched) == 3
    assert len(no_match) == 2

    # Các booking phải thuộc về 3 slots hoàn toàn riêng biệt
    held_slot_ids = {b["slot_id"] for b in repo.bookings if b["status"] == "held"}
    assert len(held_slot_ids) == 3


# =========================================================================
# KỊCH BẢN 3: Idempotency Concurrency (Spam cùng 1 nút đặt chỗ)
# =========================================================================
@pytest.mark.asyncio
async def test_concurrency_idempotent_spam():
    zone_id = uuid4()
    building_id = uuid4()
    slot_id = uuid4()

    candidate = CandidateSlotDTO(
        slot_id=slot_id,
        zone_id=zone_id,
        building_id=building_id,
        slot_type="TH1",
        size_class="M",
        share_window_id=uuid4(),
        provider_user_id=uuid4(),
        price_vnd=50_000,
    )

    repo = SimulatedPostgresBookingRepository()
    finder = StaticCandidateFinder([candidate])
    use_case = RequestParkingUseCase(booking_repo=repo, candidate_finder=finder)

    shared_idem_key = "user_spam_key_999"
    renter_id = uuid4()
    vehicle_id = uuid4()

    async def _send_spam() -> RequestParkingResult:
        cmd = RequestParkingCommand(
            zone_id=zone_id,
            building_id=building_id,
            requester_user_id=renter_id,
            vehicle_id=vehicle_id,
            vehicle_size="M",
            period_start=_dt(8, 0),
            period_end=_dt(12, 0),
            computed_level="L1",
            idempotency_key=shared_idem_key,
        )
        return await use_case.execute(conn=None, cmd=cmd)

    # 5 requests gửi cùng lúc với cùng 1 idempotency_key
    tasks = [_send_spam() for _ in range(5)]
    results: list[RequestParkingResult] = await asyncio.gather(*tasks)

    # Tất cả các kết quả trả về đều là matched
    for r in results:
        assert r.outcome == RequestOutcome.matched
        assert r.booking is not None

    # Tất cả các kết quả đều trả về CÙNG 1 booking_id
    booking_ids = {r.booking.id for r in results if r.booking}
    assert len(booking_ids) == 1

    # Trong DB chỉ lưu đúng 1 booking duy nhất
    assert len(repo.bookings) == 1


# =========================================================================
# KỊCH BẢN 4: Expired Hold Sweeper (Hồi sinh slot sau khi hết hạn 10 phút)
# =========================================================================
@pytest.mark.asyncio
async def test_expired_hold_can_be_reclaimed():
    zone_id = uuid4()
    building_id = uuid4()
    slot_id = uuid4()

    candidate = CandidateSlotDTO(
        slot_id=slot_id,
        zone_id=zone_id,
        building_id=building_id,
        slot_type="TH1",
        size_class="M",
        share_window_id=uuid4(),
        provider_user_id=uuid4(),
        price_vnd=50_000,
    )

    repo = SimulatedPostgresBookingRepository()
    finder = StaticCandidateFinder([candidate])
    use_case = RequestParkingUseCase(booking_repo=repo, candidate_finder=finder)

    # User 1 giữ slot nhưng hold đã hết hạn từ 5 phút trước
    past_time = datetime.now(UTC) - timedelta(minutes=15)
    expired_hold_time = datetime.now(UTC) - timedelta(minutes=5)
    old_booking_id = uuid4()

    repo.bookings.append(
        {
            "id": old_booking_id,
            "slot_id": slot_id,
            "start": _dt(10, 0),
            "end": _dt(16, 0),
            "status": "held",
            "hold_expires_at": expired_hold_time,
            "record": HeldBookingRecord(
                id=old_booking_id,
                ref_no=888,
                status="held",
                hold_expires_at=expired_hold_time,
                created_at=past_time,
            ),
        }
    )

    # User 2 gửi yêu cầu mới cho cùng khung giờ
    cmd2 = RequestParkingCommand(
        zone_id=zone_id,
        building_id=building_id,
        requester_user_id=uuid4(),
        vehicle_id=uuid4(),
        vehicle_size="M",
        period_start=_dt(10, 0),
        period_end=_dt(16, 0),
        computed_level="L1",
        idempotency_key="user2:step_1",
    )
    result2 = await use_case.execute(conn=None, cmd=cmd2)

    # User 2 phải giữ thành công vì hold cũ đã hết hạn!
    assert result2.outcome == RequestOutcome.matched
    assert result2.booking is not None
    assert result2.booking.id != old_booking_id

    # Kiểm tra trạng thái booking cũ trong DB đã chuyển thành 'expired'
    old_b = next(b for b in repo.bookings if b["id"] == old_booking_id)
    assert old_b["status"] == "expired"
