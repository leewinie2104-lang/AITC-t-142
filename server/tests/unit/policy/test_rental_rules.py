"""Unit tests for Policy Rule Engine (M3, SCRUM-91, BR-01, BR-04, BR-15, BR-16).

Toàn bộ test là pure domain unit tests, không mock database hay network.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.policy.domain.engine import evaluate_rental_eligibility, resolve_renter_tier
from app.policy.domain.models import (
    LevelTier,
    OpenScope,
    RuleDecision,
    TargetSlotContext,
    UserEligibilityRecord,
)


@pytest.fixture
def base_context():
    building_a1 = uuid4()
    building_a2 = uuid4()
    zone_a = uuid4()
    zone_b = uuid4()
    now = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)

    return {
        "building_a1": building_a1,
        "building_a2": building_a2,
        "zone_a": zone_a,
        "zone_b": zone_b,
        "now": now,
    }


def test_resolve_tier_l1_resident_same_building(base_context):
    """BR-15: Cư dân có tài sản trong cùng tòa A1 đạt cấp L1."""
    ctx = base_context
    user_id = uuid4()
    eligibilities = [
        UserEligibilityRecord(
            id=uuid4(),
            user_id=user_id,
            asset_id=uuid4(),
            zone_id=ctx["zone_a"],
            building_id=ctx["building_a1"],
            role="owner",
            status="verified",
            valid_from=ctx["now"] - timedelta(days=30),
            valid_to=ctx["now"] + timedelta(days=335),
        )
    ]

    tier, valid_until, has_expired_only = resolve_renter_tier(
        eligibilities=eligibilities,
        target_building_id=ctx["building_a1"],
        target_zone_id=ctx["zone_a"],
        as_of=ctx["now"],
    )

    assert tier == LevelTier.L1
    assert valid_until is not None
    assert has_expired_only is False


def test_resolve_tier_l2_same_zone_different_building(base_context):
    """BR-15: Cư dân tòa A2 cùng khu A khi thuê ở tòa A1 đạt cấp L2."""
    ctx = base_context
    user_id = uuid4()
    eligibilities = [
        UserEligibilityRecord(
            id=uuid4(),
            user_id=user_id,
            asset_id=uuid4(),
            zone_id=ctx["zone_a"],
            building_id=ctx["building_a2"],  # Khác tòa mục tiêu
            role="owner",
            status="verified",
            valid_from=ctx["now"] - timedelta(days=10),
            valid_to=ctx["now"] + timedelta(days=100),
        )
    ]

    tier, valid_until, has_expired_only = resolve_renter_tier(
        eligibilities=eligibilities,
        target_building_id=ctx["building_a1"],
        target_zone_id=ctx["zone_a"],
        as_of=ctx["now"],
    )

    assert tier == LevelTier.L2
    assert has_expired_only is False


def test_resolve_tier_l3_different_zone_in_chain(base_context):
    """BR-15: Cư dân khu B sang khu A thuê đạt cấp L3 (AC-19, AC-20)."""
    ctx = base_context
    user_id = uuid4()
    eligibilities = [
        UserEligibilityRecord(
            id=uuid4(),
            user_id=user_id,
            asset_id=uuid4(),
            zone_id=ctx["zone_b"],  # Khu B
            building_id=uuid4(),
            role="tenant",
            status="verified",
            valid_from=ctx["now"] - timedelta(days=5),
            valid_to=ctx["now"] + timedelta(days=60),
        )
    ]

    tier, valid_until, has_expired_only = resolve_renter_tier(
        eligibilities=eligibilities,
        target_building_id=ctx["building_a1"],
        target_zone_id=ctx["zone_a"],
        as_of=ctx["now"],
    )

    assert tier == LevelTier.L3
    assert has_expired_only is False


def test_resolve_tier_selects_highest_among_multiple_assets(base_context):
    """BR-15: Người có nhiều tài sản (shophouse ở A, căn hộ ở B) lấy cấp cao nhất tại điểm thuê."""
    ctx = base_context
    user_id = uuid4()
    eligibilities = [
        # Tài sản 1: Khu B (L3 nếu thuê ở A)
        UserEligibilityRecord(
            id=uuid4(),
            user_id=user_id,
            asset_id=uuid4(),
            zone_id=ctx["zone_b"],
            building_id=uuid4(),
            role="owner",
            status="verified",
            valid_from=ctx["now"] - timedelta(days=100),
            valid_to=ctx["now"] + timedelta(days=200),
        ),
        # Tài sản 2: Đúng tòa A1 (L1)
        UserEligibilityRecord(
            id=uuid4(),
            user_id=user_id,
            asset_id=uuid4(),
            zone_id=ctx["zone_a"],
            building_id=ctx["building_a1"],
            role="owner",
            status="verified",
            valid_from=ctx["now"] - timedelta(days=50),
            valid_to=ctx["now"] + timedelta(days=300),
        ),
    ]

    tier, _, _ = resolve_renter_tier(
        eligibilities=eligibilities,
        target_building_id=ctx["building_a1"],
        target_zone_id=ctx["zone_a"],
        as_of=ctx["now"],
    )

    assert tier == LevelTier.L1  # Lấy cấp cao nhất L1 thay vì L3


def test_resolve_tier_l4_for_guest_without_entitlement(base_context):
    """BR-15: Khách vãng lai không có tư cách đạt cấp L4."""
    ctx = base_context

    tier, valid_until, has_expired_only = resolve_renter_tier(
        eligibilities=[],
        target_building_id=ctx["building_a1"],
        target_zone_id=ctx["zone_a"],
        as_of=ctx["now"],
    )

    assert tier == LevelTier.L4
    assert valid_until is None
    assert has_expired_only is False


def test_resolve_tier_detects_expired_entitlements(base_context):
    """BR-16: Phát hiện người thuê chỉ có tư cách đã hết hạn (AC-22 tuan)."""
    ctx = base_context
    user_id = uuid4()
    eligibilities = [
        UserEligibilityRecord(
            id=uuid4(),
            user_id=user_id,
            asset_id=uuid4(),
            zone_id=ctx["zone_a"],
            building_id=ctx["building_a1"],
            role="tenant",
            status="verified",
            valid_from=ctx["now"] - timedelta(days=365),
            valid_to=ctx["now"] - timedelta(days=1),  # Hết hạn hôm qua
        )
    ]

    tier, valid_until, has_expired_only = resolve_renter_tier(
        eligibilities=eligibilities,
        target_building_id=ctx["building_a1"],
        target_zone_id=ctx["zone_a"],
        as_of=ctx["now"],
    )

    assert tier == LevelTier.L4
    assert valid_until is None
    assert has_expired_only is True


def test_evaluate_th1_permit_l1(base_context):
    """BR-01: Ô TH1 mở phạm vi tòa (building) -> Chấp thuận cư dân L1."""
    ctx = base_context
    user_id = uuid4()
    slot = TargetSlotContext(
        slot_id=uuid4(),
        slot_code="B2-045",
        building_id=ctx["building_a1"],
        zone_id=ctx["zone_a"],
        slot_kind="TH1",
        open_scope=OpenScope.BUILDING,
    )
    eligibilities = [
        UserEligibilityRecord(
            id=uuid4(),
            user_id=user_id,
            asset_id=uuid4(),
            zone_id=ctx["zone_a"],
            building_id=ctx["building_a1"],
            role="owner",
            status="verified",
            valid_from=ctx["now"] - timedelta(days=10),
            valid_to=ctx["now"] + timedelta(days=300),
        )
    ]

    res = evaluate_rental_eligibility(user_id, eligibilities, slot, ctx["now"])

    assert res.is_eligible is True
    assert res.decision == RuleDecision.PERMIT
    assert res.effective_tier == LevelTier.L1
    assert res.reason_code == "ELIGIBLE"


def test_evaluate_th1_redirect_l2_outside_open_scope(base_context):
    """FR-03 & BR-01: Cư dân L2 thuê ô TH1 chỉ mở phạm vi building -> Chuyển hướng TH3, không phạt KPI."""
    ctx = base_context
    user_id = uuid4()
    slot = TargetSlotContext(
        slot_id=uuid4(),
        slot_code="B2-045",
        building_id=ctx["building_a1"],
        zone_id=ctx["zone_a"],
        slot_kind="TH1",
        open_scope=OpenScope.BUILDING,
    )
    eligibilities = [
        UserEligibilityRecord(
            id=uuid4(),
            user_id=user_id,
            asset_id=uuid4(),
            zone_id=ctx["zone_a"],
            building_id=ctx["building_a2"],  # Khác tòa
            role="owner",
            status="verified",
            valid_from=ctx["now"] - timedelta(days=10),
            valid_to=ctx["now"] + timedelta(days=300),
        )
    ]

    res = evaluate_rental_eligibility(user_id, eligibilities, slot, ctx["now"])

    assert res.is_eligible is False
    assert res.decision == RuleDecision.REDIRECT_TH3
    assert res.effective_tier == LevelTier.L2
    assert res.reason_code == "OUTSIDE_OPEN_SCOPE"


def test_evaluate_expired_eligibility_blocks_transaction(base_context):
    """BR-16 & FR-04: Tư cách hết hạn -> Chặn giao dịch mới với lý do EXPIRED_ELIGIBILITY."""
    ctx = base_context
    user_id = uuid4()
    slot = TargetSlotContext(
        slot_id=uuid4(),
        slot_code="B2-045",
        building_id=ctx["building_a1"],
        zone_id=ctx["zone_a"],
        slot_kind="TH1",
        open_scope=OpenScope.BUILDING,
    )
    eligibilities = [
        UserEligibilityRecord(
            id=uuid4(),
            user_id=user_id,
            asset_id=uuid4(),
            zone_id=ctx["zone_a"],
            building_id=ctx["building_a1"],
            role="tenant",
            status="verified",
            valid_from=ctx["now"] - timedelta(days=100),
            valid_to=ctx["now"] - timedelta(days=2),  # Hết hạn 2 ngày trước
        )
    ]

    res = evaluate_rental_eligibility(user_id, eligibilities, slot, ctx["now"])

    assert res.is_eligible is False
    assert res.decision == RuleDecision.BLOCK
    assert res.reason_code == "EXPIRED_ELIGIBILITY"


def test_evaluate_th3_unauthorized_sharing_blocks(base_context):
    """BR-03: Ô TH3 không được phép cấu hình chia sẻ cá nhân ngoài phạm vi công cộng."""
    ctx = base_context
    user_id = uuid4()
    slot = TargetSlotContext(
        slot_id=uuid4(),
        slot_code="TH3-01",
        building_id=ctx["building_a1"],
        zone_id=ctx["zone_a"],
        slot_kind="TH3",
        open_scope=OpenScope.BUILDING,  # Bất thường: TH3 cá nhân chia sẻ
    )

    res = evaluate_rental_eligibility(user_id, [], slot, ctx["now"])

    assert res.is_eligible is False
    assert res.decision == RuleDecision.BLOCK
    assert res.reason_code == "UNAUTHORIZED_TH3_SHARING"
