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


@dataclass(frozen=True)
class HeldBookingRecord:
    """Bản ghi kết quả giữ chỗ tạm thời từ DB."""

    id: UUID
    ref_no: int
    status: str
    hold_expires_at: datetime
    created_at: datetime
