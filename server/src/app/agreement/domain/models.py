"""Domain models and value objects for the Agreement module (M6)."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID


class AgreementStatus(StrEnum):
    """Trạng thái vòng đời của thỏa thuận (app.agreement_status)."""

    pending_confirmation = "pending_confirmation"
    pending_approval = "pending_approval"
    effective = "effective"
    rejected = "rejected"
    expired = "expired"
    cancelled = "cancelled"


class ConsentAction(StrEnum):
    """Hành động đồng ý pháp lý (app.consent_action)."""

    registration_terms = "registration_terms"
    plate_processing = "plate_processing"
    agreement_confirm = "agreement_confirm"
    accept_relocation = "accept_relocation"


class ConsentDecision(StrEnum):
    """Quyết định đồng ý (app.consent_decision)."""

    accepted = "accepted"
    rejected = "rejected"
    withdrawn = "withdrawn"


class NextAction(StrEnum):
    """Hành động tiếp theo sau khi xác nhận thỏa thuận (phục vụ FE và AI Agent)."""

    WAIT_FOR_OTHER_PARTY = "WAIT_FOR_OTHER_PARTY"
    PENDING_BQL_APPROVAL = "PENDING_BQL_APPROVAL"
    BOOKING_ACTIVE = "BOOKING_ACTIVE"


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


@dataclass(frozen=True)
class ConsentRecord:
    """Bản ghi bằng chứng xác nhận đồng ý chỉ ghi thêm (app.consent_record, FR-09)."""

    user_id: UUID
    action: ConsentAction
    subject_type: str  # 'app_user', 'agreement', 'recovery_case'
    subject_id: UUID
    terms_version: str
    decision: ConsentDecision
    evidence: dict[str, Any] = field(default_factory=dict)
    zone_id: UUID | None = None
    id: int | None = None
    created_at: datetime | None = None
