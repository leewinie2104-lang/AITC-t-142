"""Domain models and value objects for Policy & Rule Engine (M3, ADR-0010)."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class LevelTier(StrEnum):
    """Cấp tư cách tại vị trí ô đỗ (BR-15). Thứ bậc ưu tiên quyền: L1 > L2 > L3 > L4."""

    L1 = "L1"  # Cư dân tòa (căn hộ / shophouse khối đế) - Quyền ưu tiên cao nhất
    L2 = "L2"  # Cư dân khu (tòa khác cùng khu, thấp tầng)
    L3 = "L3"  # Khách nội bộ chuỗi (cư dân khu khác trong hệ thống)
    L4 = "L4"  # Khách vãng lai / công cộng - Quyền thấp nhất

    def is_better_or_equal_to(self, other: "LevelTier") -> bool:
        """Kiểm tra cấp này có quyền bằng hoặc cao hơn cấp đối sánh.

        Quy tắc nghiệp vụ: Cấp ưu tiên L1 > L2 > L3 > L4.
        Do thứ tự từ điển chuỗi ASCII ('L1' < 'L2' < 'L3' < 'L4'), phép so sánh
        `self.value <= other.value` xác định chính xác quyền cao hơn hoặc bằng.
        Ví dụ: L1.is_better_or_equal_to(L4) là True (L1 đáp ứng được mọi phạm vi mở).
        """
        return self.value <= other.value


class OpenScope(StrEnum):
    """Phạm vi mở của ô đỗ / share window (PRD §4, BR-01)."""

    BUILDING = "building"  # Chỉ L1
    ZONE = "zone"  # L1, L2
    CHAIN = "chain"  # L1, L2, L3
    PUBLIC = "public"  # L1, L2, L3, L4

    @property
    def max_allowed_tier(self) -> LevelTier:
        """Cấp thấp nhất được chấp nhận theo phạm vi mở (schema app.scope_max_level)."""
        return _SCOPE_MAX_TIER[self]


_SCOPE_MAX_TIER: dict[OpenScope, LevelTier] = {
    OpenScope.BUILDING: LevelTier.L1,
    OpenScope.ZONE: LevelTier.L2,
    OpenScope.CHAIN: LevelTier.L3,
    OpenScope.PUBLIC: LevelTier.L4,
}


class RuleDecision(StrEnum):
    """Kết quả quyết định tất định của Rule Engine (FR-01, FR-03, FR-04)."""

    PERMIT = "permit"  # Đạt quyền thuê theo phạm vi mở
    REDIRECT_TH3 = "redirect_th3"  # Không đạt phạm vi mở, chuyển hướng sang TH3/công cộng (FR-03, không phạt KPI)
    BLOCK = "block"  # Chặn vi phạm rõ ràng (FR-04: hết hạn tư cách, sai loại chỗ...)


@dataclass(frozen=True)
class UserEligibilityRecord:
    """Bản ghi tư cách của người dùng gắn với tài sản (bảng app.eligibility)."""

    id: UUID
    user_id: UUID
    asset_id: UUID
    zone_id: UUID
    building_id: UUID | None
    role: str  # 'owner', 'tenant', 'authorized', 'employee'
    status: str  # 'verified', 'pending', 'revoked', 'expired'
    valid_from: datetime
    valid_to: datetime | None = None


@dataclass(frozen=True)
class TargetSlotContext:
    """Thông tin ngữ cảnh của ô đỗ đang yêu cầu thuê."""

    slot_id: UUID
    slot_code: str
    building_id: UUID
    zone_id: UUID
    slot_kind: str  # 'TH1', 'TH2', 'TH3'
    open_scope: OpenScope = OpenScope.BUILDING


@dataclass(frozen=True)
class RentalEligibilityResult:
    """Kết quả thẩm định quyền thuê từ Rule Engine."""

    user_id: UUID
    target_slot_id: UUID
    effective_tier: LevelTier
    is_eligible: bool
    decision: RuleDecision
    reason_code: str
    message: str
    valid_until: datetime | None = None
