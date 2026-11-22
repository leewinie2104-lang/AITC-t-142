"""Pure domain functions for Rule Engine (M3, ADR-0010).

Hoàn toàn là pure functions không I/O, không gọi DB, không gọi LLM (ADR-0010, BR-14).
"""

from datetime import datetime
from uuid import UUID

from app.policy.domain.models import (
    LevelTier,
    OpenScope,
    RentalEligibilityResult,
    RuleDecision,
    TargetSlotContext,
    UserEligibilityRecord,
)


def resolve_renter_tier(
    eligibilities: list[UserEligibilityRecord],
    target_building_id: UUID,
    target_zone_id: UUID,
    as_of: datetime,
) -> tuple[LevelTier, datetime | None, bool]:
    """Tính cấp tư cách cao nhất tại vị trí ô đỗ (BR-15, BR-16).

    Args:
        eligibilities: Danh sách các bản ghi tư cách của người dùng (từ bảng app.eligibility).
        target_building_id: UUID của tòa nhà chứa ô đỗ đang yêu cầu.
        target_zone_id: UUID của khu đô thị chứa ô đỗ đang yêu cầu.
        as_of: Thời điểm xét duyệt tư cách (aware datetime).

    Returns:
        tuple (Cấp cao nhất đạt được, Thời điểm hết hạn sớm nhất của tư cách đó, Có phải chỉ có tư cách đã hết hạn).
    """
    # 1. Lọc các bản ghi tư cách hợp lệ (đã xác minh và còn hạn tại thời điểm as_of)
    active_records = [
        rec
        for rec in eligibilities
        if rec.status == "verified" and rec.valid_from <= as_of and (rec.valid_to is None or rec.valid_to >= as_of)
    ]

    if not active_records:
        # Kiểm tra xem người dùng có phải từng có tư cách nhưng toàn bộ đã hết hạn không (BR-16)
        has_expired_only = bool(eligibilities) and all(
            rec.status == "expired" or (rec.valid_to is not None and rec.valid_to < as_of) for rec in eligibilities
        )
        return LevelTier.L4, None, has_expired_only

    # 2. Đánh giá cấp cho từng bản ghi còn hạn và chọn cấp cao nhất (L1 > L2 > L3)
    best_tier = LevelTier.L4
    best_valid_until: datetime | None = None

    for rec in active_records:
        if rec.building_id is not None and rec.building_id == target_building_id:
            tier = LevelTier.L1
        elif rec.zone_id == target_zone_id:
            tier = LevelTier.L2
        else:
            tier = LevelTier.L3

        if tier.is_better_or_equal_to(best_tier):
            # Nếu đạt cấp cao hơn, hoặc bằng cấp nhưng thời hạn xa hơn
            if tier != best_tier or (
                rec.valid_to is not None and (best_valid_until is None or rec.valid_to > best_valid_until)
            ):
                best_tier = tier
                best_valid_until = rec.valid_to

    return best_tier, best_valid_until, False


def evaluate_rental_eligibility(
    user_id: UUID,
    eligibilities: list[UserEligibilityRecord],
    target_slot: TargetSlotContext,
    as_of: datetime,
) -> RentalEligibilityResult:
    """Thẩm định quyền thuê tất định theo BR-01, BR-04, BR-15, BR-16, FR-01, FR-03, FR-04.

    Args:
        user_id: UUID của người thuê.
        eligibilities: Danh sách tư cách tài sản của người thuê.
        target_slot: Thông tin ô đỗ mục tiêu (loại ô TH1/TH2/TH3, phạm vi mở, tòa, khu).
        as_of: Thời điểm kiểm tra (aware UTC datetime).

    Returns:
        RentalEligibilityResult với quyết định PERMIT, REDIRECT_TH3 hoặc BLOCK.
    """
    # Quy tắc BR-03: Chỗ TH3 chỉ BQL khai thác công cộng, không được phép phát sinh giao dịch chia sẻ cá nhân
    if target_slot.slot_kind.upper() == "TH3" and target_slot.open_scope != OpenScope.PUBLIC:
        return RentalEligibilityResult(
            user_id=user_id,
            target_slot_id=target_slot.slot_id,
            effective_tier=LevelTier.L4,
            is_eligible=False,
            decision=RuleDecision.BLOCK,
            reason_code="UNAUTHORIZED_TH3_SHARING",
            message="Chỗ TH3 là bãi công cộng do BQL vận hành, không được phép chia sẻ cá nhân (BR-03).",
        )

    # 1. Tính cấp tư cách của người thuê tại vị trí ô đỗ (BR-15)
    renter_tier, valid_until, has_expired_only = resolve_renter_tier(
        eligibilities=eligibilities,
        target_building_id=target_slot.building_id,
        target_zone_id=target_slot.zone_id,
        as_of=as_of,
    )

    # 2. Quy tắc BR-16: Chặn giao dịch mới nếu toàn bộ tư cách cư dân đã hết hạn
    if has_expired_only:
        return RentalEligibilityResult(
            user_id=user_id,
            target_slot_id=target_slot.slot_id,
            effective_tier=LevelTier.L4,
            is_eligible=False,
            decision=RuleDecision.BLOCK,
            reason_code="EXPIRED_ELIGIBILITY",
            message="Tư cách cư dân / thành viên của bạn đã hết hạn hiệu lực. Hệ thống chặn giao dịch mới theo quy định BR-16.",
            valid_until=valid_until,
        )

    # 3. Quy tắc BR-01 & BR-04: Đối chiếu cấp với phạm vi mở của ô đỗ
    max_allowed = target_slot.open_scope.max_allowed_tier

    if renter_tier.is_better_or_equal_to(max_allowed):
        # Đạt điều kiện phạm vi mở
        return RentalEligibilityResult(
            user_id=user_id,
            target_slot_id=target_slot.slot_id,
            effective_tier=renter_tier,
            is_eligible=True,
            decision=RuleDecision.PERMIT,
            reason_code="ELIGIBLE",
            message=f"Đạt điều kiện thuê: Cấp {renter_tier.value} đáp ứng phạm vi mở '{target_slot.open_scope.value}' của ô {target_slot.slot_code}.",
            valid_until=valid_until,
        )

    # 4. Quy tắc FR-03: Không đạt phạm vi mở -> Chuyển hướng sang TH3/công cộng (không phạt KPI)
    return RentalEligibilityResult(
        user_id=user_id,
        target_slot_id=target_slot.slot_id,
        effective_tier=renter_tier,
        is_eligible=False,
        decision=RuleDecision.REDIRECT_TH3,
        reason_code="OUTSIDE_OPEN_SCOPE",
        message=(
            f"Cấp {renter_tier.value} không nằm trong phạm vi mở '{target_slot.open_scope.value}' của ô {target_slot.slot_code} "
            f"(yêu cầu tối thiểu cấp {max_allowed.value}). Đã chuyển hướng sang ô TH3 / bãi công cộng theo FR-03."
        ),
        valid_until=valid_until,
    )
