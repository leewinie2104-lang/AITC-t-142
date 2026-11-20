from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient

from app.booking.delivery.router import create_booking_router
from app.booking.domain.models import HeldBookingRecord, RequestOutcome
from app.booking.usecase.request_parking import (
    RequestParkingResult,
    RequestParkingUseCase,
)


def _dt(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 11, 20, hour, minute, tzinfo=UTC)


@pytest.fixture
def mock_use_case() -> AsyncMock:
    return AsyncMock(spec=RequestParkingUseCase)


@asynccontextmanager
async def mock_uow(user_id: UUID | None, zone_ids: list[UUID] | None) -> AsyncIterator[Any]:
    yield AsyncMock()


@pytest.fixture
def client(mock_use_case: AsyncMock) -> TestClient:
    app = FastAPI()
    router = create_booking_router(use_case=mock_use_case, uow_factory=mock_uow)
    app.include_router(router)
    return TestClient(app)


def _make_payload(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "zone_id": str(uuid4()),
        "building_id": str(uuid4()),
        "requester_user_id": str(uuid4()),
        "vehicle_id": str(uuid4()),
        "vehicle_size": "M",
        "period_start": _dt(10, 0).isoformat(),
        "period_end": _dt(17, 0).isoformat(),
        "computed_level": "L1",
        "channel": "app",
        "idempotency_key": "key_test_123",
    }
    base.update(overrides)
    return base


def test_router_request_parking_success(client: TestClient, mock_use_case: AsyncMock):
    req_id = uuid4()
    booking_id = uuid4()
    hold_expires = _dt(10, 10)

    mock_use_case.execute.return_value = RequestParkingResult(
        outcome=RequestOutcome.matched,
        request_id=req_id,
        booking=HeldBookingRecord(
            id=booking_id,
            ref_no=123,
            status="held",
            hold_expires_at=hold_expires,
            created_at=_dt(10, 0),
        ),
        message="Giữ chỗ tạm thời thành công",
    )

    resp = client.post("/api/v1/bookings/request", json=_make_payload())
    assert resp.status_code == 201
    data = resp.json()
    assert data["outcome"] == "matched"
    assert data["booking"]["booking_id"] == str(booking_id)
    assert data["booking"]["ref_no"] == 123


def test_router_request_parking_validation_error(client: TestClient, mock_use_case: AsyncMock):
    # start >= end -> usecase ném ValueError
    mock_use_case.execute.side_effect = ValueError("period_start must be before period_end")

    payload = _make_payload(
        period_start=_dt(17, 0).isoformat(),
        period_end=_dt(10, 0).isoformat(),
        idempotency_key="key_test_invalid",
    )
    resp = client.post("/api/v1/bookings/request", json=payload)
    assert resp.status_code == 422
    assert "period_start must be before period_end" in resp.json()["detail"]
