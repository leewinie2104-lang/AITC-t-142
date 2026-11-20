"""Domain models and value objects for the Agreement module (M6)."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class AgreementStatus(StrEnum):
    """Trạng thái vòng đời của thỏa thuận (app.agreement_status)."""

    pending_confirmation = "pending_confirmation"
    pending_approval = "pending_approval"
    effective = "effective"
    rejected = "rejected"
    expired = "expired"
    cancelled = "cancelled"


@dataclass(frozen=True)
class AgreementRecord:
    """Bản ghi thỏa thuận chia sẻ chỗ đỗ (app.agreement)."""

    id: UUID
    zone_id: UUID
    booking_id: UUID
    zone_policy_id: UUID
    provider_user_id: UUID
    renter_user_id: UUID
    price_vnd: int
    body_rendered: str
    body_sha256: bytes  # Length must be 32 bytes (CHECK length(body_sha256) = 32)
    status: AgreementStatus
    requires_approval: bool  # True nếu price_vnd >= policy.approval_threshold_vnd (BR-12)
    confirm_deadline: datetime
    approval_request_id: UUID | None = None
    provider_confirmed_at: datetime | None = None
    renter_confirmed_at: datetime | None = None
    effective_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def body_sha256_hex(self) -> str:
        """Chuỗi hex của body_sha256 phục vụ đối chiếu và API response."""
        return self.body_sha256.hex()
