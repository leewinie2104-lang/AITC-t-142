"""Use case: Sinh thỏa thuận theo mẫu khu (M6, SCRUM-99, FR-08, BR-12).

Quy trình thực hiện:
1. Kiểm tra thỏa thuận hiện có (Idempotent Replay chống tạo trùng).
2. Truy vấn thông tin các bên và lượt đỗ từ app.booking.
3. Truy vấn chính sách khu đang hiệu lực (app.zone_policy).
4. Render mẫu markdown với dữ liệu thực tế (pure domain function).
5. Băm SHA-256 (32 bytes) làm bằng chứng không thể chối bỏ.
6. Đánh giá cờ requires_approval theo ngưỡng (BR-12).
7. Tính hạn chót confirm_deadline = now() + TTL.
8. Lưu bản ghi vào app.agreement và chuyển booking sang 'pending_agreement'.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from app.agreement.domain.exceptions import (
    BookingNotFoundError,
    ZonePolicyNotFoundError,
)
from app.agreement.domain.models import AgreementRecord, AgreementStatus
from app.agreement.domain.ports import AgreementRepositoryPort
from app.agreement.domain.rendering import (
    check_requires_approval,
    compute_body_hash,
    render_agreement_template,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GenerateAgreementCommand:
    """Lệnh yêu cầu sinh thỏa thuận."""

    booking_id: UUID
    custom_placeholders: dict[str, str] | None = None


@dataclass(frozen=True)
class GenerateAgreementResult:
    """Kết quả sinh thỏa thuận."""

    agreement: AgreementRecord
    is_replay: bool = False
    message: str = ""


class GenerateAgreementUseCase:
    """Điều phối sinh thỏa thuận pháp lý theo chính sách khu."""

    def __init__(self, repo: AgreementRepositoryPort) -> None:
        self.repo = repo

    async def execute(self, conn: Any, cmd: GenerateAgreementCommand) -> GenerateAgreementResult:
        # 1. Idempotency Check: nếu booking này đã có thỏa thuận, trả về ngay kết quả đã tạo
        existing = await self.repo.get_by_booking_id(conn, cmd.booking_id)
        if existing is not None:
            logger.info(
                "Agreement already exists for booking_id=%s, returning replay agreement_id=%s",
                cmd.booking_id,
                existing.id,
            )
            return GenerateAgreementResult(
                agreement=existing,
                is_replay=True,
                message="Agreement already exists for this booking.",
            )

        # 2. Lấy thông tin các bên và ô đỗ
        booking = await self.repo.get_booking_parties(conn, cmd.booking_id)
        if booking is None:
            raise BookingNotFoundError(cmd.booking_id)

        # 3. Lấy chính sách khu vực hiệu lực
        policy = await self.repo.get_active_zone_policy(conn, booking.zone_id)
        if policy is None:
            raise ZonePolicyNotFoundError(booking.zone_id)

        # 4. Chuẩn bị context và render văn bản Markdown
        period_str = (
            f"{booking.period_start.strftime('%H:%M %d/%m/%Y')} - {booking.period_end.strftime('%H:%M %d/%m/%Y')}"
        )
        context: dict[str, Any] = {
            "provider": booking.provider_name,
            "renter": booking.renter_name,
            "slot": booking.slot_code,
            "period": period_str,
            "price_vnd": f"{booking.price_vnd:,}".replace(",", "."),
        }
        if cmd.custom_placeholders:
            context.update(cmd.custom_placeholders)

        body_rendered = render_agreement_template(policy.agreement_template_md, context)

        # 5. Băm SHA-256 (32 bytes raw binary)
        body_sha256 = compute_body_hash(body_rendered)

        # 6. Kiểm tra quy tắc vượt ngưỡng
        requires_approval = check_requires_approval(booking.price_vnd, policy.approval_threshold_vnd)

        # 7. Tính confirm_deadline (mặc định 30 phút)
        now = datetime.now(UTC)
        ttl_seconds = policy.agreement_confirm_ttl_seconds or 1800
        confirm_deadline = now + timedelta(seconds=ttl_seconds)

        # 8. Khởi tạo bản ghi Agreement
        agreement = AgreementRecord(
            id=uuid4(),
            zone_id=booking.zone_id,
            booking_id=booking.booking_id,
            zone_policy_id=policy.id,
            provider_user_id=booking.provider_user_id,
            renter_user_id=booking.renter_user_id,
            price_vnd=booking.price_vnd,
            body_rendered=body_rendered,
            body_sha256=body_sha256,
            status=AgreementStatus.pending_confirmation,
            requires_approval=requires_approval,
            confirm_deadline=confirm_deadline,
            created_at=now,
            updated_at=now,
        )

        # 9. Lưu vào DB & cập nhật booking
        created_agreement = await self.repo.create_agreement(conn, agreement)
        await self.repo.update_booking_status_pending_agreement(conn, booking.booking_id)

        logger.info(
            "Generated agreement_id=%s for booking_id=%s, requires_approval=%s",
            created_agreement.id,
            booking.booking_id,
            requires_approval,
        )

        return GenerateAgreementResult(
            agreement=created_agreement,
            is_replay=False,
            message="Agreement generated successfully.",
        )
