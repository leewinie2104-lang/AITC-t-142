"""Unit tests for ConfirmAgreementUseCase (SCRUM-100, M6)."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest

from app.agreement.domain.exceptions import (
    AgreementAccessDeniedError,
    AgreementExpiredError,
    AgreementNotFoundError,
    AgreementNotPendingError,
    InvalidOtpError,
    OtpExpiredError,
    PartyAlreadyConfirmedError,
)
from app.agreement.domain.models import AgreementRecord, AgreementStatus, NextAction
from app.agreement.infrastructure.otp_service import InMemoryOtpService
from app.agreement.usecase.confirm_agreement import (
    ConfirmAgreementCommand,
    ConfirmAgreementUseCase,
)


@pytest.fixture
def otp_service() -> InMemoryOtpService:
    return InMemoryOtpService()


@pytest.mark.asyncio
async def test_renter_confirm_first_awaits_other_party(
    mock_repo_cls: Any,
    sample_agreement: AgreementRecord,
    otp_service: InMemoryOtpService,
) -> None:
    repo = mock_repo_cls(existing_agreement=sample_agreement)
    use_case = ConfirmAgreementUseCase(repo=repo, otp_service=otp_service)

    # Issue OTP for renter
    code = await otp_service.issue_otp(sample_agreement.id, sample_agreement.renter_user_id)

    cmd = ConfirmAgreementCommand(
        agreement_id=sample_agreement.id,
        user_id=sample_agreement.renter_user_id,
        otp_code=code,
    )
    result = await use_case.execute(conn=None, cmd=cmd)

    assert result.confirmed_role == "renter"
    assert result.both_confirmed is False
    assert result.next_action == NextAction.WAIT_FOR_OTHER_PARTY
    assert result.agreement.renter_confirmed_at is not None
    assert result.agreement.provider_confirmed_at is None
    assert result.agreement.status == AgreementStatus.pending_confirmation
    assert len(repo.consent_records) == 1
    assert repo.consent_records[0].action == "agreement_confirm"
    assert repo.consent_records[0].user_id == sample_agreement.renter_user_id
    assert "chủ chỗ" in result.agent_summary


@pytest.mark.asyncio
async def test_both_parties_confirm_normal_agreement_becomes_effective(
    mock_repo_cls: Any,
    sample_agreement: AgreementRecord,
    otp_service: InMemoryOtpService,
) -> None:
    repo = mock_repo_cls(existing_agreement=sample_agreement)
    use_case = ConfirmAgreementUseCase(repo=repo, otp_service=otp_service)

    # 1. Renter confirms
    code_renter = await otp_service.issue_otp(sample_agreement.id, sample_agreement.renter_user_id)
    await use_case.execute(
        conn=None,
        cmd=ConfirmAgreementCommand(
            agreement_id=sample_agreement.id,
            user_id=sample_agreement.renter_user_id,
            otp_code=code_renter,
        ),
    )

    # 2. Provider confirms
    code_provider = await otp_service.issue_otp(sample_agreement.id, sample_agreement.provider_user_id)
    result = await use_case.execute(
        conn=None,
        cmd=ConfirmAgreementCommand(
            agreement_id=sample_agreement.id,
            user_id=sample_agreement.provider_user_id,
            otp_code=code_provider,
        ),
    )

    assert result.confirmed_role == "provider"
    assert result.both_confirmed is True
    assert result.next_action == NextAction.BOOKING_ACTIVE
    assert result.agreement.status == AgreementStatus.effective
    assert result.agreement.effective_at is not None
    assert len(repo.consent_records) == 2
    assert sample_agreement.booking_id in repo.updated_bookings
    assert "chính thức có hiệu lực" in result.agent_summary


@pytest.mark.asyncio
async def test_both_parties_confirm_over_threshold_creates_approval_request(
    mock_repo_cls: Any,
    sample_agreement: AgreementRecord,
    otp_service: InMemoryOtpService,
) -> None:
    over_threshold = AgreementRecord(
        id=sample_agreement.id,
        zone_id=sample_agreement.zone_id,
        booking_id=sample_agreement.booking_id,
        zone_policy_id=sample_agreement.zone_policy_id,
        provider_user_id=sample_agreement.provider_user_id,
        renter_user_id=sample_agreement.renter_user_id,
        price_vnd=1_500_000,
        body_rendered=sample_agreement.body_rendered,
        body_sha256=sample_agreement.body_sha256,
        status=AgreementStatus.pending_confirmation,
        requires_approval=True,
        confirm_deadline=datetime.now(UTC) + timedelta(minutes=30),
    )
    repo = mock_repo_cls(existing_agreement=over_threshold)
    use_case = ConfirmAgreementUseCase(repo=repo, otp_service=otp_service)

    # 1. Renter confirms
    r_code = await otp_service.issue_otp(over_threshold.id, over_threshold.renter_user_id)
    await use_case.execute(
        conn=None,
        cmd=ConfirmAgreementCommand(
            agreement_id=over_threshold.id, user_id=over_threshold.renter_user_id, otp_code=r_code
        ),
    )

    # 2. Provider confirms with thread_id
    p_code = await otp_service.issue_otp(over_threshold.id, over_threshold.provider_user_id)
    result = await use_case.execute(
        conn=None,
        cmd=ConfirmAgreementCommand(
            agreement_id=over_threshold.id,
            user_id=over_threshold.provider_user_id,
            otp_code=p_code,
            thread_id="thread-w2-hitl-123",
        ),
    )

    assert result.both_confirmed is True
    assert result.next_action == NextAction.PENDING_BQL_APPROVAL
    assert result.agreement.status == AgreementStatus.pending_approval
    assert result.approval_request_id is not None
    assert len(repo.approval_requests) == 1
    assert repo.approval_requests[0]["thread_id"] == "thread-w2-hitl-123"
    assert over_threshold.booking_id in repo.updated_bookings
    assert "Ban Quản Lý" in result.agent_summary


@pytest.mark.asyncio
async def test_confirm_with_invalid_otp_raises_error(
    mock_repo_cls: Any,
    sample_agreement: AgreementRecord,
    otp_service: InMemoryOtpService,
) -> None:
    repo = mock_repo_cls(existing_agreement=sample_agreement)
    use_case = ConfirmAgreementUseCase(repo=repo, otp_service=otp_service)

    await otp_service.issue_otp(sample_agreement.id, sample_agreement.renter_user_id)

    with pytest.raises(InvalidOtpError):
        await use_case.execute(
            conn=None,
            cmd=ConfirmAgreementCommand(
                agreement_id=sample_agreement.id,
                user_id=sample_agreement.renter_user_id,
                otp_code="000000",
            ),
        )


@pytest.mark.asyncio
async def test_confirm_without_issuing_otp_raises_expired_error(
    mock_repo_cls: Any,
    sample_agreement: AgreementRecord,
    otp_service: InMemoryOtpService,
) -> None:
    repo = mock_repo_cls(existing_agreement=sample_agreement)
    use_case = ConfirmAgreementUseCase(repo=repo, otp_service=otp_service)

    with pytest.raises(OtpExpiredError):
        await use_case.execute(
            conn=None,
            cmd=ConfirmAgreementCommand(
                agreement_id=sample_agreement.id,
                user_id=sample_agreement.renter_user_id,
                otp_code="123456",
            ),
        )


@pytest.mark.asyncio
async def test_party_already_confirmed_cannot_confirm_again(
    mock_repo_cls: Any,
    sample_agreement: AgreementRecord,
    otp_service: InMemoryOtpService,
) -> None:
    repo = mock_repo_cls(existing_agreement=sample_agreement)
    use_case = ConfirmAgreementUseCase(repo=repo, otp_service=otp_service)

    code = await otp_service.issue_otp(sample_agreement.id, sample_agreement.renter_user_id)
    await use_case.execute(
        conn=None,
        cmd=ConfirmAgreementCommand(
            agreement_id=sample_agreement.id,
            user_id=sample_agreement.renter_user_id,
            otp_code=code,
        ),
    )

    code2 = await otp_service.issue_otp(sample_agreement.id, sample_agreement.renter_user_id)
    with pytest.raises(PartyAlreadyConfirmedError):
        await use_case.execute(
            conn=None,
            cmd=ConfirmAgreementCommand(
                agreement_id=sample_agreement.id,
                user_id=sample_agreement.renter_user_id,
                otp_code=code2,
            ),
        )


@pytest.mark.asyncio
async def test_unauthorized_user_cannot_confirm(
    mock_repo_cls: Any,
    sample_agreement: AgreementRecord,
    otp_service: InMemoryOtpService,
) -> None:
    repo = mock_repo_cls(existing_agreement=sample_agreement)
    use_case = ConfirmAgreementUseCase(repo=repo, otp_service=otp_service)

    stranger_id = uuid4()
    with pytest.raises(AgreementAccessDeniedError):
        await use_case.execute(
            conn=None,
            cmd=ConfirmAgreementCommand(
                agreement_id=sample_agreement.id,
                user_id=stranger_id,
                otp_code="123456",
            ),
        )


@pytest.mark.asyncio
async def test_expired_agreement_cannot_be_confirmed(
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
        confirm_deadline=datetime.now(UTC) - timedelta(minutes=5),
    )
    repo = mock_repo_cls(existing_agreement=expired_agreement)
    use_case = ConfirmAgreementUseCase(repo=repo, otp_service=otp_service)

    with pytest.raises(AgreementExpiredError):
        await use_case.execute(
            conn=None,
            cmd=ConfirmAgreementCommand(
                agreement_id=expired_agreement.id,
                user_id=expired_agreement.renter_user_id,
                otp_code="123456",
            ),
        )


@pytest.mark.asyncio
async def test_non_existent_agreement_raises_not_found(
    mock_repo_cls: Any,
    otp_service: InMemoryOtpService,
) -> None:
    repo = mock_repo_cls()
    use_case = ConfirmAgreementUseCase(repo=repo, otp_service=otp_service)

    with pytest.raises(AgreementNotFoundError):
        await use_case.execute(
            conn=None,
            cmd=ConfirmAgreementCommand(
                agreement_id=uuid4(),
                user_id=uuid4(),
                otp_code="123456",
            ),
        )


@pytest.mark.asyncio
async def test_agreement_not_pending_raises_error(
    mock_repo_cls: Any,
    sample_agreement: AgreementRecord,
    otp_service: InMemoryOtpService,
) -> None:
    active_agreement = AgreementRecord(
        id=sample_agreement.id,
        zone_id=sample_agreement.zone_id,
        booking_id=sample_agreement.booking_id,
        zone_policy_id=sample_agreement.zone_policy_id,
        provider_user_id=sample_agreement.provider_user_id,
        renter_user_id=sample_agreement.renter_user_id,
        price_vnd=sample_agreement.price_vnd,
        body_rendered=sample_agreement.body_rendered,
        body_sha256=sample_agreement.body_sha256,
        status=AgreementStatus.effective,
        requires_approval=False,
        confirm_deadline=datetime.now(UTC) + timedelta(minutes=30),
    )
    repo = mock_repo_cls(existing_agreement=active_agreement)
    use_case = ConfirmAgreementUseCase(repo=repo, otp_service=otp_service)

    with pytest.raises(AgreementNotPendingError):
        await use_case.execute(
            conn=None,
            cmd=ConfirmAgreementCommand(
                agreement_id=active_agreement.id,
                user_id=active_agreement.renter_user_id,
                otp_code="123456",
            ),
        )
