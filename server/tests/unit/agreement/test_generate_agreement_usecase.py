"""Unit tests for GenerateAgreementUseCase (M6, SCRUM-99)."""

from dataclasses import replace
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.agreement.domain.exceptions import (
    BookingNotFoundError,
    ZonePolicyNotFoundError,
)
from app.agreement.domain.models import AgreementRecord, AgreementStatus
from app.agreement.domain.ports import (
    BookingPartiesDTO,
    ZonePolicyDTO,
)
from app.agreement.usecase.generate_agreement import (
    GenerateAgreementCommand,
    GenerateAgreementUseCase,
)


@pytest.mark.asyncio
async def test_generate_agreement_success_under_threshold(
    mock_repo_cls: Any,
    sample_ids: dict[str, UUID],
    sample_policy: ZonePolicyDTO,
    sample_booking: BookingPartiesDTO,
) -> None:
    repo = mock_repo_cls(policy=sample_policy, booking=sample_booking)
    use_case = GenerateAgreementUseCase(repo=repo)

    cmd = GenerateAgreementCommand(booking_id=sample_ids["booking_id"])
    result = await use_case.execute(conn=None, cmd=cmd)

    assert not result.is_replay
    ag = result.agreement
    assert ag.booking_id == sample_ids["booking_id"]
    assert ag.zone_id == sample_ids["zone_id"]
    assert ag.provider_user_id == sample_ids["provider_id"]
    assert ag.renter_user_id == sample_ids["renter_id"]
    assert ag.price_vnd == 40_000
    assert not ag.requires_approval  # 40.000 < 1.000.000
    assert ag.status == AgreementStatus.pending_confirmation
    assert len(ag.body_sha256) == 32
    assert "Nguyễn Thị Lan" in ag.body_rendered
    assert "Trần Văn Bình" in ag.body_rendered
    assert "B2-045" in ag.body_rendered
    assert "40.000 đ" in ag.body_rendered

    # Verify repository calls
    assert sample_ids["booking_id"] in repo.updated_bookings
    assert ag.id in repo.saved_agreements


@pytest.mark.asyncio
async def test_generate_agreement_over_threshold_requires_approval(
    mock_repo_cls: Any,
    sample_ids: dict[str, UUID],
    sample_policy: ZonePolicyDTO,
    sample_booking: BookingPartiesDTO,
) -> None:
    # Giá 1.470.000đ >= 1.000.000đ (BR-12 / AC-15)
    booking_over = replace(sample_booking, price_vnd=1_470_000)
    repo = mock_repo_cls(policy=sample_policy, booking=booking_over)
    use_case = GenerateAgreementUseCase(repo=repo)

    cmd = GenerateAgreementCommand(booking_id=sample_ids["booking_id"])
    result = await use_case.execute(conn=None, cmd=cmd)

    assert result.agreement.requires_approval is True
    assert result.agreement.status == AgreementStatus.pending_confirmation


@pytest.mark.asyncio
async def test_generate_agreement_idempotent_replay(
    mock_repo_cls: Any,
    sample_ids: dict[str, UUID],
    sample_policy: ZonePolicyDTO,
    sample_booking: BookingPartiesDTO,
) -> None:
    existing = AgreementRecord(
        id=uuid4(),
        zone_id=sample_ids["zone_id"],
        booking_id=sample_ids["booking_id"],
        zone_policy_id=sample_ids["policy_id"],
        provider_user_id=sample_ids["provider_id"],
        renter_user_id=sample_ids["renter_id"],
        price_vnd=40_000,
        body_rendered="Thỏa thuận đã tồn tại trước đó",
        body_sha256=b"x" * 32,
        status=AgreementStatus.pending_confirmation,
        requires_approval=False,
        confirm_deadline=datetime.now(UTC),
    )
    repo = mock_repo_cls(
        policy=sample_policy,
        booking=sample_booking,
        existing_agreement=existing,
    )
    use_case = GenerateAgreementUseCase(repo=repo)

    cmd = GenerateAgreementCommand(booking_id=sample_ids["booking_id"])
    result = await use_case.execute(conn=None, cmd=cmd)

    assert result.is_replay is True
    assert result.agreement.id == existing.id
    assert len(repo.saved_agreements) == 0  # Không insert thêm bản ghi mới


@pytest.mark.asyncio
async def test_generate_agreement_booking_not_found(
    mock_repo_cls: Any,
    sample_ids: dict[str, UUID],
) -> None:
    repo = mock_repo_cls(policy=None, booking=None)
    use_case = GenerateAgreementUseCase(repo=repo)

    cmd = GenerateAgreementCommand(booking_id=sample_ids["booking_id"])
    with pytest.raises(BookingNotFoundError):
        await use_case.execute(conn=None, cmd=cmd)


@pytest.mark.asyncio
async def test_generate_agreement_zone_policy_not_found(
    mock_repo_cls: Any,
    sample_ids: dict[str, UUID],
    sample_booking: BookingPartiesDTO,
) -> None:
    repo = mock_repo_cls(policy=None, booking=sample_booking)
    use_case = GenerateAgreementUseCase(repo=repo)

    cmd = GenerateAgreementCommand(booking_id=sample_ids["booking_id"])
    with pytest.raises(ZonePolicyNotFoundError):
        await use_case.execute(conn=None, cmd=cmd)
