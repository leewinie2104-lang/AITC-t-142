"""Router quản lý Lịch chia sẻ ô đỗ và Cơ chế Về sớm W3 (ADR-0010)."""

from uuid import UUID

from fastapi import APIRouter, Header
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


# Cấu hình mẫu mặc định cho lịch chia sẻ ô đỗ
_DEFAULT_SCHEDULE_TEMPLATE = {
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

# Cô lập trạng thái lịch chia sẻ theo từng người dùng (X-User-Id) tránh data leakage giữa các phiên
_SCHEDULES_BY_USER: dict[UUID, dict] = {}


def _get_user_schedule(user_id: UUID | None) -> dict:
    resolved_id = user_id or demo_id("user", "A", "owner")
    if resolved_id not in _SCHEDULES_BY_USER:
        _SCHEDULES_BY_USER[resolved_id] = dict(_DEFAULT_SCHEDULE_TEMPLATE)
    return _SCHEDULES_BY_USER[resolved_id]


def _calc_schedule_dto(schedule: dict) -> OwnerScheduleOut:
    hours = 9.5
    daily = int(schedule["price_per_hour"] * hours * (schedule["resident_share_percent"] / 100))
    monthly = daily * len(schedule["active_days"]) * 4

    return OwnerScheduleOut(
        **schedule,
        daily_estimated_earnings=daily,
        monthly_estimated_earnings=monthly,
    )


router = APIRouter(prefix="/api/v1/sharing", tags=["sharing"])


@router.get("/my-schedule", response_model=OwnerScheduleOut)
async def get_my_schedule(x_user_id: UUID | None = Header(default=None)) -> OwnerScheduleOut:
    """Lấy cấu hình lịch chia sẻ và doanh thu tích lũy của chủ căn hộ (cô lập theo X-User-Id)."""
    schedule = _get_user_schedule(x_user_id)
    return _calc_schedule_dto(schedule)


@router.post("/schedule", response_model=OwnerScheduleOut)
async def update_schedule(
    payload: UpdateScheduleIn,
    x_user_id: UUID | None = Header(default=None),
) -> OwnerScheduleOut:
    """Cập nhật ngày và khung giờ mở chia sẻ định kỳ cho chủ căn hộ hiện tại."""
    schedule = _get_user_schedule(x_user_id)
    schedule["active_days"] = payload.active_days
    schedule["start_time"] = payload.start_time
    schedule["end_time"] = payload.end_time
    schedule["auto_share_lpr"] = payload.auto_share_lpr
    return _calc_schedule_dto(schedule)


@router.post("/early-return", response_model=EarlyReturnOut)
async def trigger_early_return(
    payload: EarlyReturnIn,
    x_user_id: UUID | None = Header(default=None),
) -> EarlyReturnOut:
    """Kích hoạt cơ chế W3 khi chủ chỗ về sớm: Tự động điều phối xe khách sang ô TH3 dự phòng."""
    schedule = _get_user_schedule(x_user_id)
    schedule["status"] = "early_return_swapped"
    reallocated_id = demo_id("slot", "A", "TH3-01")

    return EarlyReturnOut(
        success=True,
        slot_code=schedule["slot_code"],
        reallocated_slot_code="TH3-01",
        reallocated_slot_id=reallocated_id,
        renter_refund_vnd=35000,
        message=f"Kích hoạt thành công quy trình W3: Xe khách đã được chuyển sang ô TH3-01 dự phòng. Ô {schedule['slot_code']} của bạn đã sẵn sàng trống khi xe về cổng.",
    )
