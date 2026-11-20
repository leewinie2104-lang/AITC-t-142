"""FastAPI Router for Agreement module (M6, SCRUM-99).

Cung cấp các API:
- GET /api/v1/agreements/{id}: Xem chi tiết thỏa thuận và mã băm SHA-256.
- POST /api/v1/agreements/generate: Kích hoạt sinh thỏa thuận theo mẫu khu.
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
    AgreementNotFoundError,
    BookingNotFoundError,
    ZonePolicyNotFoundError,
)
from app.agreement.domain.models import AgreementRecord
from app.agreement.usecase.generate_agreement import (
    GenerateAgreementCommand,
    GenerateAgreementResult,
    GenerateAgreementUseCase,
)
from app.agreement.usecase.get_agreement import (
    GetAgreementQuery,
    GetAgreementUseCase,
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


@asynccontextmanager
async def _default_uow(user_id: UUID | None, zone_ids: list[UUID] | None) -> AsyncIterator[Any]:
    async with unit_of_work(user_id=user_id, zone_ids=zone_ids) as conn:
        yield conn


def create_agreement_router(
    get_use_case: GetAgreementUseCase,
    generate_use_case: GenerateAgreementUseCase | None = None,
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

    return router
