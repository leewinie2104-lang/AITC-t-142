"""Domain exports cho module Agreement (M6)."""

from app.agreement.domain.exceptions import (
    AgreementAccessDeniedError,
    AgreementError,
    AgreementExpiredError,
    AgreementNotFoundError,
    AgreementNotPendingError,
    BookingNotFoundError,
    InvalidOtpError,
    OtpExpiredError,
    OtpMaxAttemptsExceededError,
    PartyAlreadyConfirmedError,
    ZonePolicyNotFoundError,
)
from app.agreement.domain.models import (
    AgreementRecord,
    AgreementStatus,
    ConsentAction,
    ConsentDecision,
    ConsentRecord,
    NextAction,
)
from app.agreement.domain.ports import (
    AgreementRepositoryPort,
    BookingPartiesDTO,
    OtpServicePort,
    ZonePolicyDTO,
)
from app.agreement.domain.rendering import (
    check_requires_approval,
    compute_body_hash,
    format_vn_datetime,
    render_agreement_template,
)

__all__ = [
    "AgreementAccessDeniedError",
    "AgreementError",
    "AgreementExpiredError",
    "AgreementNotFoundError",
    "AgreementNotPendingError",
    "AgreementRecord",
    "AgreementRepositoryPort",
    "AgreementStatus",
    "BookingNotFoundError",
    "BookingPartiesDTO",
    "ConsentAction",
    "ConsentDecision",
    "ConsentRecord",
    "InvalidOtpError",
    "NextAction",
    "OtpExpiredError",
    "OtpMaxAttemptsExceededError",
    "OtpServicePort",
    "PartyAlreadyConfirmedError",
    "ZonePolicyDTO",
    "ZonePolicyNotFoundError",
    "check_requires_approval",
    "compute_body_hash",
    "format_vn_datetime",
    "render_agreement_template",
]
