"""Agreement Repository implementation (M6, SCRUM-99)."""

import logging
from typing import Any
from uuid import UUID

from app.agreement.domain.models import AgreementRecord, AgreementStatus
from app.agreement.domain.ports import (
    AgreementRepositoryPort,
    BookingPartiesDTO,
    ZonePolicyDTO,
)

logger = logging.getLogger(__name__)


def _to_agreement_record(row: Any) -> AgreementRecord:
    data = dict(row)
    data["status"] = AgreementStatus(data["status"])
    if isinstance(data.get("body_sha256"), memoryview):
        data["body_sha256"] = bytes(data["body_sha256"])
    return AgreementRecord(**data)


def _to_zone_policy_dto(row: Any) -> ZonePolicyDTO:
    data = dict(row)
    return ZonePolicyDTO(
        id=data["id"],
        zone_id=data["zone_id"],
        version=data["version"],
        agreement_template_md=data["agreement_template_md"],
        approval_threshold_vnd=data["approval_threshold_vnd"],
        agreement_confirm_ttl_seconds=int(data["agreement_confirm_ttl_seconds"]),
    )


def _to_booking_parties_dto(row: Any) -> BookingPartiesDTO:
    data = dict(row)
    return BookingPartiesDTO(
        booking_id=data["booking_id"],
        zone_id=data["zone_id"],
        slot_id=data["slot_id"],
        slot_code=data["slot_code"],
        provider_user_id=data["provider_user_id"],
        provider_name=data["provider_name"],
        renter_user_id=data["renter_user_id"],
        renter_name=data["renter_name"],
        price_vnd=data["price_vnd"],
        period_start=data["period_start"],
        period_end=data["period_end"],
        booking_status=data["booking_status"],
    )


class AgreementRepository(AgreementRepositoryPort):
    async def get_by_id(self, conn: Any, agreement_id: UUID) -> AgreementRecord | None:
        """Lấy thỏa thuận theo ID."""
        sql = """
            SELECT id, zone_id, booking_id, zone_policy_id, provider_user_id, renter_user_id,
                   price_vnd, body_rendered, body_sha256, status, requires_approval,
                   confirm_deadline, approval_request_id, provider_confirmed_at,
                   renter_confirmed_at, effective_at, created_at, updated_at
            FROM app.agreement
            WHERE id = $1;
        """
        row = await conn.fetchrow(sql, agreement_id)
        return _to_agreement_record(row) if row else None

    async def get_by_booking_id(self, conn: Any, booking_id: UUID) -> AgreementRecord | None:
        """Lấy thỏa thuận theo booking_id"""
        sql = """
            SELECT id, zone_id, booking_id, zone_policy_id, provider_user_id, renter_user_id,
                   price_vnd, body_rendered, body_sha256, status, requires_approval,
                   confirm_deadline, approval_request_id, provider_confirmed_at,
                   renter_confirmed_at, effective_at, created_at, updated_at
            FROM app.agreement
            WHERE booking_id = $1;
        """
        row = await conn.fetchrow(sql, booking_id)
        return _to_agreement_record(row) if row else None

    async def create_agreement(self, conn: Any, agreement: AgreementRecord) -> AgreementRecord:
        """Lưu bản ghi thỏa thuận mới vào app.agreement."""
        insert_sql = """
            INSERT INTO app.agreement (
                id, zone_id, booking_id, zone_policy_id, provider_user_id, renter_user_id,
                price_vnd, body_rendered, body_sha256, status, requires_approval,
                confirm_deadline, created_at, updated_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6,
                $7, $8, $9, $10, $11,
                $12, $13, $14
            )
            ON CONFLICT (booking_id) DO NOTHING
            RETURNING id, zone_id, booking_id, zone_policy_id, provider_user_id, renter_user_id,
                      price_vnd, body_rendered, body_sha256, status, requires_approval,
                      confirm_deadline, approval_request_id, provider_confirmed_at,
                      renter_confirmed_at, effective_at, created_at, updated_at;
        """
        row = await conn.fetchrow(
            insert_sql,
            agreement.id,
            agreement.zone_id,
            agreement.booking_id,
            agreement.zone_policy_id,
            agreement.provider_user_id,
            agreement.renter_user_id,
            agreement.price_vnd,
            agreement.body_rendered,
            agreement.body_sha256,
            agreement.status.value,
            agreement.requires_approval,
            agreement.confirm_deadline,
            agreement.created_at,
            agreement.updated_at,
        )
        if row is None:
            existing = await self.get_by_booking_id(conn, agreement.booking_id)
            if existing is not None:
                return existing
            raise RuntimeError(f"Failed to create or retrieve agreement for booking {agreement.booking_id}")
        return _to_agreement_record(row)

    async def get_active_zone_policy(self, conn: Any, zone_id: UUID) -> ZonePolicyDTO | None:
        """Lấy chính sách hiệu lực gần nhất của khu vực (app.current_zone_policy)."""
        sql = """
            SELECT id, zone_id, version, agreement_template_md, approval_threshold_vnd,
                   COALESCE(EXTRACT(EPOCH FROM agreement_confirm_ttl)::int, 1800) AS agreement_confirm_ttl_seconds
            FROM app.zone_policy
            WHERE zone_id = $1 AND effective_from <= now()
            ORDER BY effective_from DESC, version DESC
            LIMIT 1;
        """
        row = await conn.fetchrow(sql, zone_id)
        return _to_zone_policy_dto(row) if row else None

    async def get_booking_parties(self, conn: Any, booking_id: UUID) -> BookingPartiesDTO | None:
        """Lấy thông tin các bên và chi tiết ô đỗ từ app.booking và bảng liên quan."""
        sql = """
            SELECT b.id AS booking_id, b.zone_id, b.slot_id, s.code AS slot_code,
                   b.provider_user_id, COALESCE(pu.full_name, 'Ban Quản Lý') AS provider_name,
                   b.renter_user_id, ru.full_name AS renter_name,
                   b.price_vnd, lower(b.period) AS period_start, upper(b.period) AS period_end,
                   b.status::text AS booking_status
            FROM app.booking b
            JOIN app.slot s ON b.slot_id = s.id
            JOIN app.app_user ru ON b.renter_user_id = ru.id
            LEFT JOIN app.app_user pu ON b.provider_user_id = pu.id
            WHERE b.id = $1;
        """
        row = await conn.fetchrow(sql, booking_id)
        return _to_booking_parties_dto(row) if row else None

    async def update_booking_status_pending_agreement(self, conn: Any, booking_id: UUID) -> None:
        """Cập nhật trạng thái booking sang 'pending_agreement'."""
        sql = """
            UPDATE app.booking
            SET status = 'pending_agreement', updated_at = now()
            WHERE id = $1;
        """
        await conn.execute(sql, booking_id)
