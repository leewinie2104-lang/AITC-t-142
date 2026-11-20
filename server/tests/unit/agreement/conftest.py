"""Shared fixtures and mocks for agreement unit tests."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.agreement.domain.models import AgreementRecord, AgreementStatus
from app.agreement.domain.ports import BookingPartiesDTO, ZonePolicyDTO


class MockAgreementRepository:
    """Mock repository in-memory cho unit test."""

    def __init__(
        self,
        policy: ZonePolicyDTO | None = None,
        booking: BookingPartiesDTO | None = None,
        existing_agreement: AgreementRecord | None = None,
    ) -> None:
        self.policy = policy
        self.booking = booking
        self.existing_agreement = existing_agreement
        self.saved_agreements: dict[UUID, AgreementRecord] = {}
        self.updated_bookings: list[UUID] = []

    async def get_by_id(self, conn: Any, agreement_id: UUID) -> AgreementRecord | None:
        if self.existing_agreement and self.existing_agreement.id == agreement_id:
            return self.existing_agreement
        return self.saved_agreements.get(agreement_id)

    async def get_by_booking_id(self, conn: Any, booking_id: UUID) -> AgreementRecord | None:
        if self.existing_agreement and self.existing_agreement.booking_id == booking_id:
            return self.existing_agreement
        return next((ag for ag in self.saved_agreements.values() if ag.booking_id == booking_id), None)

    async def create_agreement(self, conn: Any, agreement: AgreementRecord) -> AgreementRecord:
        self.saved_agreements[agreement.id] = agreement
        return agreement

    async def get_active_zone_policy(self, conn: Any, zone_id: UUID) -> ZonePolicyDTO | None:
        if self.policy and self.policy.zone_id == zone_id:
            return self.policy
        return None

    async def get_booking_parties(self, conn: Any, booking_id: UUID) -> BookingPartiesDTO | None:
        if self.booking and self.booking.booking_id == booking_id:
            return self.booking
        return None

    async def update_booking_status_pending_agreement(self, conn: Any, booking_id: UUID) -> None:
        self.updated_bookings.append(booking_id)


@pytest.fixture
def mock_repo_cls() -> type[MockAgreementRepository]:
    return MockAgreementRepository


@pytest.fixture
def sample_ids() -> dict[str, UUID]:
    return {
        "zone_id": uuid4(),
        "booking_id": uuid4(),
        "policy_id": uuid4(),
        "provider_id": uuid4(),
        "renter_id": uuid4(),
        "slot_id": uuid4(),
    }


@pytest.fixture
def sample_policy(sample_ids: dict[str, UUID]) -> ZonePolicyDTO:
    return ZonePolicyDTO(
        id=sample_ids["policy_id"],
        zone_id=sample_ids["zone_id"],
        version=1,
        agreement_template_md=(
            "# Thỏa thuận chia sẻ\nChủ: {{provider}} - Thuê: {{renter}} - Chỗ: {{slot}} - Giá: {{price_vnd}} đ."
        ),
        approval_threshold_vnd=1_000_000,
        agreement_confirm_ttl_seconds=1800,
    )


@pytest.fixture
def sample_booking(sample_ids: dict[str, UUID]) -> BookingPartiesDTO:
    return BookingPartiesDTO(
        booking_id=sample_ids["booking_id"],
        zone_id=sample_ids["zone_id"],
        slot_id=sample_ids["slot_id"],
        slot_code="B2-045",
        provider_user_id=sample_ids["provider_id"],
        provider_name="Nguyễn Thị Lan",
        renter_user_id=sample_ids["renter_id"],
        renter_name="Trần Văn Bình",
        price_vnd=40_000,
        period_start=datetime(2026, 11, 20, 8, 0, tzinfo=UTC),
        period_end=datetime(2026, 11, 20, 12, 0, tzinfo=UTC),
        booking_status="held",
    )


@pytest.fixture
def sample_agreement(sample_ids: dict[str, UUID]) -> AgreementRecord:
    return AgreementRecord(
        id=uuid4(),
        zone_id=sample_ids["zone_id"],
        booking_id=sample_ids["booking_id"],
        zone_policy_id=sample_ids["policy_id"],
        provider_user_id=sample_ids["provider_id"],
        renter_user_id=sample_ids["renter_id"],
        price_vnd=40_000,
        body_rendered="Thỏa thuận chia sẻ...",
        body_sha256=b"x" * 32,
        status=AgreementStatus.pending_confirmation,
        requires_approval=False,
        confirm_deadline=datetime.now(UTC),
    )
