"""Domain models and value objects for Policy & Rule Engine (M3, ADR-0010)."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class LevelTier(StrEnum):
    """Cấp tư cách tại vị trí ô đỗ (BR-15). Thứ bậc: L1 > L2 > L3 > L4."""

    L1 = "L1"  # Thành viên tòa (cư dân / shophouse khối đế tòa)
    L2 = "L2"  # Thành viên khu (cư dân tòa khác cùng khu, shophouse thấp tầng)
    L3 = "L3"  # Thành viên chuỗi (cư dân khu khác trong hệ sinh thái)
    L4 = "L4"  # Khách vãng lai (không có tư cách hợp lệ)

    def is_better_or_equal_to(self, other: "LevelTier") -> bool:
        """Kiểm tra cấp này có bằng hoặc cao hơn cấp đối sánh (L1 < L2 < L3 < L4)."""
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
        mapping = {
            OpenScope.BUILDING: LevelTier.L1,
            OpenScope.ZONE: LevelTier.L2,
            OpenScope.CHAIN: LevelTier.L3,
            OpenScope.PUBLIC: LevelTier.L4,
        }
        return mapping[self]


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
