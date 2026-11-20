"""Domain ports và DTOs cho Agreement module (M6)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from app.agreement.domain.models import AgreementRecord


@dataclass(frozen=True)
class ZonePolicyDTO:
    """Thông tin chính sách khu vực đang hiệu lực (app.zone_policy)."""

    id: UUID
    zone_id: UUID
    version: int
    agreement_template_md: str
    approval_threshold_vnd: int
    agreement_confirm_ttl_seconds: int


@dataclass(frozen=True)
class BookingPartiesDTO:
    """Thông tin các bên tham gia và chi tiết booking để sinh thỏa thuận."""

    booking_id: UUID
    zone_id: UUID
    slot_id: UUID
    slot_code: str
    provider_user_id: UUID
    provider_name: str
    renter_user_id: UUID
    renter_name: str
    price_vnd: int
    period_start: datetime
    period_end: datetime
    booking_status: str


class AgreementRepositoryPort(Protocol):
    """Port giao tiếp tầng dữ liệu cho module Agreement."""

    async def get_by_id(self, conn: Any, agreement_id: UUID) -> AgreementRecord | None:
        """Lấy thỏa thuận theo ID."""
        ...

    async def get_by_booking_id(self, conn: Any, booking_id: UUID) -> AgreementRecord | None:
        """Lấy thỏa thuận theo booking_id (1:1 relation)."""
        ...

    async def create_agreement(self, conn: Any, agreement: AgreementRecord) -> AgreementRecord:
        """Lưu bản ghi thỏa thuận mới vào app.agreement."""
        ...

    async def get_active_zone_policy(self, conn: Any, zone_id: UUID) -> ZonePolicyDTO | None:
        """Lấy chính sách hiện hành của khu (app.current_zone_policy)."""
        ...

    async def get_booking_parties(self, conn: Any, booking_id: UUID) -> BookingPartiesDTO | None:
        """Lấy thông tin các bên tham gia booking để điền vào thỏa thuận."""
        ...

    async def update_booking_status_pending_agreement(self, conn: Any, booking_id: UUID) -> None:
        """Cập nhật trạng thái booking sang 'pending_agreement'."""
        ...
