"""Unit tests for GetAgreementUseCase (M6, SCRUM-99)."""

from typing import Any
from uuid import uuid4

import pytest

from app.agreement.domain.exceptions import (
    AgreementAccessDeniedError,
    AgreementNotFoundError,
)
from app.agreement.domain.models import AgreementRecord
from app.agreement.usecase.get_agreement import (
    GetAgreementQuery,
    GetAgreementUseCase,
)


@pytest.mark.asyncio
async def test_get_agreement_success_by_renter(
    mock_repo_cls: Any,
    sample_agreement: AgreementRecord,
) -> None:
    repo = mock_repo_cls(existing_agreement=sample_agreement)
    use_case = GetAgreementUseCase(repo=repo)

    query = GetAgreementQuery(
        agreement_id=sample_agreement.id,
        requester_user_id=sample_agreement.renter_user_id,
        requester_role="renter",
        requester_zone_ids=[],
    )
    result = await use_case.execute(conn=None, query=query)
    assert result.id == sample_agreement.id


@pytest.mark.asyncio
async def test_get_agreement_success_by_provider(
    mock_repo_cls: Any,
    sample_agreement: AgreementRecord,
) -> None:
    repo = mock_repo_cls(existing_agreement=sample_agreement)
    use_case = GetAgreementUseCase(repo=repo)

    query = GetAgreementQuery(
        agreement_id=sample_agreement.id,
        requester_user_id=sample_agreement.provider_user_id,
        requester_role="resident",
        requester_zone_ids=[],
    )
    result = await use_case.execute(conn=None, query=query)
    assert result.id == sample_agreement.id


@pytest.mark.asyncio
async def test_get_agreement_success_by_zone_staff(
    mock_repo_cls: Any,
    sample_agreement: AgreementRecord,
) -> None:
    repo = mock_repo_cls(existing_agreement=sample_agreement)
    use_case = GetAgreementUseCase(repo=repo)

    query = GetAgreementQuery(
        agreement_id=sample_agreement.id,
        requester_user_id=uuid4(),  # Staff ID
        requester_role="zone_manager",
        requester_zone_ids=[sample_agreement.zone_id],  # Thuộc khu của ô đỗ
    )
    result = await use_case.execute(conn=None, query=query)
    assert result.id == sample_agreement.id


@pytest.mark.asyncio
async def test_get_agreement_access_denied_for_third_party(
    mock_repo_cls: Any,
    sample_agreement: AgreementRecord,
) -> None:
    repo = mock_repo_cls(existing_agreement=sample_agreement)
    use_case = GetAgreementUseCase(repo=repo)

    query = GetAgreementQuery(
        agreement_id=sample_agreement.id,
        requester_user_id=uuid4(),  # Người lạ
        requester_role="renter",
        requester_zone_ids=[],
    )
    with pytest.raises(AgreementAccessDeniedError):
        await use_case.execute(conn=None, query=query)


@pytest.mark.asyncio
async def test_get_agreement_not_found(mock_repo_cls: Any) -> None:
    repo = mock_repo_cls(existing_agreement=None)
    use_case = GetAgreementUseCase(repo=repo)

    query = GetAgreementQuery(
        agreement_id=uuid4(),
        requester_user_id=uuid4(),
        requester_role="renter",
        requester_zone_ids=[],
    )
    with pytest.raises(AgreementNotFoundError):
        await use_case.execute(conn=None, query=query)
