"""Domain exceptions for Booking and Holding operations."""

from uuid import UUID


class BookingError(Exception):
    """Base exception cho nghiệp vụ booking."""


class SlotAlreadyHeldError(BookingError):
    """Xảy ra khi ô đỗ đã bị giữ chỗ bởi giao dịch khác trong cùng khoảng thời gian (PostgreSQL 23P01)."""

    def __init__(self, slot_id: UUID, message: str | None = None) -> None:
        self.slot_id = slot_id
        super().__init__(message or f"Slot {slot_id} already has an overlapping reservation or active hold.")


class DuplicateIdempotencyKeyError(BookingError):
    """Khóa idempotency_key đã tồn tại (PostgreSQL 23505)."""

    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(f"Operation with idempotency key '{key}' has already been processed.")
