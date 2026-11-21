"""Unit tests for Agreement OTP endpoints in Router (M6, SCRUM-100)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.agreement.delivery.router import create_agreement_router
from app.agreement.domain.models import AgreementRecord
from app.agreement.infrastructure.otp_service import InMemoryOtpService
from app.agreement.usecase.confirm_agreement import ConfirmAgreementUseCase
from app.agreement.usecase.get_agreement import GetAgreementUseCase
from app.agreement.usecase.send_agreement_otp import SendAgreementOtpUseCase


@pytest.fixture
def test_setup(mock_repo_cls: Any, sample_agreement: AgreementRecord) -> dict[str, Any]:
    repo = mock_repo_cls(existing_agreement=sample_agreement)
    otp_svc = InMemoryOtpService()
    get_uc = GetAgreementUseCase(repo=repo)
    confirm_uc = ConfirmAgreementUseCase(repo=repo, otp_service=otp_svc)
    send_otp_uc = SendAgreementOtpUseCase(repo=repo, otp_service=otp_svc)

    @asynccontextmanager
    async def fake_uow(uid: UUID | None, zids: list[UUID] | None) -> AsyncIterator[Any]:
        yield None

    router = create_agreement_router(
        get_use_case=get_uc,
        confirm_use_case=confirm_uc,
        send_otp_use_case=send_otp_uc,
        repo=repo,
        uow_factory=fake_uow,
    )

    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)

    return {
        "app": app,
        "repo": repo,
        "otp_svc": otp_svc,
        "agreement": sample_agreement,
    }


@pytest.mark.asyncio
async def test_send_otp_endpoint_success(test_setup: dict[str, Any]) -> None:
    app = test_setup["app"]
    ag = test_setup["agreement"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/agreements/{ag.id}/otp/send",
            headers={"X-User-Id": str(ag.renter_user_id)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "renter"
        assert len(data["dev_otp"]) == 6
        assert data["ttl_seconds"] > 0


@pytest.mark.asyncio
async def test_send_otp_endpoint_missing_auth_returns_401(test_setup: dict[str, Any]) -> None:
    app = test_setup["app"]
    ag = test_setup["agreement"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(f"/api/v1/agreements/{ag.id}/otp/send")
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_confirm_endpoint_success_and_consent_record_list(test_setup: dict[str, Any]) -> None:
    app = test_setup["app"]
    ag = test_setup["agreement"]
    otp_svc = test_setup["otp_svc"]

    code = await otp_svc.issue_otp(ag.id, ag.renter_user_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Confirm OTP
        resp = await client.post(
            f"/api/v1/agreements/{ag.id}/confirm",
            headers={"X-User-Id": str(ag.renter_user_id)},
            json={"otp_code": code},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["confirmed_role"] == "renter"
        assert data["both_confirmed"] is False
        assert data["next_action"] == "WAIT_FOR_OTHER_PARTY"
        assert data["consent_record"]["action"] == "agreement_confirm"

        # 2. Get consent records list
        rec_resp = await client.get(
            f"/api/v1/agreements/{ag.id}/consent-records",
            headers={"X-User-Id": str(ag.renter_user_id), "X-Role": "renter"},
        )
        assert rec_resp.status_code == 200
        records = rec_resp.json()
        assert len(records) == 1
        assert records[0]["action"] == "agreement_confirm"


@pytest.mark.asyncio
async def test_confirm_endpoint_invalid_otp_returns_422(test_setup: dict[str, Any]) -> None:
    app = test_setup["app"]
    ag = test_setup["agreement"]
    otp_svc = test_setup["otp_svc"]

    await otp_svc.issue_otp(ag.id, ag.renter_user_id)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/agreements/{ag.id}/confirm",
            headers={"X-User-Id": str(ag.renter_user_id)},
            json={"otp_code": "000000"},
        )
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_confirm_endpoint_unauthorized_stranger_returns_403(test_setup: dict[str, Any]) -> None:
    app = test_setup["app"]
    ag = test_setup["agreement"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/agreements/{ag.id}/confirm",
            headers={"X-User-Id": str(uuid4())},
            json={"otp_code": "123456"},
        )
        assert resp.status_code == 403
