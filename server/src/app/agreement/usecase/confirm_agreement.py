"""Use case: Xác nhận thỏa thuận chia sẻ bằng OTP (M6, SCRUM-100, FR-08, FR-09, AC-07, AC-15).

Quy trình nghiệp vụ:
1. Kiểm tra tồn tại và trạng thái thỏa thuận (phải là pending_confirmation).
2. Kiểm tra hạn chót confirm_deadline.
3. Xác định vai trò của caller (renter hoặc provider). Chặn người ngoài cuộc.
4. Kiểm tra xem bên này đã xác nhận từ trước chưa.
5. Xác thực mã OTP qua OtpServicePort (Redis/InMemory).
6. Ghi bằng chứng xác nhận vào app.consent_record (append-only, FR-09).
7. Cập nhật mốc thời gian renter_confirmed_at / provider_confirmed_at.
8. Đánh giá trạng thái cả 2 bên:
   - Nếu mới 1 bên: giữ nguyên pending_confirmation, trả next_action = WAIT_FOR_OTHER_PARTY.
   - Nếu đủ 2 bên và requires_approval = False: chuyển sang effective, booking = confirmed, trả next_action = BOOKING_ACTIVE.
   - Nếu đủ 2 bên và requires_approval = True: tạo approval_request cho BQL, chuyển thỏa thuận + booking sang pending_approval, trả next_action = PENDING_BQL_APPROVAL.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.agreement.domain.exceptions import (
    AgreementAccessDeniedError,
    AgreementExpiredError,
    AgreementNotFoundError,
    AgreementNotPendingError,
    PartyAlreadyConfirmedError,
)
from app.agreement.domain.models import (
    AgreementRecord,
    AgreementStatus,
    ConsentAction,
    ConsentDecision,
    ConsentRecord,
    NextAction,
)
from app.agreement.domain.ports import AgreementRepositoryPort, OtpServicePort

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ConfirmAgreementCommand:
    """Lệnh xác nhận thỏa thuận bằng OTP."""

    agreement_id: UUID
    user_id: UUID
    otp_code: str
    thread_id: str | None = None


@dataclass(frozen=True)
class ConfirmAgreementResult:
    """Kết quả xác nhận thỏa thuận (phục vụ FE và AI Agent)."""

    agreement: AgreementRecord
    consent_record: ConsentRecord
    confirmed_role: str  # 'renter' | 'provider'
    both_confirmed: bool
    next_action: NextAction
    approval_request_id: UUID | None = None
    agent_summary: str = ""


class ConfirmAgreementUseCase:
    """Điều phối xác thực OTP và ghi nhận bằng chứng thỏa thuận 2 bên."""

    def __init__(self, repo: AgreementRepositoryPort, otp_service: OtpServicePort) -> None:
        self.repo = repo
        self.otp_service = otp_service

    async def execute(self, conn: Any, cmd: ConfirmAgreementCommand) -> ConfirmAgreementResult:
        # 1. Truy vấn thỏa thuận
        agreement = await self.repo.get_by_id(conn, cmd.agreement_id)
        if agreement is None:
            raise AgreementNotFoundError(cmd.agreement_id)

        # 2. Kiểm tra trạng thái thỏa thuận
        if agreement.status != AgreementStatus.pending_confirmation:
            raise AgreementNotPendingError(agreement.id, agreement.status)

        # 3. Kiểm tra thời hạn hiệu lực (confirm_deadline)
        now = datetime.now(UTC)
        if agreement.confirm_deadline and now > agreement.confirm_deadline:
            logger.warning(
                "Agreement confirmation deadline expired for agreement_id=%s (deadline: %s)",
                agreement.id,
                agreement.confirm_deadline,
            )
            raise AgreementExpiredError(agreement.id)

        # 4. Xác định vai trò của caller và kiểm tra đã confirm chưa
        if cmd.user_id == agreement.renter_user_id:
            role = "renter"
            if agreement.renter_confirmed_at is not None:
                raise PartyAlreadyConfirmedError(agreement.id, "renter")
        elif cmd.user_id == agreement.provider_user_id:
            role = "provider"
            if agreement.provider_confirmed_at is not None:
                raise PartyAlreadyConfirmedError(agreement.id, "provider")
        else:
            logger.warning(
                "User %s is neither renter nor provider of agreement %s",
                cmd.user_id,
                cmd.agreement_id,
            )
            raise AgreementAccessDeniedError(agreement.id, cmd.user_id)

        # 5. Xác thực OTP qua OtpService
        await self.otp_service.verify_otp(cmd.agreement_id, cmd.user_id, cmd.otp_code)

        # 6. Ghi nhận bằng chứng pháp lý vào app.consent_record (append-only)
        consent = ConsentRecord(
            user_id=cmd.user_id,
            action=ConsentAction.agreement_confirm,
            subject_type="agreement",
            subject_id=agreement.id,
            terms_version=str(agreement.zone_policy_id),
            decision=ConsentDecision.accepted,
            evidence={
                "role": role,
                "body_sha256": agreement.body_sha256_hex,
                "channel": "otp",
            },
            zone_id=agreement.zone_id,
            created_at=now,
        )
        saved_consent = await self.repo.append_consent_record(conn, consent)

        # 7. Cập nhật mốc thời gian xác nhận của bên này
        agreement = await self.repo.update_party_confirmation(conn, agreement.id, role, now)

        # 8. Đánh giá trạng thái cả 2 bên
        both_confirmed = agreement.renter_confirmed_at is not None and agreement.provider_confirmed_at is not None

        approval_request_id: UUID | None = None
        if not both_confirmed:
            next_action = NextAction.WAIT_FOR_OTHER_PARTY
            other_role = "chủ chỗ" if role == "renter" else "người thuê"
            agent_summary = (
                f"Bên {role} ({cmd.user_id}) đã xác nhận OTP thành công. "
                f"Hệ thống đang chờ {other_role} hoàn tất xác nhận để kích hoạt thỏa thuận."
            )
        else:
            if agreement.requires_approval:
                # Vượt ngưỡng BQL (BR-12 / AC-15) -> tạo approval_request
                agreement, approval_request_id = await self.repo.mark_agreement_pending_approval(
                    conn,
                    agreement_id=agreement.id,
                    booking_id=agreement.booking_id,
                    zone_id=agreement.zone_id,
                    price_vnd=agreement.price_vnd,
                    thread_id=cmd.thread_id,
                )
                next_action = NextAction.PENDING_BQL_APPROVAL
                agent_summary = (
                    f"Cả hai bên đã hoàn tất xác nhận OTP. Do giá trị thỏa thuận ({agreement.price_vnd:,}đ) "
                    f"vượt ngưỡng quy định khu vực, hồ sơ đã được chuyển tới Ban Quản Lý (yêu cầu #{approval_request_id}) để phê duyệt."
                )
            else:
                # Kích hoạt thỏa thuận (effective) và booking confirmed (AC-07)
                agreement = await self.repo.activate_agreement(
                    conn,
                    agreement_id=agreement.id,
                    booking_id=agreement.booking_id,
                    effective_at=now,
                )
                next_action = NextAction.BOOKING_ACTIVE
                agent_summary = (
                    "Cả hai bên đã hoàn tất xác nhận OTP thành công. "
                    "Thỏa thuận chia sẻ chỗ đỗ chính thức có hiệu lực và lượt đặt chỗ đã được xác nhận!"
                )

        logger.info(
            "Confirmed agreement_id=%s by role=%s, both_confirmed=%s, next_action=%s",
            agreement.id,
            role,
            both_confirmed,
            next_action,
        )

        return ConfirmAgreementResult(
            agreement=agreement,
            consent_record=saved_consent,
            confirmed_role=role,
            both_confirmed=both_confirmed,
            next_action=next_action,
            approval_request_id=approval_request_id,
            agent_summary=agent_summary,
        )
