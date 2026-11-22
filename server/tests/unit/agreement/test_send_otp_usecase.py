"""Unit tests for SendAgreementOtpUseCase (SCRUM-100, M6)."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest

from app.agreement.domain.exceptions import (
    AgreementAccessDeniedError,
    AgreementExpiredError,
    AgreementNotFoundError,
    PartyAlreadyConfirmedError,
)
from app.agreement.domain.models import AgreementRecord, AgreementStatus
from app.agreement.infrastructure.otp_service import InMemoryOtpService
from app.agreement.usecase.send_agreement_otp import (
    SendAgreementOtpCommand,
    SendAgreementOtpUseCase,
)


@pytest.fixture
def otp_service() -> InMemoryOtpService:
    return InMemoryOtpService()


@pytest.mark.asyncio
async def test_send_otp_success_for_renter_and_provider(
    mock_repo_cls: Any,
    sample_agreement: AgreementRecord,
    otp_service: InMemoryOtpService,
) -> None:
    repo = mock_repo_cls(existing_agreement=sample_agreement)
    use_case = SendAgreementOtpUseCase(repo=repo, otp_service=otp_service)

    # 1. Renter requests OTP
    r_res = await use_case.execute(
        conn=None,
        cmd=SendAgreementOtpCommand(agreement_id=sample_agreement.id, user_id=sample_agreement.renter_user_id),
    )
    assert r_res.role == "renter"
    assert len(r_res.dev_otp) == 6
    assert r_res.ttl_seconds > 0

    # 2. Provider requests OTP
    p_res = await use_case.execute(
        conn=None,
        cmd=SendAgreementOtpCommand(agreement_id=sample_agreement.id, user_id=sample_agreement.provider_user_id),
    )
    assert p_res.role == "provider"
    assert len(p_res.dev_otp) == 6


@pytest.mark.asyncio
async def test_send_otp_party_already_confirmed_raises_error(
    mock_repo_cls: Any,
    sample_agreement: AgreementRecord,
    otp_service: InMemoryOtpService,
) -> None:
    confirmed_agreement = AgreementRecord(
        id=sample_agreement.id,
        zone_id=sample_agreement.zone_id,
        booking_id=sample_agreement.booking_id,
        zone_policy_id=sample_agreement.zone_policy_id,
        provider_user_id=sample_agreement.provider_user_id,
        renter_user_id=sample_agreement.renter_user_id,
        price_vnd=sample_agreement.price_vnd,
        body_rendered=sample_agreement.body_rendered,
        body_sha256=sample_agreement.body_sha256,
        status=AgreementStatus.pending_confirmation,
        requires_approval=False,
        confirm_deadline=datetime.now(UTC) + timedelta(minutes=30),
        renter_confirmed_at=datetime.now(UTC),
    )
    repo = mock_repo_cls(existing_agreement=confirmed_agreement)
    use_case = SendAgreementOtpUseCase(repo=repo, otp_service=otp_service)

    with pytest.raises(PartyAlreadyConfirmedError):
        await use_case.execute(
            conn=None,
            cmd=SendAgreementOtpCommand(
                agreement_id=confirmed_agreement.id, user_id=confirmed_agreement.renter_user_id
            ),
        )


@pytest.mark.asyncio
async def test_send_otp_unauthorized_user_raises_error(
    mock_repo_cls: Any,
    sample_agreement: AgreementRecord,
    otp_service: InMemoryOtpService,
) -> None:
    repo = mock_repo_cls(existing_agreement=sample_agreement)
    use_case = SendAgreementOtpUseCase(repo=repo, otp_service=otp_service)

    with pytest.raises(AgreementAccessDeniedError):
        await use_case.execute(
            conn=None,
            cmd=SendAgreementOtpCommand(agreement_id=sample_agreement.id, user_id=uuid4()),
        )


@pytest.mark.asyncio
async def test_send_otp_expired_agreement_raises_error(
    mock_repo_cls: Any,
    sample_agreement: AgreementRecord,
    otp_service: InMemoryOtpService,
) -> None:
    expired_agreement = AgreementRecord(
        id=sample_agreement.id,
        zone_id=sample_agreement.zone_id,
        booking_id=sample_agreement.booking_id,
        zone_policy_id=sample_agreement.zone_policy_id,
        provider_user_id=sample_agreement.provider_user_id,
        renter_user_id=sample_agreement.renter_user_id,
        price_vnd=sample_agreement.price_vnd,
        body_rendered=sample_agreement.body_rendered,
        body_sha256=sample_agreement.body_sha256,
        status=AgreementStatus.pending_confirmation,
        requires_approval=False,
        confirm_deadline=datetime.now(UTC) - timedelta(minutes=1),
    )
    repo = mock_repo_cls(existing_agreement=expired_agreement)
    use_case = SendAgreementOtpUseCase(repo=repo, otp_service=otp_service)

    with pytest.raises(AgreementExpiredError):
        await use_case.execute(
            conn=None,
            cmd=SendAgreementOtpCommand(agreement_id=expired_agreement.id, user_id=expired_agreement.renter_user_id),
        )


@pytest.mark.asyncio
async def test_send_otp_not_found_raises_error(
    mock_repo_cls: Any,
    otp_service: InMemoryOtpService,
) -> None:
    repo = mock_repo_cls()
    use_case = SendAgreementOtpUseCase(repo=repo, otp_service=otp_service)

    with pytest.raises(AgreementNotFoundError):
        await use_case.execute(
            conn=None,
            cmd=SendAgreementOtpCommand(agreement_id=uuid4(), user_id=uuid4()),
        )
