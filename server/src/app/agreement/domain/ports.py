"""Domain ports và DTOs cho Agreement module (M6)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from app.agreement.domain.models import AgreementRecord, ConsentRecord


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

    async def append_consent_record(self, conn: Any, record: ConsentRecord) -> ConsentRecord:
        """Ghi bằng chứng xác nhận vào app.consent_record (append-only, FR-09)."""
        ...

    async def get_consent_records_by_agreement(self, conn: Any, agreement_id: UUID) -> list[ConsentRecord]:
        """Truy vấn các bằng chứng xác nhận của một thỏa thuận."""
        ...

    async def update_party_confirmation(
        self,
        conn: Any,
        agreement_id: UUID,
        role: str,
        confirmed_at: datetime,
    ) -> AgreementRecord:
        """Cập nhật mốc thời gian xác nhận của một bên (provider hoặc renter)."""
        ...

    async def activate_agreement(
        self,
        conn: Any,
        agreement_id: UUID,
        booking_id: UUID,
        effective_at: datetime,
    ) -> AgreementRecord:
        """Kích hoạt thỏa thuận (effective) và chuyển booking sang 'confirmed'."""
        ...

    async def mark_agreement_pending_approval(
        self,
        conn: Any,
        agreement_id: UUID,
        booking_id: UUID,
        zone_id: UUID,
        price_vnd: int,
        thread_id: str | None = None,
    ) -> tuple[AgreementRecord, UUID]:
        """Tạo approval_request cho BQL và chuyển thỏa thuận + booking sang 'pending_approval'."""
        ...


class OtpServicePort(Protocol):
    """Port dịch vụ OTP (lưu trữ Redis hoặc cache tạm)."""

    async def issue_otp(self, agreement_id: UUID, user_id: UUID, ttl_seconds: int = 1800) -> str:
        """Phát sinh mã OTP ngẫu nhiên (6 chữ số), lưu vào cache với TTL."""
        ...

    async def verify_otp(self, agreement_id: UUID, user_id: UUID, code: str) -> bool:
        """Xác thực mã OTP. Trả về True nếu đúng, raise lỗi nếu hết lượt hoặc hết hạn."""
        ...

    async def invalidate_otp(self, agreement_id: UUID, user_id: UUID) -> None:
        """Xóa mã OTP sau khi xác nhận thành công."""
        ...
