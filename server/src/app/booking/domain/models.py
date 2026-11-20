"""Domain models and value objects for the Booking module (M5)."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class BookingStatus(StrEnum):
    held = "held"
    pending_agreement = "pending_agreement"
    pending_approval = "pending_approval"
    confirmed = "confirmed"
    cancelled = "cancelled"
    expired = "expired"
    relocated = "relocated"
    void = "void"


class RequestOutcome(StrEnum):
    matched = "matched"
    redirected_th3 = "redirected_th3"
    redirected_public = "redirected_public"
    blocked = "blocked"
    no_match = "no_match"


@dataclass(frozen=True)
class HeldBookingRecord:
    """Bản ghi kết quả giữ chỗ tạm thời từ DB."""

    id: UUID
    ref_no: int
    status: str
    hold_expires_at: datetime
    created_at: datetime


@dataclass(frozen=True)
class ParkingRequestRecord:
    """Bản ghi yêu cầu tìm chỗ (app.parking_request)."""

    id: UUID
    zone_id: UUID
    building_id: UUID
    requester_user_id: UUID
    vehicle_id: UUID
    period_start: datetime
    period_end: datetime
    computed_level: str
    outcome: RequestOutcome
    block_reason: str | None
    channel: str
    idempotency_key: str
    created_at: datetime
