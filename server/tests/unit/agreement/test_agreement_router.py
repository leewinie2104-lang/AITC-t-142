"""Unit tests for Agreement FastAPI Router (M6, SCRUM-99)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from app.agreement.delivery.router import create_agreement_router
from app.agreement.domain.exceptions import (
    AgreementAccessDeniedError,
    AgreementNotFoundError,
    BookingNotFoundError,
    ZonePolicyNotFoundError,
)
from app.agreement.domain.models import AgreementRecord
from app.agreement.usecase.generate_agreement import (
    GenerateAgreementResult,
    GenerateAgreementUseCase,
)
from app.agreement.usecase.get_agreement import GetAgreementUseCase


@pytest.fixture
def mock_get_use_case() -> AsyncMock:
    return AsyncMock(spec=GetAgreementUseCase)


@pytest.fixture
def mock_generate_use_case() -> AsyncMock:
    return AsyncMock(spec=GenerateAgreementUseCase)


@asynccontextmanager
async def mock_uow(user_id: UUID | None, zone_ids: list[UUID] | None) -> AsyncIterator[Any]:
    yield AsyncMock()


@pytest.fixture
def client(mock_get_use_case: AsyncMock, mock_generate_use_case: AsyncMock) -> TestClient:
    app = FastAPI()
    router = create_agreement_router(
        get_use_case=mock_get_use_case,
        generate_use_case=mock_generate_use_case,
        uow_factory=mock_uow,
    )
    app.include_router(router)
    return TestClient(app)


def test_get_agreement_success(
    client: TestClient, mock_get_use_case: AsyncMock, sample_agreement: AgreementRecord
) -> None:
    mock_get_use_case.execute.return_value = sample_agreement

    resp = client.get(
        f"/api/v1/agreements/{sample_agreement.id}",
        headers={"x-user-id": str(sample_agreement.renter_user_id), "x-role": "renter"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(sample_agreement.id)
    assert data["body_sha256"] == sample_agreement.body_sha256_hex
    assert data["status"] == "pending_confirmation"
    assert data["requires_approval"] is False


def test_get_agreement_missing_auth(client: TestClient) -> None:
    resp = client.get(f"/api/v1/agreements/{uuid4()}")
    assert resp.status_code == 401
    assert "Missing authentication" in resp.json()["detail"]


def test_get_agreement_forbidden(client: TestClient, mock_get_use_case: AsyncMock) -> None:
    ag_id = uuid4()
    user_id = uuid4()
    mock_get_use_case.execute.side_effect = AgreementAccessDeniedError(ag_id, user_id)

    resp = client.get(
        f"/api/v1/agreements/{ag_id}",
        headers={"x-user-id": str(user_id), "x-role": "renter"},
    )
    assert resp.status_code == 403


def test_get_agreement_not_found(client: TestClient, mock_get_use_case: AsyncMock) -> None:
    ag_id = uuid4()
    mock_get_use_case.execute.side_effect = AgreementNotFoundError(ag_id)

    resp = client.get(
        f"/api/v1/agreements/{ag_id}",
        headers={"x-user-id": str(uuid4()), "x-role": "renter"},
    )
    assert resp.status_code == 404


def test_generate_agreement_success(
    client: TestClient, mock_generate_use_case: AsyncMock, sample_agreement: AgreementRecord
) -> None:
    mock_generate_use_case.execute.return_value = GenerateAgreementResult(
        agreement=sample_agreement,
        is_replay=False,
        message="Sinh thành công",
    )

    resp = client.post(
        "/api/v1/agreements/generate",
        json={"booking_id": str(sample_agreement.booking_id)},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["is_replay"] is False
    assert data["agreement"]["id"] == str(sample_agreement.id)


def test_generate_agreement_replay(
    client: TestClient, mock_generate_use_case: AsyncMock, sample_agreement: AgreementRecord
) -> None:
    mock_generate_use_case.execute.return_value = GenerateAgreementResult(
        agreement=sample_agreement,
        is_replay=True,
        message="Đã sinh trước đó",
    )

    resp = client.post(
        "/api/v1/agreements/generate",
        json={"booking_id": str(sample_agreement.booking_id)},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["is_replay"] is True


def test_generate_agreement_booking_not_found(client: TestClient, mock_generate_use_case: AsyncMock) -> None:
    b_id = uuid4()
    mock_generate_use_case.execute.side_effect = BookingNotFoundError(b_id)

    resp = client.post(
        "/api/v1/agreements/generate",
        json={"booking_id": str(b_id)},
    )
    assert resp.status_code == 404


def test_generate_agreement_policy_not_found(client: TestClient, mock_generate_use_case: AsyncMock) -> None:
    mock_generate_use_case.execute.side_effect = ZonePolicyNotFoundError(uuid4())

    resp = client.post(
        "/api/v1/agreements/generate",
        json={"booking_id": str(uuid4())},
    )
    assert resp.status_code == 422
