"""Demo dataset: 3 zones, scenario of docs/03-design/sql/seed-and-tests.sql sections 1-2.

Pure data, no I/O. ``build_demo_data`` is deterministic for a given ``today`` (the only moving part: the AC-22 lease
of ``tuan`` ends at the end of yesterday, local time).

Scenario (Scope section 1): one operator, 3 zones.
  A: Tower A1 (TH1 + TH2 slots), shophouse cluster ALR, public lot APL (TH3).
  B: Tower B1 (TH1).
  C: Tower C1 with a TH2 pool open to the whole chain, public lot CPL (TH3).
Users: lan (A1 owner, holds TH1 B2-045/B2-046), binh (A1 owner, L1; lessee of TH2 B2-101), minh (shophouse in A +
apartment in B: L2 in A, L1 in B1, L3 in C - AC-19), hoa (B1 resident, L3 in C - AC-20), tuan (A1 tenant, expired
yesterday - AC-22), khach (guest, L4), van (C1 resident, lessee of TH2 B1-010), one BQL per zone, guard_a, op.

Prices, buffers and thresholds are the researched defaults of docs/03-design/07-db-decision-log.md: ALL ARE
"default, confirm with BQL" (they come from the zone_policy column DEFAULTs except ``prices``).
"""

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone
from uuid import UUID

from app.facility.domain.plate import mask, normalize

from .ids import demo_id

ICT = timezone(timedelta(hours=7))  # Asia/Ho_Chi_Minh has no DST

_PRICES = {
    "TH1": {"L1": {"hour": 10000, "day": 50000}, "L2": {"hour": 10000, "day": 50000}},
    "TH2": {
        "L1": {"hour": 10000, "day": 50000},
        "L2": {"hour": 10000, "day": 50000},
        "L3": {"hour": 15000, "day": 70000},
    },
    "TH3": {"L1": {"hour": 20000}, "L2": {"hour": 20000}, "L3": {"hour": 20000}, "L4": {"hour": 30000}},
}
_AGREEMENT_TEMPLATE = (
    "# Thỏa thuận chia sẻ chỗ đỗ — Bên cho thuê {{provider}} chia sẻ chỗ {{slot}} cho Bên thuê {{renter}} "
    "trong khoảng {{period}}, giá {{price_vnd}} đ. Hai bên xác nhận bằng mã OTP."
)
# Pilot (docs/01-product/07-pilot-mot-toa.md section 7, Tower A1) lives on the demo day = tomorrow, local time. Every
# demo-day clock time, including the gate events of lpr_csv.py, is defined here and nowhere else.
CLOCK: dict[str, time] = {
    # share windows (owner away); bookable = period minus buffers (15 min before, 30 min after, zone_policy defaults)
    "a_win_from": time(7, 45), "a_win_to": time(16, 0),   # chi_a: "free until 16:00"
    "c_win_from": time(7, 45), "c_win_to": time(18, 0),   # anh_c
    # anh_b rents anh_c's slot, planned exit 15:00; history: anh_b overstayed on chi_a's slot, anh_c came home early (window closed_early)
    "b_from": time(8, 30), "b_to": time(15, 0),
    "hist_b_from": time(8, 0), "hist_b_to": time(12, 0), "hist_b_in": time(8, 5), "hist_b_out": time(12, 50),
    "hist_c_from": time(9, 0), "hist_c_to": time(16, 0), "hist_c_in": time(9, 5), "hist_c_out": time(15, 55),
    "hist_c_return": time(13, 10),  # anh_c came home early: his window closed at this time
    # gate events: pilot timeline
    "gate_a_in": time(6, 50), "gate_c_out": time(8, 5), "gate_b_in": time(8, 25),
    "gate_c_back": time(14, 20), "gate_b_out": time(15, 40),
    # gate events: 3-zone set
    "gate_lan_in": time(7, 55), "gate_lan_out": time(17, 10), "gate_hoa_in": time(7, 30), "gate_hoa_out": time(18, 5),
    "gate_minh_in": time(9, 10), "gate_minh_out": time(11, 45), "gate_lowocr": time(10, 12),
    "gate_unreadable": time(12, 20), "gate_unknown": time(13, 5),
}  # fmt: skip
HISTORY_DAYS = {"a": 3, "c": 2}  # past windows / bookings sit this many days before the demo day
_BUFFER_BEFORE, _BUFFER_AFTER = timedelta(minutes=15), timedelta(minutes=30)
# Schema v7 (migration 0012): an open window needs the owner's OTP confirmation and a listing expiry.
# The owner confirms 15' before the window starts; the listing lapses after zone_policy.listing_expiry (default 30').
_POSTED_BEFORE, _LISTING_EXPIRY = timedelta(minutes=15), timedelta(minutes=30)
_POLICY_EFFECTIVE_FROM = datetime(2026, 1, 1, tzinfo=ICT)
_CONSENT_AT = datetime(2026, 1, 1, tzinfo=ICT)


@dataclass(frozen=True)
class ZoneRow:
    id: UUID
    code: str
    name: str


@dataclass(frozen=True)
class BuildingRow:
    id: UUID
    zone_id: UUID
    subzone_code: str | None
    code: str
    name: str
    kind: str


@dataclass(frozen=True)
class PoolRow:
    id: UUID
    zone_id: UUID
    building_id: UUID | None
    slot_type: str
    max_open_scope: str
    investor_consent_at: datetime | None


@dataclass(frozen=True)
class SlotRow:
    id: UUID
    zone_id: UUID
    building_id: UUID
    pool_id: UUID
    slot_type: str
    level_code: str
    code: str
    size_class: str


@dataclass(frozen=True)
class PolicyRow:
    id: UUID
    zone_id: UUID
    version: int
    effective_from: datetime
    prices_json: str
    agreement_template_md: str


@dataclass(frozen=True)
class UserRow:
    id: UUID
    key: str
    full_name: str
    phone_e164: str
    role: str
    staff_zone_id: UUID | None


@dataclass(frozen=True)
class AssetRow:
    id: UUID
    zone_id: UUID
    building_id: UUID | None
    kind: str
    code: str


@dataclass(frozen=True)
class EligibilityRow:
    id: UUID
    user_id: UUID
    asset_id: UUID
    zone_id: UUID
    role: str
    valid_from: datetime
    valid_to: datetime | None
    status: str
    verified_by: UUID


@dataclass(frozen=True)
class HoldingRow:
    id: UUID
    zone_id: UUID
    slot_id: UUID
    slot_type: str
    user_id: UUID
    kind: str
    held_from: datetime


@dataclass(frozen=True)
class VehicleRow:
    id: UUID
    user_id: UUID
    plate: str  # normalized, PII: only the writer encrypts it
    plate_masked: str
    size_class: str


@dataclass(frozen=True)
class WindowRow:
    id: UUID
    zone_id: UUID
    slot_id: UUID
    owner_user_id: UUID
    period_from: datetime
    period_to: datetime
    bookable_from: datetime
    bookable_to: datetime
    open_scope: str
    idempotency_key: str
    otp_confirmed_at: datetime
    expires_at: datetime
    returned_at: datetime | None = None  # owner came home early: the writer closes the window (status closed_early)


@dataclass(frozen=True)
class BookingRow:
    id: UUID
    zone_id: UUID
    slot_id: UUID
    window_id: UUID
    provider_user_id: UUID
    renter_user_id: UUID
    vehicle_id: UUID
    period_from: datetime
    period_to: datetime
    eligibility_level: str
    price_vnd: int
    status: str
    checked_in_at: datetime | None
    checked_out_at: datetime | None
    idempotency_key: str


@dataclass(frozen=True)
class DemoData:
    zones: list[ZoneRow]
    buildings: list[BuildingRow]
    pools: list[PoolRow]
    slots: list[SlotRow]
    policies: list[PolicyRow]
    users: list[UserRow]
    assets: list[AssetRow]
    eligibilities: list[EligibilityRow]
    holdings: list[HoldingRow]
    vehicles: list[VehicleRow]
    windows: list[WindowRow]  # newest first: shifting them forward one by one never overlaps two windows of a slot
    bookings: list[BookingRow]
    demo_day: date

    def user(self, key: str) -> UserRow:
        return next(u for u in self.users if u.key == key)


def _at(day: date, key: str) -> datetime:
    return datetime.combine(day, CLOCK[key], tzinfo=ICT)


def _ict(year: int, month: int = 1, day: int = 1) -> datetime:
    return datetime(year, month, day, tzinfo=ICT)


def build_demo_data(today: date | None = None) -> DemoData:
    """``today`` is the local (Asia/Ho_Chi_Minh) date; defaults to the current one. The pilot day is ``today + 1``."""
    if today is None:
        today = datetime.now(UTC).astimezone(ICT).date()
    demo_day = today + timedelta(days=1)
    end_of_yesterday = datetime.combine(today, time.min, tzinfo=ICT)  # = start of today, local

    # --- zones, buildings ---
    zone_names = {"A": "Khu A", "B": "Khu B", "C": "Khu C"}
    zid = {code: demo_id("zone", code) for code in zone_names}
    zones = [ZoneRow(zid[code], code, name) for code, name in zone_names.items()]

    building_defs = [
        ("A", "A-S1", "A1", "Tòa A1", "residential_tower"),
        ("A", "A-S1", "ALR", "Cụm shophouse A", "lowrise_cluster"),
        ("A", "A-S1", "APL", "Bãi công cộng A", "public_lot"),
        ("B", "B-S1", "B1", "Tòa B1", "residential_tower"),
        ("C", "C-S1", "C1", "Tòa C1", "residential_tower"),
        ("C", None, "CPL", "Bãi công cộng C", "public_lot"),
    ]
    bid = {code: demo_id("building", z, code) for z, _, code, _, _ in building_defs}
    buildings = [BuildingRow(bid[c], zid[z], sub, c, n, k) for z, sub, c, n, k in building_defs]

    # --- pools: (zone, building or None, type, max open scope, investor consent) ---
    pool_defs = [
        ("A", "A1", "TH1", "building", False),
        ("A", None, "TH2", "zone", True),
        ("A", None, "TH3", "public", False),
        ("B", "B1", "TH1", "building", False),
        ("C", None, "TH2", "chain", True),
        ("C", None, "TH3", "public", False),
    ]
    pid = {(z, t): demo_id("pool", z, b or "-", t) for z, b, t, _, _ in pool_defs}
    pools = [
        PoolRow(pid[(z, t)], zid[z], bid[b] if b else None, t, scope, _CONSENT_AT if consent else None)
        for z, b, t, scope, consent in pool_defs
    ]

    # --- slots: (zone, building, pool type, level, code, size) ---
    slot_defs = [
        ("A", "A1", "TH1", "B2", "B2-045", "M"),
        ("A", "A1", "TH1", "B2", "B2-046", "S"),
        ("A", "A1", "TH1", "B2", "B2-050", "M"),  # pilot: chi_a
        ("A", "A1", "TH1", "B3", "B3-001", "M"),  # pilot: anh_c, another floor
        ("A", "A1", "TH2", "B2", "B2-101", "L"),
        ("A", "APL", "TH3", "G", "TH3-012", "L"),
        ("A", "APL", "TH3", "G", "TH3-013", "L"),
        ("B", "B1", "TH1", "B1", "B1-001", "M"),
        ("C", "C1", "TH2", "B1", "B1-010", "L"),
        ("C", "CPL", "TH3", "G", "TH3-001", "L"),
    ]
    sid = {(b, c): demo_id("slot", b, c) for _, b, _, _, c, _ in slot_defs}
    slots = [SlotRow(sid[(b, c)], zid[z], bid[b], pid[(z, t)], t, lvl, c, size) for z, b, t, lvl, c, size in slot_defs]

    # --- zone policy v1 for every zone ---
    prices_json = json.dumps(_PRICES, separators=(",", ":"))
    policies = [
        PolicyRow(demo_id("policy", z, "1"), zid[z], 1, _POLICY_EFFECTIVE_FROM, prices_json, _AGREEMENT_TEMPLATE)
        for z in zone_names
    ]

    # --- users: 5 roles (resident, renter, guard, zone_manager, chain_operator) ---
    user_defs = [
        ("lan", "Nguyễn Thị Lan", "+84901000001", "resident", None),
        ("binh", "Trần Văn Bình", "+84901000002", "resident", None),
        ("minh", "Lê Minh", "+84901000003", "resident", None),
        ("hoa", "Phạm Thu Hoa", "+84901000004", "resident", None),
        ("tuan", "Đỗ Tuấn", "+84901000005", "renter", None),
        ("khach", "Khách Vãng Lai", "+84901000006", "renter", None),
        ("van", "Vũ Văn", "+84901000007", "resident", None),
        ("chi_a", "Chị A", "+84901000008", "resident", None),  # pilot, Tower A1
        ("anh_b", "Anh B", "+84901000009", "resident", None),
        ("anh_c", "Anh C", "+84901000010", "resident", None),
        ("bql_a", "BQL Khu A", "+84902000001", "zone_manager", "A"),
        ("bql_b", "BQL Khu B", "+84902000002", "zone_manager", "B"),
        ("bql_c", "BQL Khu C", "+84902000003", "zone_manager", "C"),
        ("guard_a", "Bảo vệ A", "+84903000001", "guard", "A"),
        ("op", "Vận hành chuỗi", "+84904000001", "chain_operator", None),
    ]
    uid = {key: demo_id("user", key) for key, *_ in user_defs}
    users = [UserRow(uid[k], k, n, p, r, zid[z] if z else None) for k, n, p, r, z in user_defs]

    # --- assets (unit numbers) ---
    asset_defs = [
        ("lan", "A", "A1", "apartment", "A1-12-05"),
        ("binh", "A", "A1", "apartment", "A1-15-01"),
        ("minh_a", "A", None, "shophouse", "ALR-S07"),
        ("minh_b", "B", "B1", "apartment", "B1-08-02"),
        ("hoa", "B", "B1", "apartment", "B1-10-10"),
        ("tuan", "A", "A1", "apartment", "A1-20-03"),
        ("van", "C", "C1", "apartment", "C1-05-05"),
        ("chi_a", "A", "A1", "apartment", "A1-08-01"),
        ("anh_b", "A", "A1", "apartment", "A1-09-02"),
        ("anh_c", "A", "A1", "apartment", "A1-11-03"),
    ]
    aid = {key: demo_id("asset", z, code) for key, z, _, _, code in asset_defs}
    assets = [AssetRow(aid[k], zid[z], bid[b] if b else None, kind, code) for k, z, b, kind, code in asset_defs]
    asset_zone = {k: zid[z] for k, z, *_ in asset_defs}

    # --- eligibility: (user, asset, role, valid_from, valid_to, verifier) ---
    elig_defs: list[tuple[str, str, str, datetime, datetime | None, str]] = [
        ("lan", "lan", "owner", _ict(2020), None, "bql_a"),
        ("binh", "binh", "owner", _ict(2020), None, "bql_a"),
        ("minh", "minh_a", "owner", _ict(2021), None, "bql_a"),
        ("minh", "minh_b", "owner", _ict(2021), None, "bql_b"),
        ("hoa", "hoa", "owner", _ict(2022), None, "bql_b"),
        ("tuan", "tuan", "tenant", _ict(2025), end_of_yesterday, "bql_a"),  # AC-22: lease ended yesterday
        ("van", "van", "owner", _ict(2020), None, "bql_c"),
        ("chi_a", "chi_a", "owner", _ict(2024), None, "bql_a"),
        ("anh_b", "anh_b", "owner", _ict(2024), None, "bql_a"),
        ("anh_c", "anh_c", "owner", _ict(2024), None, "bql_a"),
    ]
    eligibilities = [
        EligibilityRow(
            demo_id("eligibility", u, a, role), uid[u], aid[a], asset_zone[a], role, frm, to, "verified", uid[ver]
        )
        for u, a, role, frm, to, ver in elig_defs
    ]

    # --- slot holdings: (zone, building, slot code, type, user, kind, from) ---
    holding_defs = [
        ("A", "A1", "B2-045", "TH1", "lan", "owner", _ict(2020)),
        ("A", "A1", "B2-046", "TH1", "lan", "owner", _ict(2020)),
        ("A", "A1", "B2-101", "TH2", "binh", "lessee", _ict(2024)),
        ("C", "C1", "B1-010", "TH2", "van", "lessee", _ict(2024)),
        ("A", "A1", "B2-050", "TH1", "chi_a", "owner", _ict(2024)),
        ("A", "A1", "B3-001", "TH1", "anh_c", "owner", _ict(2024)),
    ]
    holdings = [
        HoldingRow(demo_id("holding", b, c, u), zid[z], sid[(b, c)], t, uid[u], kind, frm)
        for z, b, c, t, u, kind, frm in holding_defs
    ]

    # --- vehicles: (user, raw plate, size class) ---
    vehicle_defs = [
        ("lan", "30A-123.45", "M"),
        ("binh", "30A-222.22", "M"),
        ("binh", "29C-999.99", "XL"),
        ("minh", "51G-333.33", "M"),
        ("hoa", "30E-444.44", "M"),
        ("tuan", "30F-555.55", "M"),
        ("khach", "29H-666.66", "M"),
        ("chi_a", "30B-111.11", "M"),
        ("anh_b", "30B-222.22", "M"),
        ("anh_c", "30B-333.33", "M"),
    ]
    vehicles = []
    for user, raw, size in vehicle_defs:
        plate = normalize(raw)
        vehicles.append(VehicleRow(demo_id("vehicle", user, plate), uid[user], plate, mask(plate), size))

    # --- pilot share windows and bookings in Tower A1 (zone A): open scope 'building', A1 residents are L1 ---
    slot_a, slot_c = sid[("A1", "B2-050")], sid[("A1", "B3-001")]
    d_a, d_c = (demo_day - timedelta(days=HISTORY_DAYS[k]) for k in ("a", "c"))
    window_defs = [  # key, slot, owner, day, from, to, owner returned at
        ("a_today", slot_a, "chi_a", demo_day, "a_win_from", "a_win_to", None),
        ("c_today", slot_c, "anh_c", demo_day, "c_win_from", "c_win_to", None),
        ("c_hist", slot_c, "anh_c", d_c, "c_win_from", "c_win_to", "hist_c_return"),
        ("a_hist", slot_a, "chi_a", d_a, "a_win_from", "a_win_to", None),
    ]
    windows = {}
    for key, slot, owner, day, frm, to, back in window_defs:
        start, end = _at(day, frm), _at(day, to)
        windows[key] = WindowRow(
            demo_id("share_window", key), zid["A"], slot, uid[owner], start, end,
            start + _BUFFER_BEFORE, end - _BUFFER_AFTER, "building", f"seed:pilot:w-{key}",
            start - _POSTED_BEFORE, start - _POSTED_BEFORE + _LISTING_EXPIRY, _at(day, back) if back else None,
        )  # fmt: skip
    th1_hour = _PRICES["TH1"]["L1"]["hour"]
    vehicle_of = {v.user_id: v.id for v in vehicles}
    booking_defs = [  # key, window, renter, day, from, to, status, checked in, checked out
        ("b_today", "c_today", "anh_b", demo_day, "b_from", "b_to", "confirmed", None, None),
        # anh_b overstayed: left 12:50, planned 12:00
        ("b_hist", "a_hist", "anh_b", d_a, "hist_b_from", "hist_b_to", "completed", "hist_b_in", "hist_b_out"),
        # chi_a's normal booking; anh_c came home early, see the c_hist window (recovery_case needs v6 columns)
        ("c_hist", "c_hist", "chi_a", d_c, "hist_c_from", "hist_c_to", "completed", "hist_c_in", "hist_c_out"),
    ]
    bookings = []
    for key, wkey, renter, day, frm, to, status, cin, cout in booking_defs:
        w = windows[wkey]
        start, end = _at(day, frm), _at(day, to)
        price = int((end - start).total_seconds() * th1_hour / 3600)  # pro rata of the zone price per hour
        bookings.append(
            BookingRow(
                demo_id("booking", key), w.zone_id, w.slot_id, w.id, w.owner_user_id, uid[renter], vehicle_of[uid[renter]],
                start, end, "L1", price, status, _at(day, cin) if cin else None, _at(day, cout) if cout else None,
                f"seed:pilot:b-{key}",
            )
        )  # fmt: skip
    return DemoData(
        zones, buildings, pools, slots, policies, users, assets, eligibilities, holdings, vehicles,
        list(windows.values()), bookings, demo_day,
    )  # fmt: skip
