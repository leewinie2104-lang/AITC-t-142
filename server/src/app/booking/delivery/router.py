"""FastAPI Router for Booking and Parking Requests (M5, SCRUM-96)."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.booking.domain.models import RequestOutcome
from app.booking.usecase.request_parking import (
    RequestParkingCommand,
    RequestParkingResult,
    RequestParkingUseCase,
)
from app.platform.db.session import unit_of_work


class ParkingRequestIn(BaseModel):
    """Payload yêu cầu đỗ xe từ phía Client / Mini-App."""

    zone_id: UUID
    building_id: UUID
    requester_user_id: UUID
    vehicle_id: UUID
    vehicle_size: str = Field(description="S, M, L, XL")
    period_start: datetime
    period_end: datetime
    computed_level: str = Field(default="L1", description="L1, L2, L3, L4")
    channel: str = Field(default="app", description="app hoặc chat")
    idempotency_key: str = Field(description="Khóa chống trùng giao dịch, ví dụ user:timestamp:req")


class BookingHeldOut(BaseModel):
    """Thông tin giữ chỗ tạm thời nếu ghép thành công."""

    booking_id: UUID
    ref_no: int
    status: str
    hold_expires_at: datetime


class ParkingRequestOut(BaseModel):
    """Kết quả trả về cho yêu cầu đỗ xe."""

    request_id: UUID
    outcome: RequestOutcome
    booking: BookingHeldOut | None = None
    block_reason: str | None = None
    message: str


@asynccontextmanager
async def _default_uow(user_id: UUID | None, zone_ids: list[UUID] | None) -> AsyncIterator[Any]:
    async with unit_of_work(user_id=user_id, zone_ids=zone_ids) as conn:
        yield conn


def create_booking_router(
    use_case: RequestParkingUseCase,
    uow_factory: Callable[[UUID | None, list[UUID] | None], Any] | None = None,
) -> APIRouter:
    """Tạo APIRouter cho module booking được tiêm (injected) usecase và uow_factory."""
    router = APIRouter(prefix="/api/v1/bookings", tags=["bookings"])
    get_uow = uow_factory or _default_uow

    @router.post(
        "/request",
        response_model=ParkingRequestOut,
        status_code=status.HTTP_201_CREATED,
    )
    async def request_parking(payload: ParkingRequestIn) -> ParkingRequestOut:
        cmd = RequestParkingCommand(
            zone_id=payload.zone_id,
            building_id=payload.building_id,
            requester_user_id=payload.requester_user_id,
            vehicle_id=payload.vehicle_id,
            vehicle_size=payload.vehicle_size.upper(),
            period_start=payload.period_start,
            period_end=payload.period_end,
            computed_level=payload.computed_level.upper(),
            channel=payload.channel,
            idempotency_key=payload.idempotency_key,
        )

        try:
            async with get_uow(cmd.requester_user_id, [cmd.zone_id]) as conn:
                res: RequestParkingResult = await use_case.execute(conn, cmd)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(exc),
            ) from exc

        booking_dto = None
        if res.booking:
            booking_dto = BookingHeldOut(
                booking_id=res.booking.id,
                ref_no=res.booking.ref_no,
                status=res.booking.status,
                hold_expires_at=res.booking.hold_expires_at,
            )

        return ParkingRequestOut(
            request_id=res.request_id,
            outcome=res.outcome,
            booking=booking_dto,
            block_reason=res.block_reason,
            message=res.message,
        )

    return router
