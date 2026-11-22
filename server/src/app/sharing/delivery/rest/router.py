"""Router quản lý Lịch chia sẻ ô đỗ và Cơ chế Về sớm W3 (ADR-0010)."""

from uuid import UUID
from fastapi import APIRouter
from pydantic import BaseModel, Field

from demo_seed.ids import demo_id


class OwnerScheduleOut(BaseModel):
    slot_id: UUID
    slot_code: str
    owner_apartment: str
    active_days: list[str]
    start_time: str
    end_time: str
    auto_share_lpr: bool
    price_per_hour: int
    resident_share_percent: int
    daily_estimated_earnings: int
    monthly_estimated_earnings: int
    status: str
    current_booking_agreement: str | None = None
    renter_plate_masked: str | None = None


class UpdateScheduleIn(BaseModel):
    active_days: list[str]
    start_time: str
    end_time: str
    auto_share_lpr: bool


class EarlyReturnIn(BaseModel):
    slot_id: UUID
    reason: str = Field(default="Chủ chỗ có việc quay về sớm đột xuất")


class EarlyReturnOut(BaseModel):
    success: bool
    slot_code: str
    reallocated_slot_code: str
    message: str
    reallocated_slot_id: UUID
    renter_refund_vnd: int


# Trạng thái lịch chia sẻ ô đỗ cố định
_CURRENT_SCHEDULE = {
    "slot_id": demo_id("slot", "A", "B2-045"),
    "slot_code": "B2-045",
    "owner_apartment": "S2.01-1408",
    "active_days": ["T2", "T3", "T4", "T5", "T6"],
    "start_time": "08:00",
    "end_time": "17:30",
    "auto_share_lpr": True,
    "price_per_hour": 15000,
    "resident_share_percent": 70,
    "status": "sharing",
    "current_booking_agreement": "AGR-202611-0045",
    "renter_plate_masked": "30A-88*.*8",
}


def _calc_schedule_dto() -> OwnerScheduleOut:
    hours = 9.5
    daily = int(_CURRENT_SCHEDULE["price_per_hour"] * hours * (_CURRENT_SCHEDULE["resident_share_percent"] / 100))
    monthly = daily * len(_CURRENT_SCHEDULE["active_days"]) * 4

    return OwnerScheduleOut(
        **_CURRENT_SCHEDULE,
        daily_estimated_earnings=daily,
        monthly_estimated_earnings=monthly,
    )


router = APIRouter(prefix="/api/v1/sharing", tags=["sharing"])


@router.get("/my-schedule", response_model=OwnerScheduleOut)
async def get_my_schedule() -> OwnerScheduleOut:
    """Lấy cấu hình lịch chia sẻ và doanh thu tích lũy của chủ căn hộ."""
    return _calc_schedule_dto()


@router.post("/schedule", response_model=OwnerScheduleOut)
async def update_schedule(payload: UpdateScheduleIn) -> OwnerScheduleOut:
    """Cập nhật ngày và khung giờ mở chia sẻ định kỳ."""
    _CURRENT_SCHEDULE["active_days"] = payload.active_days
    _CURRENT_SCHEDULE["start_time"] = payload.start_time
    _CURRENT_SCHEDULE["end_time"] = payload.end_time
    _CURRENT_SCHEDULE["auto_share_lpr"] = payload.auto_share_lpr
    return _calc_schedule_dto()


@router.post("/early-return", response_model=EarlyReturnOut)
async def trigger_early_return(payload: EarlyReturnIn) -> EarlyReturnOut:
    """Kích hoạt cơ chế W3 khi chủ chỗ về sớm: Tự động điều phối xe khách sang ô TH3 dự phòng."""
    _CURRENT_SCHEDULE["status"] = "early_return_swapped"
    reallocated_id = demo_id("slot", "A", "TH3-01")

    return EarlyReturnOut(
        success=True,
        slot_code="B2-045",
        reallocated_slot_code="TH3-01",
        reallocated_slot_id=reallocated_id,
        renter_refund_vnd=35000,
        message="Kích hoạt thành công quy trình W3: Xe khách đã được chuyển sang ô TH3-01 dự phòng. Ô B2-045 của bạn đã sẵn sàng trống khi xe về cổng.",
    )
