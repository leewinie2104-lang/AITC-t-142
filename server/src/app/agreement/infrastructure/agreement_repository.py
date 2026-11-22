"""Agreement Repository implementation (M6, SCRUM-99, SCRUM-100)."""

import json
import logging
from contextlib import nullcontext
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.agreement.domain.models import (
    AgreementRecord,
    AgreementStatus,
    ConsentAction,
    ConsentDecision,
    ConsentRecord,
)
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


def _to_consent_record(row: Any) -> ConsentRecord:
    data = dict(row)
    data["action"] = ConsentAction(data["action"])
    data["decision"] = ConsentDecision(data["decision"])
    evidence = data.get("evidence")
    if isinstance(evidence, str):
        data["evidence"] = json.loads(evidence)
    elif evidence is None:
        data["evidence"] = {}
    return ConsentRecord(**data)


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
        """Lấy thỏa thuận theo booking_id."""
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

    async def append_consent_record(self, conn: Any, record: ConsentRecord) -> ConsentRecord:
        """Ghi nhận bằng chứng vào app.consent_record (append-only, FR-09)."""
        insert_sql = """
            INSERT INTO app.consent_record (
                user_id, zone_id, action, subject_type, subject_id,
                terms_version, decision, evidence, created_at
            ) VALUES (
                $1, $2, $3, $4, $5,
                $6, $7, $8::jsonb, $9
            )
            ON CONFLICT (user_id, action, subject_id, terms_version, decision) DO NOTHING
            RETURNING id, user_id, zone_id, action, subject_type, subject_id,
                      terms_version, decision, evidence, created_at;
        """
        evidence_json = json.dumps(record.evidence)
        row = await conn.fetchrow(
            insert_sql,
            record.user_id,
            record.zone_id,
            record.action.value,
            record.subject_type,
            record.subject_id,
            record.terms_version,
            record.decision.value,
            evidence_json,
            record.created_at or datetime.now(UTC),
        )
        if row is None:
            # Idempotent replay: lấy lại bản ghi đã có
            select_sql = """
                SELECT id, user_id, zone_id, action, subject_type, subject_id,
                       terms_version, decision, evidence, created_at
                FROM app.consent_record
                WHERE user_id = $1 AND action = $2 AND subject_id = $3
                  AND terms_version = $4 AND decision = $5;
            """
            row = await conn.fetchrow(
                select_sql,
                record.user_id,
                record.action.value,
                record.subject_id,
                record.terms_version,
                record.decision.value,
            )
            if row is None:
                raise RuntimeError("Failed to insert or retrieve consent record.")
        return _to_consent_record(row)

    async def get_consent_records_by_agreement(self, conn: Any, agreement_id: UUID) -> list[ConsentRecord]:
        """Lấy tất cả bằng chứng xác nhận của một thỏa thuận."""
        sql = """
            SELECT id, user_id, zone_id, action, subject_type, subject_id,
                   terms_version, decision, evidence, created_at
            FROM app.consent_record
            WHERE subject_type = 'agreement' AND subject_id = $1
            ORDER BY created_at ASC;
        """
        rows = await conn.fetch(sql, agreement_id)
        return [_to_consent_record(r) for r in rows]

    async def update_party_confirmation(
        self,
        conn: Any,
        agreement_id: UUID,
        role: str,
        confirmed_at: datetime,
    ) -> AgreementRecord:
        """Cập nhật mốc thời gian xác nhận của một bên."""
        if role == "renter":
            sql = """
                UPDATE app.agreement
                SET renter_confirmed_at = $2, updated_at = now()
                WHERE id = $1
                RETURNING id, zone_id, booking_id, zone_policy_id, provider_user_id, renter_user_id,
                          price_vnd, body_rendered, body_sha256, status, requires_approval,
                          confirm_deadline, approval_request_id, provider_confirmed_at,
                          renter_confirmed_at, effective_at, created_at, updated_at;
            """
        else:
            sql = """
                UPDATE app.agreement
                SET provider_confirmed_at = $2, updated_at = now()
                WHERE id = $1
                RETURNING id, zone_id, booking_id, zone_policy_id, provider_user_id, renter_user_id,
                          price_vnd, body_rendered, body_sha256, status, requires_approval,
                          confirm_deadline, approval_request_id, provider_confirmed_at,
                          renter_confirmed_at, effective_at, created_at, updated_at;
            """
        row = await conn.fetchrow(sql, agreement_id, confirmed_at)
        if row is None:
            raise RuntimeError(f"Failed to update party confirmation for agreement {agreement_id}")
        return _to_agreement_record(row)

    async def activate_agreement(
        self,
        conn: Any,
        agreement_id: UUID,
        booking_id: UUID,
        effective_at: datetime,
    ) -> AgreementRecord:
        """Kích hoạt thỏa thuận (effective) và chuyển booking sang 'confirmed'."""
        if conn is not None and hasattr(conn, "acquire"):
            raise TypeError("Expected an asyncpg Connection, but received a ConnectionPool.")
        tx_cm = conn.transaction() if (conn is not None and hasattr(conn, "transaction")) else nullcontext()
        async with tx_cm:
            sql_agree = """
                UPDATE app.agreement
                SET status = 'effective', effective_at = $2, updated_at = now()
                WHERE id = $1
                RETURNING id, zone_id, booking_id, zone_policy_id, provider_user_id, renter_user_id,
                          price_vnd, body_rendered, body_sha256, status, requires_approval,
                          confirm_deadline, approval_request_id, provider_confirmed_at,
                          renter_confirmed_at, effective_at, created_at, updated_at;
            """
            row = await conn.fetchrow(sql_agree, agreement_id, effective_at)
            if row is None:
                raise RuntimeError(f"Failed to activate agreement {agreement_id}")

            sql_book = """
                UPDATE app.booking
                SET status = 'confirmed', updated_at = now()
                WHERE id = $1;
            """
            await conn.execute(sql_book, booking_id)
            return _to_agreement_record(row)

    async def mark_agreement_pending_approval(
        self,
        conn: Any,
        agreement_id: UUID,
        booking_id: UUID,
        zone_id: UUID,
        price_vnd: int,
        thread_id: str | None = None,
    ) -> tuple[AgreementRecord, UUID]:
        """Tạo approval_request cho BQL và chuyển thỏa thuận + booking sang 'pending_approval'."""
        if conn is not None and hasattr(conn, "acquire"):
            raise TypeError("Expected an asyncpg Connection, but received a ConnectionPool.")
        actual_thread_id = thread_id or f"thread:agreement:{agreement_id}"
        tx_cm = conn.transaction() if (conn is not None and hasattr(conn, "transaction")) else nullcontext()
        async with tx_cm:
            # 1. Đảm bảo agent_thread tồn tại để thỏa mãn FK của app.approval_request
            thread_sql = """
                INSERT INTO app.agent_thread (thread_id, user_id, zone_id, workflow, status, pending_card)
                SELECT $1, renter_user_id, zone_id, 'W2', 'awaiting_manager',
                       jsonb_build_object('card', 'agreement_over_threshold', 'agreement_id', $2::text, 'price_vnd', $3)
                FROM app.agreement
                WHERE id = $2
                ON CONFLICT (thread_id) DO UPDATE SET status = 'awaiting_manager', updated_at = now();
            """
            await conn.execute(thread_sql, actual_thread_id, agreement_id, price_vnd)

            # 2. Tạo approval_request
            approval_id = uuid4()
            approval_sql = """
                INSERT INTO app.approval_request (
                    id, zone_id, kind, subject_id, thread_id, status, summary, requested_at, due_at
                ) VALUES (
                    $1, $2, 'agreement_over_threshold', $3, $4, 'pending',
                    $5, now(), now() + interval '24 hours'
                )
                ON CONFLICT (kind, subject_id) WHERE status = 'pending'
                DO UPDATE SET updated_at = now()
                RETURNING id;
            """
            summary = f"Thỏa thuận chia sẻ vượt ngưỡng ({price_vnd:,}đ)"
            appr_row = await conn.fetchrow(approval_sql, approval_id, zone_id, agreement_id, actual_thread_id, summary)
            final_approval_id = appr_row["id"] if appr_row else approval_id

            # 3. Cập nhật agreement: requires_approval & approval_request_id
            agree_sql = """
                UPDATE app.agreement
                SET status = 'pending_approval', approval_request_id = $2, updated_at = now()
                WHERE id = $1
                RETURNING id, zone_id, booking_id, zone_policy_id, provider_user_id, renter_user_id,
                          price_vnd, body_rendered, body_sha256, status, requires_approval,
                          confirm_deadline, approval_request_id, provider_confirmed_at,
                          renter_confirmed_at, effective_at, created_at, updated_at;
            """
            row = await conn.fetchrow(agree_sql, agreement_id, final_approval_id)
            if row is None:
                raise RuntimeError(f"Failed to update agreement {agreement_id} to pending_approval")

            # 4. Cập nhật booking sang pending_approval
            book_sql = """
                UPDATE app.booking
                SET status = 'pending_approval', updated_at = now()
                WHERE id = $1;
            """
            await conn.execute(book_sql, booking_id)

            return _to_agreement_record(row), final_approval_id
