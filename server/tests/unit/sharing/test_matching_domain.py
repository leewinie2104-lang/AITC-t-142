from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.sharing.domain.matching import (
    EligibilityLevel,
    MatchingRequest,
    OpenScope,
    ShareStatus,
    SizeClass,
    SlotCandidate,
    SlotOperationalStatus,
    TimeRange,
    can_fit,
    evaluate_match,
    is_scope_eligible,
)


def _dt(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 11, 20, hour, minute, tzinfo=UTC)


# =========================================================================
# 1. Size Compatibility (BR-11)
# =========================================================================
@pytest.mark.parametrize(
    "v_size, s_size, expected",
    [
        (SizeClass.S, SizeClass.S, True),
        (SizeClass.S, SizeClass.M, True),
        (SizeClass.S, SizeClass.L, True),
        (SizeClass.S, SizeClass.XL, True),
        (SizeClass.M, SizeClass.S, False),
        (SizeClass.M, SizeClass.M, True),
        (SizeClass.M, SizeClass.L, True),
        (SizeClass.L, SizeClass.M, False),
        (SizeClass.L, SizeClass.L, True),
        (SizeClass.XL, SizeClass.L, False),
        (SizeClass.XL, SizeClass.XL, True),
    ],
)
def test_can_fit_size_rules(v_size: SizeClass, s_size: SizeClass, expected: bool):
    assert can_fit(v_size, s_size) is expected


# =========================================================================
# 2. Scope & Eligibility (BR-01, BR-15)
# =========================================================================
@pytest.mark.parametrize(
    "level, scope, expected",
    [
        (EligibilityLevel.L1, OpenScope.building, True),
        (EligibilityLevel.L2, OpenScope.building, False),
        (EligibilityLevel.L3, OpenScope.building, False),
        (EligibilityLevel.L4, OpenScope.building, False),
        (EligibilityLevel.L1, OpenScope.zone, True),
        (EligibilityLevel.L2, OpenScope.zone, True),
        (EligibilityLevel.L3, OpenScope.zone, False),
        (EligibilityLevel.L1, OpenScope.chain, True),
        (EligibilityLevel.L3, OpenScope.chain, True),
        (EligibilityLevel.L4, OpenScope.chain, False),
        (EligibilityLevel.L1, OpenScope.public, True),
        (EligibilityLevel.L4, OpenScope.public, True),
    ],
)
def test_is_scope_eligible(level: EligibilityLevel, scope: OpenScope, expected: bool):
    assert is_scope_eligible(level, scope) is expected


# =========================================================================
# 3. TimeRange & Buffers (FR-06)
# =========================================================================
def test_timerange_validation():
    with pytest.raises(ValueError, match="timezone-aware"):
        TimeRange(start=datetime(2026, 11, 20, 8, 0), end=_dt(17, 0))

    with pytest.raises(ValueError, match="must be before end"):
        TimeRange(start=_dt(17, 0), end=_dt(8, 0))


def test_timerange_contains():
    outer = TimeRange(start=_dt(8, 0), end=_dt(17, 0))
    inner = TimeRange(start=_dt(9, 0), end=_dt(12, 0))
    exact = TimeRange(start=_dt(8, 0), end=_dt(17, 0))
    overlap_early = TimeRange(start=_dt(7, 30), end=_dt(12, 0))
    overlap_late = TimeRange(start=_dt(12, 0), end=_dt(17, 30))
    disjoint = TimeRange(start=_dt(18, 0), end=_dt(20, 0))

    assert outer.contains(inner) is True
    assert outer.contains(exact) is True
    assert outer.contains(overlap_early) is False
    assert outer.contains(overlap_late) is False
    assert outer.contains(disjoint) is False


def test_timerange_apply_buffers():
    raw_window = TimeRange(start=_dt(8, 0), end=_dt(17, 0))
    # 15 phút đầu và cuối
    bookable = raw_window.apply_buffers(timedelta(minutes=15), timedelta(minutes=15))
    assert bookable is not None
    assert bookable.start == _dt(8, 15)
    assert bookable.end == _dt(16, 45)

    # Buffer quá lớn vượt quá cả khung giờ -> None
    too_large = raw_window.apply_buffers(timedelta(hours=5), timedelta(hours=5))
    assert too_large is None


# =========================================================================
# 4. End-to-End Match Evaluation
# =========================================================================
@pytest.fixture
def base_candidate() -> SlotCandidate:
    return SlotCandidate(
        slot_id=uuid4(),
        zone_id=uuid4(),
        building_id=uuid4(),
        slot_type="TH1",
        size_class=SizeClass.L,
        operational_status=SlotOperationalStatus.active,
        open_scope=OpenScope.zone,
        bookable_period=TimeRange(start=_dt(8, 0), end=_dt(17, 0)),
        price_vnd=50_000,
        share_window_id=uuid4(),
        provider_user_id=uuid4(),
        window_status=ShareStatus.open,
    )


@pytest.fixture
def base_request(base_candidate: SlotCandidate) -> MatchingRequest:
    return MatchingRequest(
        renter_user_id=uuid4(),
        vehicle_id=uuid4(),
        vehicle_size=SizeClass.M,
        renter_level=EligibilityLevel.L2,
        requested_period=TimeRange(start=_dt(9, 0), end=_dt(16, 0)),
    )


def test_evaluate_match_happy_path(base_request: MatchingRequest, base_candidate: SlotCandidate):
    decision = evaluate_match(base_request, base_candidate)
    assert decision.is_match is True
    assert decision.reason is None


def test_evaluate_match_rejects_inactive_slot(base_request: MatchingRequest, base_candidate: SlotCandidate):
    candidate = SlotCandidate(**{**base_candidate.__dict__, "operational_status": SlotOperationalStatus.maintenance})
    decision = evaluate_match(base_request, candidate)
    assert decision.is_match is False
    assert "Slot operational status is maintenance" in (decision.reason or "")


def test_evaluate_match_rejects_cancelled_window(base_request: MatchingRequest, base_candidate: SlotCandidate):
    candidate = SlotCandidate(**{**base_candidate.__dict__, "window_status": ShareStatus.cancelled})
    decision = evaluate_match(base_request, candidate)
    assert decision.is_match is False
    assert "Share window status is cancelled" in (decision.reason or "")


def test_evaluate_match_rejects_self_booking(base_request: MatchingRequest, base_candidate: SlotCandidate):
    # Renter chính là Owner của slot
    req = MatchingRequest(**{**base_request.__dict__, "renter_user_id": base_candidate.provider_user_id})
    decision = evaluate_match(req, base_candidate)
    assert decision.is_match is False
    assert "Provider cannot be the renter" in (decision.reason or "")


def test_evaluate_match_rejects_oversized_vehicle(base_request: MatchingRequest, base_candidate: SlotCandidate):
    # Xe XL muốn đỗ vào slot L
    req = MatchingRequest(**{**base_request.__dict__, "vehicle_size": SizeClass.XL})
    decision = evaluate_match(req, base_candidate)
    assert decision.is_match is False
    assert "Vehicle size XL exceeds slot size L" in (decision.reason or "")


def test_evaluate_match_rejects_ineligible_renter(base_request: MatchingRequest, base_candidate: SlotCandidate):
    # Khách vãng lai (L4) xin vào slot có scope chỉ mở tới zone (L1, L2)
    req = MatchingRequest(**{**base_request.__dict__, "renter_level": EligibilityLevel.L4})
    decision = evaluate_match(req, base_candidate)
    assert decision.is_match is False
    assert "Renter level L4 not allowed for scope zone" in (decision.reason or "")


def test_evaluate_match_rejects_time_overflow(base_request: MatchingRequest, base_candidate: SlotCandidate):
    # Đòi đỗ tới 17:30 trong khi bookable chỉ đến 17:00
    req = MatchingRequest(
        **{
            **base_request.__dict__,
            "requested_period": TimeRange(start=_dt(9, 0), end=_dt(17, 30)),
        }
    )
    decision = evaluate_match(req, base_candidate)
    assert decision.is_match is False
    assert "not within slot bookable period" in (decision.reason or "")
