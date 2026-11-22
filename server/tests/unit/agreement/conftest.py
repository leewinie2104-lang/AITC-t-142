"""Shared fixtures and mocks for agreement unit tests."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.agreement.domain.models import (
    AgreementRecord,
    AgreementStatus,
    ConsentRecord,
)
from app.agreement.domain.ports import (
    AgreementRepositoryPort,
    BookingPartiesDTO,
    ZonePolicyDTO,
)
from app.agreement.infrastructure.otp_service import InMemoryOtpService


class MockAgreementRepository(AgreementRepositoryPort):
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
        self.consent_records: list[ConsentRecord] = []
        self.approval_requests: list[dict[str, Any]] = []

    async def get_by_id(self, conn: Any, agreement_id: UUID) -> AgreementRecord | None:
        if agreement_id in self.saved_agreements:
            return self.saved_agreements[agreement_id]
        if self.existing_agreement and self.existing_agreement.id == agreement_id:
            return self.existing_agreement
        return None

    async def get_by_booking_id(self, conn: Any, booking_id: UUID) -> AgreementRecord | None:
        for ag in self.saved_agreements.values():
            if ag.booking_id == booking_id:
                return ag
        if self.existing_agreement and self.existing_agreement.booking_id == booking_id:
            return self.existing_agreement
        return None

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

    async def append_consent_record(self, conn: Any, record: ConsentRecord) -> ConsentRecord:
        saved = replace(record, id=len(self.consent_records) + 1)
        self.consent_records.append(saved)
        return saved

    async def get_consent_records_by_agreement(self, conn: Any, agreement_id: UUID) -> list[ConsentRecord]:
        return [r for r in self.consent_records if r.subject_id == agreement_id]

    async def update_party_confirmation(
        self,
        conn: Any,
        agreement_id: UUID,
        role: str,
        confirmed_at: datetime,
    ) -> AgreementRecord:
        current = self.saved_agreements.get(agreement_id) or self.existing_agreement
        if current is None:
            raise RuntimeError("Agreement not found in mock.")
        if role == "renter":
            updated = replace(current, renter_confirmed_at=confirmed_at, updated_at=confirmed_at)
        else:
            updated = replace(current, provider_confirmed_at=confirmed_at, updated_at=confirmed_at)
        self.saved_agreements[agreement_id] = updated
        return updated

    async def activate_agreement(
        self,
        conn: Any,
        agreement_id: UUID,
        booking_id: UUID,
        effective_at: datetime,
    ) -> AgreementRecord:
        current = self.saved_agreements.get(agreement_id) or self.existing_agreement
        if current is None:
            raise RuntimeError("Agreement not found in mock.")
        updated = replace(current, status=AgreementStatus.effective, effective_at=effective_at, updated_at=effective_at)
        self.saved_agreements[agreement_id] = updated
        self.updated_bookings.append(booking_id)
        return updated

    async def mark_agreement_pending_approval(
        self,
        conn: Any,
        agreement_id: UUID,
        booking_id: UUID,
        zone_id: UUID,
        price_vnd: int,
        thread_id: str | None = None,
    ) -> tuple[AgreementRecord, UUID]:
        current = self.saved_agreements.get(agreement_id) or self.existing_agreement
        if current is None:
            raise RuntimeError("Agreement not found in mock.")
        approval_id = uuid4()
        self.approval_requests.append(
            {
                "id": approval_id,
                "agreement_id": agreement_id,
                "zone_id": zone_id,
                "thread_id": thread_id or f"thread:agreement:{agreement_id}",
                "price_vnd": price_vnd,
            }
        )
        updated = replace(
            current,
            status=AgreementStatus.pending_approval,
            approval_request_id=approval_id,
            updated_at=datetime.now(UTC),
        )
        self.saved_agreements[agreement_id] = updated
        self.updated_bookings.append(booking_id)
        return updated, approval_id


@pytest.fixture
def mock_repo_cls() -> type[MockAgreementRepository]:
    return MockAgreementRepository


@pytest.fixture
def in_memory_otp_service() -> InMemoryOtpService:
    return InMemoryOtpService()


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
        confirm_deadline=datetime.now(UTC) + timedelta(minutes=30),
    )
