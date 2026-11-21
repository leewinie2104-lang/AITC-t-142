"""FastAPI Router for Agreement module (M6, SCRUM-99, SCRUM-100).

Cung cấp các API:
- GET /api/v1/agreements/{id}: Xem chi tiết thỏa thuận và mã băm SHA-256.
- POST /api/v1/agreements/generate: Kích hoạt sinh thỏa thuận theo mẫu khu.
- POST /api/v1/agreements/{id}/otp/send: Phát sinh / gửi lại mã OTP cho một bên.
- POST /api/v1/agreements/{id}/confirm: Xác nhận thỏa thuận bằng OTP (ghi consent_record).
- GET /api/v1/agreements/{id}/consent-records: Xem bằng chứng xác nhận đã lưu.
"""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.agreement.domain.exceptions import (
    AgreementAccessDeniedError,
    AgreementExpiredError,
    AgreementNotFoundError,
    AgreementNotPendingError,
    BookingNotFoundError,
    InvalidOtpError,
    OtpExpiredError,
    OtpMaxAttemptsExceededError,
    PartyAlreadyConfirmedError,
    ZonePolicyNotFoundError,
)
from app.agreement.domain.models import AgreementRecord, ConsentRecord
from app.agreement.domain.ports import AgreementRepositoryPort
from app.agreement.usecase.confirm_agreement import (
    ConfirmAgreementCommand,
    ConfirmAgreementResult,
    ConfirmAgreementUseCase,
)
from app.agreement.usecase.generate_agreement import (
    GenerateAgreementCommand,
    GenerateAgreementResult,
    GenerateAgreementUseCase,
)
from app.agreement.usecase.get_agreement import (
    GetAgreementQuery,
    GetAgreementUseCase,
)
from app.agreement.usecase.send_agreement_otp import (
    SendAgreementOtpCommand,
    SendAgreementOtpResult,
    SendAgreementOtpUseCase,
)
from app.platform.db.session import unit_of_work


class AgreementOut(BaseModel):
    """Thông tin chi tiết thỏa thuận gửi tới client."""

    id: UUID
    zone_id: UUID
    booking_id: UUID
    zone_policy_id: UUID
    provider_user_id: UUID
    renter_user_id: UUID
    price_vnd: int
    body_rendered: str
    body_sha256: str = Field(description="Hex-encoded 32-byte SHA-256 hash")
    status: str
    requires_approval: bool
    confirm_deadline: datetime
    approval_request_id: UUID | None = None
    provider_confirmed_at: datetime | None = None
    renter_confirmed_at: datetime | None = None
    effective_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def from_record(cls, record: AgreementRecord) -> "AgreementOut":
        data = asdict(record)
        data["body_sha256"] = record.body_sha256_hex
        return cls(**data)


class GenerateAgreementIn(BaseModel):
    """Payload yêu cầu sinh thỏa thuận."""

    booking_id: UUID
    custom_placeholders: dict[str, str] | None = None


class GenerateAgreementOut(BaseModel):
    """Kết quả sinh thỏa thuận."""

    agreement: AgreementOut
    is_replay: bool
    message: str


class SendOtpOut(BaseModel):
    """Kết quả phát sinh/gửi mã OTP."""

    agreement_id: UUID
    user_id: UUID
    role: str
    ttl_seconds: int
    dev_otp: str | None = None
    message: str


class ConfirmAgreementIn(BaseModel):
    """Payload xác nhận thỏa thuận bằng OTP."""

    otp_code: str = Field(min_length=4, max_length=10, description="Mã OTP 6 số")
    thread_id: str | None = Field(default=None, description="LangGraph thread_id nếu có")


class ConsentRecordOut(BaseModel):
    """Bằng chứng xác nhận đồng ý (app.consent_record)."""

    id: int | None = None
    user_id: UUID
    action: str
    subject_type: str
    subject_id: UUID
    terms_version: str
    decision: str
    evidence: dict[str, Any]
    zone_id: UUID | None = None
    created_at: datetime | None = None

    @classmethod
    def from_record(cls, record: ConsentRecord) -> "ConsentRecordOut":
        return cls(
            id=record.id,
            user_id=record.user_id,
            action=record.action.value,
            subject_type=record.subject_type,
            subject_id=record.subject_id,
            terms_version=record.terms_version,
            decision=record.decision.value,
            evidence=record.evidence,
            zone_id=record.zone_id,
            created_at=record.created_at,
        )


class ConfirmAgreementOut(BaseModel):
    """Kết quả xác nhận thỏa thuận bằng OTP."""

    agreement: AgreementOut
    consent_record: ConsentRecordOut
    confirmed_role: str
    both_confirmed: bool
    next_action: str
    approval_request_id: UUID | None = None
    agent_summary: str


@asynccontextmanager
async def _default_uow(user_id: UUID | None, zone_ids: list[UUID] | None) -> AsyncIterator[Any]:
    async with unit_of_work(user_id=user_id, zone_ids=zone_ids) as conn:
        yield conn


def create_agreement_router(
    get_use_case: GetAgreementUseCase,
    generate_use_case: GenerateAgreementUseCase | None = None,
    confirm_use_case: ConfirmAgreementUseCase | None = None,
    send_otp_use_case: SendAgreementOtpUseCase | None = None,
    repo: AgreementRepositoryPort | None = None,
    uow_factory: Callable[[UUID | None, list[UUID] | None], Any] | None = None,
) -> APIRouter:
    """Tạo APIRouter cho module Agreement được tiêm usecases và uow_factory."""
    router = APIRouter(prefix="/api/v1/agreements", tags=["agreements"])
    get_uow = uow_factory or _default_uow

    @router.get(
        "/{id}",
        response_model=AgreementOut,
        status_code=status.HTTP_200_OK,
        summary="Xem chi tiết thỏa thuận",
    )
    async def get_agreement(
        id: UUID,
        x_user_id: UUID | None = Header(default=None, description="Current authenticated user id"),
        x_role: str = Header(default="renter", description="Current user role"),
        x_zone_id: UUID | None = Header(default=None, description="Current user staff zone id"),
    ) -> AgreementOut:
        if not x_user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authentication user identifier.",
            )
        caller_zone_ids = [x_zone_id] if x_zone_id else []

        query = GetAgreementQuery(
            agreement_id=id,
            requester_user_id=x_user_id,
            requester_role=x_role,
            requester_zone_ids=caller_zone_ids,
        )

        try:
            async with get_uow(x_user_id, caller_zone_ids) as conn:
                record = await get_use_case.execute(conn, query)
                return AgreementOut.from_record(record)
        except AgreementNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc
        except AgreementAccessDeniedError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(exc),
            ) from exc

    @router.post(
        "/generate",
        response_model=GenerateAgreementOut,
        status_code=status.HTTP_201_CREATED,
        summary="Sinh thỏa thuận theo mẫu khu",
    )
    async def generate_agreement(
        payload: GenerateAgreementIn,
        x_user_id: UUID | None = Header(default=None),
        x_zone_id: UUID | None = Header(default=None),
    ) -> GenerateAgreementOut:
        if generate_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Generate agreement usecase is not wired in this deployment.",
            )

        cmd = GenerateAgreementCommand(
            booking_id=payload.booking_id,
            custom_placeholders=payload.custom_placeholders,
        )

        zone_ids = [x_zone_id] if x_zone_id else []
        try:
            async with get_uow(x_user_id, zone_ids) as conn:
                result: GenerateAgreementResult = await generate_use_case.execute(conn, cmd)
                return GenerateAgreementOut(
                    agreement=AgreementOut.from_record(result.agreement),
                    is_replay=result.is_replay,
                    message=result.message,
                )
        except BookingNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            ) from exc
        except ZonePolicyNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(exc),
            ) from exc

    @router.post(
        "/{id}/otp/send",
        response_model=SendOtpOut,
        status_code=status.HTTP_200_OK,
        summary="Phát sinh và gửi mã OTP xác nhận thỏa thuận",
    )
    async def send_agreement_otp(
        id: UUID,
        x_user_id: UUID | None = Header(default=None),
        x_zone_id: UUID | None = Header(default=None),
    ) -> SendOtpOut:
        if send_otp_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Send OTP usecase is not wired in this deployment.",
            )
        if not x_user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authentication user identifier.",
            )

        cmd = SendAgreementOtpCommand(agreement_id=id, user_id=x_user_id)
        zone_ids = [x_zone_id] if x_zone_id else []
        try:
            async with get_uow(x_user_id, zone_ids) as conn:
                result: SendAgreementOtpResult = await send_otp_use_case.execute(conn, cmd)
                return SendOtpOut(
                    agreement_id=result.agreement_id,
                    user_id=result.user_id,
                    role=result.role,
                    ttl_seconds=result.ttl_seconds,
                    dev_otp=result.dev_otp,
                    message=result.message,
                )
        except AgreementNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except AgreementAccessDeniedError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
        except PartyAlreadyConfirmedError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        except AgreementExpiredError as exc:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(exc)) from exc
        except AgreementNotPendingError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    @router.post(
        "/{id}/confirm",
        response_model=ConfirmAgreementOut,
        status_code=status.HTTP_200_OK,
        summary="Xác nhận thỏa thuận bằng OTP (ghi consent_record)",
    )
    async def confirm_agreement(
        id: UUID,
        payload: ConfirmAgreementIn,
        x_user_id: UUID | None = Header(default=None),
        x_zone_id: UUID | None = Header(default=None),
    ) -> ConfirmAgreementOut:
        if confirm_use_case is None:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Confirm agreement usecase is not wired in this deployment.",
            )
        if not x_user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authentication user identifier.",
            )

        cmd = ConfirmAgreementCommand(
            agreement_id=id,
            user_id=x_user_id,
            otp_code=payload.otp_code,
            thread_id=payload.thread_id,
        )
        zone_ids = [x_zone_id] if x_zone_id else []
        try:
            async with get_uow(x_user_id, zone_ids) as conn:
                result: ConfirmAgreementResult = await confirm_use_case.execute(conn, cmd)
                return ConfirmAgreementOut(
                    agreement=AgreementOut.from_record(result.agreement),
                    consent_record=ConsentRecordOut.from_record(result.consent_record),
                    confirmed_role=result.confirmed_role,
                    both_confirmed=result.both_confirmed,
                    next_action=result.next_action.value,
                    approval_request_id=result.approval_request_id,
                    agent_summary=result.agent_summary,
                )
        except AgreementNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except AgreementAccessDeniedError as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
        except PartyAlreadyConfirmedError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
        except AgreementExpiredError as exc:
            raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(exc)) from exc
        except (InvalidOtpError, OtpExpiredError, OtpMaxAttemptsExceededError) as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
        except AgreementNotPendingError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    @router.get(
        "/{id}/consent-records",
        response_model=list[ConsentRecordOut],
        status_code=status.HTTP_200_OK,
        summary="Xem danh sách bằng chứng xác nhận của thỏa thuận",
    )
    async def get_consent_records(
        id: UUID,
        x_user_id: UUID | None = Header(default=None),
        x_role: str = Header(default="renter"),
        x_zone_id: UUID | None = Header(default=None),
    ) -> list[ConsentRecordOut]:
        if repo is None:
            raise HTTPException(
                status_code=status.HTTP_501_NOT_IMPLEMENTED,
                detail="Agreement repository is not wired for direct queries.",
            )
        if not x_user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authentication user identifier.",
            )

        zone_ids = [x_zone_id] if x_zone_id else []
        async with get_uow(x_user_id, zone_ids) as conn:
            agreement = await repo.get_by_id(conn, id)
            if agreement is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agreement not found.")

            # Auth check: phải là renter, provider, hoặc staff của khu đó
            is_party = x_user_id in (agreement.renter_user_id, agreement.provider_user_id)
            is_staff = x_role in ("zone_staff", "zone_manager", "admin") and (
                not x_zone_id or x_zone_id == agreement.zone_id
            )
            if not (is_party or is_staff):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Permission denied to view consent records for this agreement.",
                )

            records = await repo.get_consent_records_by_agreement(conn, id)
            return [ConsentRecordOut.from_record(r) for r in records]

    return router
