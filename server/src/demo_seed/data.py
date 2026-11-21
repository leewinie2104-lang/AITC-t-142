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

    def user(self, key: str) -> UserRow:
        return next(u for u in self.users if u.key == key)


def _ict(year: int, month: int = 1, day: int = 1) -> datetime:
    return datetime(year, month, day, tzinfo=ICT)


def build_demo_data(today: date | None = None) -> DemoData:
    """``today`` is the local (Asia/Ho_Chi_Minh) date; defaults to the current one."""
    if today is None:
        today = datetime.now(UTC).astimezone(ICT).date()
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
    ]
    vehicles = []
    for user, raw, size in vehicle_defs:
        plate = normalize(raw)
        vehicles.append(VehicleRow(demo_id("vehicle", user, plate), uid[user], plate, mask(plate), size))

    return DemoData(zones, buildings, pools, slots, policies, users, assets, eligibilities, holdings, vehicles)
