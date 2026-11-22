"""Pure Domain Logic for Slot Matching and Eligibility (BR-01, BR-11, BR-15, FR-06, FR-07).

Không có I/O, không gọi DB, không phụ thuộc framework ngoài standard library và pydantic.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from uuid import UUID


class SizeClass(StrEnum):
    S = "S"
    M = "M"
    L = "L"
    XL = "XL"


_SIZE_RANK: dict[SizeClass, int] = {
    SizeClass.S: 1,
    SizeClass.M: 2,
    SizeClass.L: 3,
    SizeClass.XL: 4,
}


def can_fit(vehicle_size: SizeClass, slot_size: SizeClass) -> bool:
    """BR-11: Xe nhỏ đỗ ô to được, xe to không thể đỗ ô nhỏ (S < M < L < XL)."""
    return _SIZE_RANK[vehicle_size] <= _SIZE_RANK[slot_size]


class OpenScope(StrEnum):
    building = "building"
    zone = "zone"
    chain = "chain"
    public = "public"


class EligibilityLevel(StrEnum):
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"


_SCOPE_PERMITTED_LEVELS: dict[OpenScope, frozenset[EligibilityLevel]] = {
    OpenScope.building: frozenset({EligibilityLevel.L1}),
    OpenScope.zone: frozenset({EligibilityLevel.L1, EligibilityLevel.L2}),
    OpenScope.chain: frozenset({EligibilityLevel.L1, EligibilityLevel.L2, EligibilityLevel.L3}),
    OpenScope.public: frozenset(
        {
            EligibilityLevel.L1,
            EligibilityLevel.L2,
            EligibilityLevel.L3,
            EligibilityLevel.L4,
        }
    ),
}


def is_scope_eligible(renter_level: EligibilityLevel, scope: OpenScope) -> bool:
    """BR-01, BR-15: Kiểm tra cấp tư cách có nằm trong phạm vi mở của ô/khung chia sẻ không."""
    return renter_level in _SCOPE_PERMITTED_LEVELS[scope]


class SlotOperationalStatus(StrEnum):
    active = "active"
    maintenance = "maintenance"
    blocked = "blocked"


class ShareStatus(StrEnum):
    open = "open"
    closed_early = "closed_early"
    cancelled = "cancelled"
    expired = "expired"


@dataclass(frozen=True)
class TimeRange:
    """Khoảng thời gian [start, end), chuẩn hóa UTC."""

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("TimeRange timestamps must be timezone-aware")
        if self.start >= self.end:
            raise ValueError(f"TimeRange start ({self.start}) must be before end ({self.end})")

    def contains(self, other: "TimeRange") -> bool:
        """Kiểm tra khoảng khác có nằm trọn trong khoảng này không (other <@ self)."""
        return self.start <= other.start and self.end >= other.end

    def apply_buffers(self, buffer_before: timedelta, buffer_after: timedelta) -> "TimeRange | None":
        """FR-06: Trừ buffer an toàn hai đầu để tạo bookable_period."""
        new_start = self.start + buffer_before
        new_end = self.end - buffer_after
        if new_start >= new_end:
            return None
        return TimeRange(start=new_start, end=new_end)


@dataclass(frozen=True)
class SlotCandidate:
    """Thông tin ứng viên ô đỗ và khung chia sẻ sẵn sàng để khớp."""

    slot_id: UUID
    zone_id: UUID
    building_id: UUID
    slot_type: str  # 'TH1', 'TH2', 'TH3'
    size_class: SizeClass
    operational_status: SlotOperationalStatus
    open_scope: OpenScope
    bookable_period: TimeRange
    price_vnd: int
    share_window_id: UUID | None = None
    provider_user_id: UUID | None = None
    window_status: ShareStatus | None = None


@dataclass(frozen=True)
class MatchingRequest:
    """Nhu cầu tìm chỗ đỗ từ người thuê (Renter)."""

    renter_user_id: UUID
    vehicle_id: UUID
    vehicle_size: SizeClass
    renter_level: EligibilityLevel
    requested_period: TimeRange


@dataclass(frozen=True)
class MatchDecision:
    """Kết quả đánh giá ghép cặp."""

    is_match: bool
    reason: str | None = None


def evaluate_match(request: MatchingRequest, candidate: SlotCandidate) -> MatchDecision:
    """Quy tắc nghiệp vụ cốt lõi so khớp ô đỗ (Pure function)."""
    # 1. Trạng thái ô đỗ
    if candidate.operational_status != SlotOperationalStatus.active:
        return MatchDecision(
            is_match=False,
            reason=f"Slot operational status is {candidate.operational_status.value}, expected active",
        )

    # 2. Khung chia sẻ (đối với TH1/TH2)
    if candidate.window_status is not None and candidate.window_status != ShareStatus.open:
        return MatchDecision(
            is_match=False,
            reason=f"Share window status is {candidate.window_status.value}, expected open",
        )

    # 3. Chủ ô không thể tự thuê ô của chính mình
    if candidate.provider_user_id is not None and candidate.provider_user_id == request.renter_user_id:
        return MatchDecision(
            is_match=False,
            reason="Provider cannot be the renter of their own slot",
        )

    # 4. Kiểm tra thời gian (FR-06, FR-07)
    if not candidate.bookable_period.contains(request.requested_period):
        return MatchDecision(
            is_match=False,
            reason="Requested period is not within slot bookable period",
        )

    # 5. Kích thước xe (BR-11)
    if not can_fit(request.vehicle_size, candidate.size_class):
        return MatchDecision(
            is_match=False,
            reason=f"Vehicle size {request.vehicle_size.value} exceeds slot size {candidate.size_class.value}",
        )

    # 6. Tư cách và phạm vi mở (BR-01, BR-15)
    if not is_scope_eligible(request.renter_level, candidate.open_scope):
        return MatchDecision(
            is_match=False,
            reason=f"Renter level {request.renter_level.value} not allowed for scope {candidate.open_scope.value}",
        )

    return MatchDecision(is_match=True)
