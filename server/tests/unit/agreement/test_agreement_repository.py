"""Unit tests for AgreementRepository mapping and queries (M6, SCRUM-99)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.agreement.domain.models import AgreementStatus
from app.agreement.infrastructure.agreement_repository import (
    AgreementRepository,
    _to_agreement_record,
    _to_booking_parties_dto,
    _to_zone_policy_dto,
)


def test_to_agreement_record_mapping() -> None:
    now = datetime.now(UTC)
    sha_bytes = b"k" * 32
    raw_row = {
        "id": uuid4(),
        "zone_id": uuid4(),
        "booking_id": uuid4(),
        "zone_policy_id": uuid4(),
        "provider_user_id": uuid4(),
        "renter_user_id": uuid4(),
        "price_vnd": 50_000,
        "body_rendered": "# Thỏa thuận",
        "body_sha256": memoryview(sha_bytes),
        "status": "pending_confirmation",
        "requires_approval": False,
        "confirm_deadline": now,
        "approval_request_id": None,
        "provider_confirmed_at": None,
        "renter_confirmed_at": None,
        "effective_at": None,
        "created_at": now,
        "updated_at": now,
    }

    record = _to_agreement_record(raw_row)
    assert record.id == raw_row["id"]
    assert record.status == AgreementStatus.pending_confirmation
    assert isinstance(record.body_sha256, bytes)
    assert len(record.body_sha256) == 32
    assert record.body_sha256_hex == sha_bytes.hex()


def test_to_zone_policy_dto_mapping() -> None:
    raw_row = {
        "id": uuid4(),
        "zone_id": uuid4(),
        "version": 2,
        "agreement_template_md": "Template markdown",
        "approval_threshold_vnd": 1_000_000,
        "agreement_confirm_ttl_seconds": 1800,
    }

    dto = _to_zone_policy_dto(raw_row)
    assert dto.id == raw_row["id"]
    assert dto.version == 2
    assert dto.approval_threshold_vnd == 1_000_000
    assert dto.agreement_confirm_ttl_seconds == 1800


def test_to_booking_parties_dto_mapping() -> None:
    now = datetime.now(UTC)
    raw_row = {
        "booking_id": uuid4(),
        "zone_id": uuid4(),
        "slot_id": uuid4(),
        "slot_code": "B1-002",
        "provider_user_id": uuid4(),
        "provider_name": "Nguyễn Văn A",
        "renter_user_id": uuid4(),
        "renter_name": "Trần Thị B",
        "price_vnd": 60_000,
        "period_start": now,
        "period_end": now,
        "booking_status": "held",
    }

    dto = _to_booking_parties_dto(raw_row)
    assert dto.booking_id == raw_row["booking_id"]
    assert dto.slot_code == "B1-002"
    assert dto.provider_name == "Nguyễn Văn A"


@pytest.mark.asyncio
async def test_repository_get_by_id_calls_fetchrow() -> None:
    mock_conn = AsyncMock()
    now = datetime.now(UTC)
    ag_id = uuid4()
    mock_conn.fetchrow.return_value = {
        "id": ag_id,
        "zone_id": uuid4(),
        "booking_id": uuid4(),
        "zone_policy_id": uuid4(),
        "provider_user_id": uuid4(),
        "renter_user_id": uuid4(),
        "price_vnd": 40_000,
        "body_rendered": "Thỏa thuận",
        "body_sha256": b"a" * 32,
        "status": "pending_confirmation",
        "requires_approval": False,
        "confirm_deadline": now,
        "approval_request_id": None,
        "provider_confirmed_at": None,
        "renter_confirmed_at": None,
        "effective_at": None,
        "created_at": now,
        "updated_at": now,
    }

    repo = AgreementRepository()
    record = await repo.get_by_id(mock_conn, ag_id)

    assert record is not None
    assert record.id == ag_id
    mock_conn.fetchrow.assert_awaited_once()


@pytest.mark.asyncio
async def test_repository_update_booking_status() -> None:
    mock_conn = AsyncMock()
    booking_id = uuid4()

    repo = AgreementRepository()
    await repo.update_booking_status_pending_agreement(mock_conn, booking_id)

    mock_conn.execute.assert_awaited_once()
