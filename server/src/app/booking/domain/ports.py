"""Domain ports and DTOs for the Booking module (M5).

Định nghĩa interface để giao tiếp với các module khác (như M4 Sharing)
và interface repository theo nguyên tắc Clean Architecture (ADR-0010),
usecase/ chỉ phụ thuộc vào domain/ports, không phụ thuộc vào infrastructure/.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Protocol
from uuid import UUID

from app.booking.domain.models import HeldBookingRecord, ParkingRequestRecord, RequestOutcome


@dataclass(frozen=True)
class CandidateSlotDTO:
    """DTO thông tin ứng viên ô đỗ khả dụng từ module chia sẻ (M4)."""

    slot_id: UUID
    zone_id: UUID
    building_id: UUID
    slot_type: str
    size_class: str
    share_window_id: UUID | None
    provider_user_id: UUID | None
    price_vnd: int


class CandidateFinderPort(Protocol):
    """Port tìm kiếm ứng viên ô đỗ khả dụng (do M4 Sharing cung cấp)."""

    async def find_candidates(
        self,
        conn: Any,
        zone_id: UUID,
        period_start: datetime,
        period_end: datetime,
        vehicle_size: str,
        allowed_scopes: list[str],
        limit: int = 10,
    ) -> list[CandidateSlotDTO]: ...


class BookingRepositoryPort(Protocol):
    """Port thao tác lưu trữ cho module booking."""

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
    ) -> ParkingRequestRecord: ...

    async def get_request_by_idempotency_key(self, conn: Any, idempotency_key: str) -> ParkingRequestRecord | None: ...

    async def get_booking_by_request_id(self, conn: Any, request_id: UUID) -> HeldBookingRecord | None: ...

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
    ) -> HeldBookingRecord: ...
