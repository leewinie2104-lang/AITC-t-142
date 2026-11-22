"""Use case: Phát sinh và gửi mã OTP xác nhận thỏa thuận (M6, SCRUM-100)."""

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
from app.agreement.domain.models import AgreementStatus
from app.agreement.domain.ports import AgreementRepositoryPort, OtpServicePort

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SendAgreementOtpCommand:
    """Lệnh yêu cầu phát sinh mã OTP."""

    agreement_id: UUID
    user_id: UUID


@dataclass(frozen=True)
class SendAgreementOtpResult:
    """Kết quả phát sinh mã OTP."""

    agreement_id: UUID
    user_id: UUID
    role: str
    ttl_seconds: int
    dev_otp: str | None = None
    message: str = ""


class SendAgreementOtpUseCase:
    """Điều phối tạo mã OTP và lưu vào Redis/cache cho người dùng."""

    def __init__(self, repo: AgreementRepositoryPort, otp_service: OtpServicePort) -> None:
        self.repo = repo
        self.otp_service = otp_service

    async def execute(self, conn: Any, cmd: SendAgreementOtpCommand) -> SendAgreementOtpResult:
        # 1. Truy vấn thỏa thuận
        agreement = await self.repo.get_by_id(conn, cmd.agreement_id)
        if agreement is None:
            raise AgreementNotFoundError(cmd.agreement_id)

        # 2. Kiểm tra trạng thái thỏa thuận
        if agreement.status != AgreementStatus.pending_confirmation:
            raise AgreementNotPendingError(agreement.id, agreement.status)

        # 3. Kiểm tra hạn chót
        now = datetime.now(UTC)
        if agreement.confirm_deadline and now > agreement.confirm_deadline:
            raise AgreementExpiredError(agreement.id)

        # 4. Xác định vai trò của người yêu cầu
        if cmd.user_id == agreement.renter_user_id:
            role = "renter"
            if agreement.renter_confirmed_at is not None:
                raise PartyAlreadyConfirmedError(agreement.id, "renter")
        elif cmd.user_id == agreement.provider_user_id:
            role = "provider"
            if agreement.provider_confirmed_at is not None:
                raise PartyAlreadyConfirmedError(agreement.id, "provider")
        else:
            raise AgreementAccessDeniedError(agreement.id, cmd.user_id)

        # 5. Tính TTL còn lại theo confirm_deadline
        ttl_seconds = 1800
        if agreement.confirm_deadline:
            diff = int((agreement.confirm_deadline - now).total_seconds())
            ttl_seconds = max(60, min(diff, 1800))

        # 6. Phát sinh mã OTP qua OtpService
        code = await self.otp_service.issue_otp(agreement.id, cmd.user_id, ttl_seconds=ttl_seconds)

        logger.info(
            "Issued OTP for agreement_id=%s, user_id=%s, role=%s, ttl=%ss",
            agreement.id,
            cmd.user_id,
            role,
            ttl_seconds,
        )

        return SendAgreementOtpResult(
            agreement_id=agreement.id,
            user_id=cmd.user_id,
            role=role,
            ttl_seconds=ttl_seconds,
            dev_otp=code,  # Cung cấp cho dev/test/agent trong giai đoạn MVP
            message=f"OTP code has been generated for {role} and will expire in {ttl_seconds} seconds.",
        )
