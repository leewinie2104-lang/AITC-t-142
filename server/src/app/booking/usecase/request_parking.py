"""Use case: Yêu cầu đỗ xe & giữ chỗ tạm thời (M5, SCRUM-96).

Thực hiện:
1. Kiểm tra idempotency_key chống chạy lại (Idempotent Replay).
2. Xác định phạm vi mở theo cấp tư cách (BR-01, BR-15).
3. Tìm kiếm ứng viên từ Sharing (M4) qua CandidateFinderPort.
4. Giữ chỗ nguyên tử (Hold Booking) kèm tự động thử ứng viên kế tiếp nếu gặp SlotAlreadyHeldError (23P01).
5. Ghi nhận lịch sử yêu cầu vào app.parking_request (kể cả khi không có chỗ hoặc bị chặn),
   bắt lỗi DuplicateIdempotencyKeyError (23505) để giải quyết race condition giữa các request đồng thời.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from app.booking.domain.exceptions import (
    DuplicateIdempotencyKeyError,
    SlotAlreadyHeldError,
)
from app.booking.domain.models import (
    HeldBookingRecord,
    RequestOutcome,
)
from app.booking.domain.ports import BookingRepositoryPort, CandidateFinderPort

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RequestParkingCommand:
    """Tham số đầu vào yêu cầu đỗ xe."""

    zone_id: UUID
    building_id: UUID
    requester_user_id: UUID
    vehicle_id: UUID
    vehicle_size: str
    period_start: datetime
    period_end: datetime
    computed_level: str
    idempotency_key: str
    channel: str = "app"


@dataclass(frozen=True)
class RequestParkingResult:
    """Kết quả trả về của usecase."""

    outcome: RequestOutcome
    request_id: UUID
    booking: HeldBookingRecord | None = None
    block_reason: str | None = None
    message: str = ""


_LEVEL_TO_ALLOWED_SCOPES: dict[str, list[str]] = {
    "L1": ["building", "zone", "chain", "public"],
    "L2": ["zone", "chain", "public"],
    "L3": ["chain", "public"],
    "L4": ["public"],
}


class RequestParkingUseCase:
    """Use case xử lý yêu cầu tìm chỗ và giữ chỗ tạm thời."""

    def __init__(
        self,
        booking_repo: BookingRepositoryPort,
        candidate_finder: CandidateFinderPort,
    ) -> None:
        self.booking_repo = booking_repo
        self.candidate_finder = candidate_finder

    async def _resolve_idempotent_replay(self, conn: Any, idempotency_key: str) -> RequestParkingResult | None:
        """Helper lấy kết quả của request đã được ghi nhận trước đó."""
        existing = await self.booking_repo.get_request_by_idempotency_key(conn, idempotency_key)
        if not existing:
            return None
        existing_booking = None
        if existing.outcome == RequestOutcome.matched:
            existing_booking = await self.booking_repo.get_booking_by_request_id(conn, existing.id)
        return RequestParkingResult(
            outcome=existing.outcome,
            request_id=existing.id,
            booking=existing_booking,
            block_reason=existing.block_reason,
            message="Yêu cầu đã được xử lý trước đó (Idempotent replay)",
        )

    async def execute(self, conn: Any, cmd: RequestParkingCommand) -> RequestParkingResult:
        if cmd.period_start >= cmd.period_end:
            raise ValueError("period_start must be before period_end")

        # 1. Idempotency replay check ban đầu
        replay = await self._resolve_idempotent_replay(conn, cmd.idempotency_key)
        if replay:
            logger.info("Replaying request with idempotency key: %s", cmd.idempotency_key)
            return replay

        # 2. Xác định phạm vi mở được phép theo cấp tư cách
        allowed_scopes = _LEVEL_TO_ALLOWED_SCOPES.get(cmd.computed_level, ["public"])

        # 3. Tìm ứng viên từ Module Chia sẻ (M4)
        candidates = await self.candidate_finder.find_candidates(
            conn=conn,
            zone_id=cmd.zone_id,
            period_start=cmd.period_start,
            period_end=cmd.period_end,
            vehicle_size=cmd.vehicle_size,
            allowed_scopes=allowed_scopes,
            limit=5,
        )

        request_id = uuid4()

        if not candidates:
            # Không có ứng viên nào phù hợp
            try:
                await self.booking_repo.create_parking_request(
                    conn=conn,
                    request_id=request_id,
                    zone_id=cmd.zone_id,
                    building_id=cmd.building_id,
                    requester_user_id=cmd.requester_user_id,
                    vehicle_id=cmd.vehicle_id,
                    period_start=cmd.period_start,
                    period_end=cmd.period_end,
                    computed_level=cmd.computed_level,
                    outcome=RequestOutcome.no_match,
                    idempotency_key=cmd.idempotency_key,
                    channel=cmd.channel,
                )
            except DuplicateIdempotencyKeyError:
                replay = await self._resolve_idempotent_replay(conn, cmd.idempotency_key)
                if replay:
                    return replay

            return RequestParkingResult(
                outcome=RequestOutcome.no_match,
                request_id=request_id,
                message="Không tìm thấy ô đỗ phù hợp trong khung giờ yêu cầu",
            )

        # 4. Thử giữ chỗ nguyên tử theo thứ tự ưu tiên
        held_booking: HeldBookingRecord | None = None
        for candidate in candidates:
            booking_id = uuid4()
            booking_idem_key = f"{cmd.idempotency_key}:booking"
            try:
                held_booking = await self.booking_repo.hold_slot_atomic(
                    conn=conn,
                    booking_id=booking_id,
                    zone_id=cmd.zone_id,
                    slot_id=candidate.slot_id,
                    renter_user_id=cmd.requester_user_id,
                    vehicle_id=cmd.vehicle_id,
                    period_start=cmd.period_start,
                    period_end=cmd.period_end,
                    eligibility_level=cmd.computed_level,
                    price_vnd=candidate.price_vnd,
                    idempotency_key=booking_idem_key,
                    request_id=request_id,
                    share_window_id=candidate.share_window_id,
                    provider_user_id=candidate.provider_user_id,
                )
                break  # Giữ chỗ thành công -> thoát loop
            except SlotAlreadyHeldError:
                logger.warning(
                    "Candidate slot %s was held concurrently, trying next candidate...",
                    candidate.slot_id,
                )
                continue
            except DuplicateIdempotencyKeyError:
                # Trùng booking idempotency do request đồng thời đã giữ thành công
                replay = await self._resolve_idempotent_replay(conn, cmd.idempotency_key)
                if replay:
                    return replay

        if held_booking is not None:
            # Ghi nhận parking_request thành công (matched)
            try:
                await self.booking_repo.create_parking_request(
                    conn=conn,
                    request_id=request_id,
                    zone_id=cmd.zone_id,
                    building_id=cmd.building_id,
                    requester_user_id=cmd.requester_user_id,
                    vehicle_id=cmd.vehicle_id,
                    period_start=cmd.period_start,
                    period_end=cmd.period_end,
                    computed_level=cmd.computed_level,
                    outcome=RequestOutcome.matched,
                    idempotency_key=cmd.idempotency_key,
                    channel=cmd.channel,
                )
            except DuplicateIdempotencyKeyError:
                replay = await self._resolve_idempotent_replay(conn, cmd.idempotency_key)
                if replay:
                    return replay

            return RequestParkingResult(
                outcome=RequestOutcome.matched,
                request_id=request_id,
                booking=held_booking,
                message="Giữ chỗ tạm thời thành công",
            )

        # Toàn bộ ứng viên đều bị giành mất (Race condition exhaust)
        try:
            await self.booking_repo.create_parking_request(
                conn=conn,
                request_id=request_id,
                zone_id=cmd.zone_id,
                building_id=cmd.building_id,
                requester_user_id=cmd.requester_user_id,
                vehicle_id=cmd.vehicle_id,
                period_start=cmd.period_start,
                period_end=cmd.period_end,
                computed_level=cmd.computed_level,
                outcome=RequestOutcome.no_match,
                idempotency_key=cmd.idempotency_key,
                channel=cmd.channel,
            )
        except DuplicateIdempotencyKeyError:
            replay = await self._resolve_idempotent_replay(conn, cmd.idempotency_key)
            if replay:
                return replay

        return RequestParkingResult(
            outcome=RequestOutcome.no_match,
            request_id=request_id,
            message="Các ô đỗ ứng viên đã bị giữ bởi giao dịch khác trong cùng thời điểm",
        )
