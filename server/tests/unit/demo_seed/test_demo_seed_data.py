"""The demo dataset is internally consistent and mirrors the schema's CHECK / FK rules (no DB needed)."""

import json
import re
from datetime import date, datetime, timedelta

import pytest

from demo_seed.data import ICT, DemoData, build_demo_data
from demo_seed.ids import demo_id

TODAY = date(2026, 11, 21)


@pytest.fixture(scope="module")
def data() -> DemoData:
    return build_demo_data(TODAY)


def _ids(rows: list) -> list:
    return [r.id for r in rows]


def test_ids_are_unique_within_each_table(data: DemoData) -> None:
    for name in ("zones", "buildings", "pools", "slots", "policies", "users", "assets", "eligibilities", "holdings",
                 "vehicles"):  # fmt: skip
        ids = _ids(getattr(data, name))
        assert len(ids) == len(set(ids)), name


def test_ids_are_stable_across_builds_and_machines() -> None:
    a, b = build_demo_data(TODAY), build_demo_data(TODAY)
    assert _ids(a.users) == _ids(b.users)
    assert _ids(a.vehicles) == _ids(b.vehicles)
    # Pinned values: SCRUM-110 (LPR CSV) and eval datasets may hard-code them. Changing them is a breaking change.
    assert str(demo_id("zone", "A")) == str(a.zones[0].id)
    assert a.user("lan").id == demo_id("user", "lan")


def test_three_zones_each_with_policy_manager_and_pools(data: DemoData) -> None:
    assert [z.code for z in data.zones] == ["A", "B", "C"]
    zone_ids = {z.id for z in data.zones}
    assert {p.zone_id for p in data.policies} == zone_ids
    assert {u.staff_zone_id for u in data.users if u.role == "zone_manager"} == zone_ids  # BR-18: an approver per zone
    assert {p.zone_id for p in data.pools} == zone_ids


def test_all_five_roles_are_present(data: DemoData) -> None:
    assert {u.role for u in data.users} == {"resident", "renter", "guard", "zone_manager", "chain_operator"}


def test_staff_zone_only_on_guard_and_manager(data: DemoData) -> None:
    for u in data.users:
        if u.staff_zone_id is not None:
            assert u.role in {"guard", "zone_manager"}, u.key
        elif u.role in {"guard", "zone_manager"}:
            pytest.fail(f"{u.key} is staff without a zone")


def test_phones_are_unique_e164(data: DemoData) -> None:
    phones = [u.phone_e164 for u in data.users]
    assert len(phones) == len(set(phones))
    assert all(re.fullmatch(r"\+[1-9][0-9]{7,14}", p) for p in phones)


def test_hierarchy_zone_building_pool_slot_is_consistent(data: DemoData) -> None:
    zones = {z.id for z in data.zones}
    buildings = {b.id: b for b in data.buildings}
    pools = {p.id: p for p in data.pools}
    for b in data.buildings:
        assert b.zone_id in zones
    for p in data.pools:
        assert p.zone_id in zones
        if p.building_id is not None:
            assert buildings[p.building_id].zone_id == p.zone_id  # composite FK (building_id, zone_id)
    for s in data.slots:
        assert buildings[s.building_id].zone_id == s.zone_id
        pool = pools[s.pool_id]
        assert (pool.zone_id, pool.slot_type) == (s.zone_id, s.slot_type)  # composite FK (pool_id, type, zone)


def test_pool_rows_satisfy_slot_pool_scope_by_type(data: DemoData) -> None:
    for p in data.pools:
        if p.slot_type == "TH1":
            assert p.building_id is not None and p.max_open_scope in {"building", "zone"}
        elif p.slot_type == "TH2":
            assert p.max_open_scope in {"zone", "chain"} and p.investor_consent_at is not None
        else:
            assert p.slot_type == "TH3" and p.max_open_scope == "public"


def test_pools_and_slot_codes_are_unique_where_the_schema_requires(data: DemoData) -> None:
    keys = [(p.zone_id, p.building_id, p.slot_type) for p in data.pools]
    assert len(keys) == len(set(keys))
    codes = [(s.building_id, s.code) for s in data.slots]
    assert len(codes) == len(set(codes))
    assert all(re.fullmatch(r"[A-Z0-9]{1,8}", s.level_code) for s in data.slots)


def test_scenario_covers_th1_th2_th3_in_every_demo_zone_that_needs_it(data: DemoData) -> None:
    by_zone: dict = {}
    for s in data.slots:
        by_zone.setdefault(s.zone_id, set()).add(s.slot_type)
    a, b, c = (z.id for z in data.zones)
    assert by_zone[a] == {"TH1", "TH2", "TH3"}
    assert by_zone[b] == {"TH1"}
    assert by_zone[c] == {"TH2", "TH3"}


def test_holdings_match_slot_type_and_never_overlap_on_a_slot(data: DemoData) -> None:
    slots = {s.id: s for s in data.slots}
    held = [h.slot_id for h in data.holdings]
    assert len(held) == len(set(held))  # one open-ended holding per slot, else the EXCLUDE constraint fires
    for h in data.holdings:
        slot = slots[h.slot_id]
        assert (h.zone_id, h.slot_type) == (slot.zone_id, slot.slot_type)
        assert (h.slot_type, h.kind) in {("TH1", "owner"), ("TH2", "lessee")}


def test_eligibility_references_and_zone_agree(data: DemoData) -> None:
    users = {u.id: u for u in data.users}
    assets = {a.id: a for a in data.assets}
    for e in data.eligibilities:
        assert e.user_id in users and e.asset_id in assets
        assert e.zone_id == assets[e.asset_id].zone_id  # composite FK (asset_id, zone_id)
        verifier = users[e.verified_by]
        assert verifier.role == "zone_manager" and verifier.staff_zone_id == e.zone_id  # BR-18
        assert e.status == "verified"


def test_assets_belong_to_buildings_of_the_same_zone(data: DemoData) -> None:
    buildings = {b.id: b for b in data.buildings}
    for a in data.assets:
        if a.building_id is not None:
            assert buildings[a.building_id].zone_id == a.zone_id
    codes = [(a.zone_id, a.code) for a in data.assets]
    assert len(codes) == len(set(codes))


def test_overlapping_eligibilities_for_same_user_asset_role_do_not_exist(data: DemoData) -> None:
    keys = [(e.user_id, e.asset_id, e.role) for e in data.eligibilities]
    assert len(keys) == len(set(keys))


def test_ac22_tenant_lease_ended_at_end_of_yesterday_local(data: DemoData) -> None:
    tuan = next(e for e in data.eligibilities if e.user_id == data.user("tuan").id)
    assert tuan.role == "tenant"
    assert tuan.valid_to == datetime(2026, 11, 21, tzinfo=ICT)  # 00:00 today == 24:00 yesterday
    now = datetime(2026, 11, 21, 9, 0, tzinfo=ICT)
    assert tuan.valid_to <= now  # already expired during today


def test_ac22_lease_end_moves_with_today() -> None:
    later = build_demo_data(TODAY + timedelta(days=3))
    tuan = next(e for e in later.eligibilities if e.role == "tenant")
    assert tuan.valid_to == datetime(2026, 11, 24, tzinfo=ICT)


def test_lifelong_owners_have_open_ended_validity(data: DemoData) -> None:
    owners = [e for e in data.eligibilities if e.role == "owner"]
    assert owners and all(e.valid_to is None for e in owners)


def test_ac19_minh_holds_assets_in_two_zones(data: DemoData) -> None:
    minh = data.user("minh").id
    zones = {e.zone_id for e in data.eligibilities if e.user_id == minh}
    assert zones == {data.zones[0].id, data.zones[1].id}


def test_vehicles_have_masked_plates_only_in_display_field(data: DemoData) -> None:
    users = {u.id for u in data.users}
    assert len(data.vehicles) == 10
    for v in data.vehicles:
        assert v.user_id in users
        assert re.fullmatch(r"[0-9]{2}[A-Z0-9]-•••\.[0-9A-Z]{2}", v.plate_masked)
        assert v.plate not in v.plate_masked
        assert v.size_class in {"S", "M", "L", "XL"}


def test_pilot_bookings_lie_inside_the_bookable_period_of_a_foreign_window(data: DemoData) -> None:
    windows = {w.id: w for w in data.windows}
    vehicles = {v.id: v for v in data.vehicles}
    assert data.bookings
    for b in data.bookings:
        w = windows[b.window_id]
        assert w.bookable_from <= b.period_from < b.period_to <= w.bookable_to
        assert b.renter_user_id != b.provider_user_id == w.owner_user_id
        assert vehicles[b.vehicle_id].user_id == b.renter_user_id


def test_pilot_history_has_an_early_return_and_an_overstay(data: DemoData) -> None:
    windows = {w.id: w for w in data.windows}
    bookings = {b.id: b for b in data.bookings}
    c_win = windows[demo_id("share_window", "c_hist")]
    c_book = bookings[demo_id("booking", "c_hist")]
    assert c_win.returned_at is not None and c_win.period_from < c_win.returned_at < c_win.period_to
    assert c_book.period_to > c_win.returned_at  # the renter kept the slot after the owner came back
    b_book = bookings[demo_id("booking", "b_hist")]
    assert b_book.checked_out_at is not None and b_book.checked_out_at > b_book.period_to
    assert [w.returned_at for w in data.windows].count(None) == 3


def test_binh_has_two_vehicles_with_different_sizes(data: DemoData) -> None:
    binh = [v for v in data.vehicles if v.user_id == data.user("binh").id]
    assert sorted(v.size_class for v in binh) == ["M", "XL"]


def test_policy_prices_are_a_json_object_with_every_slot_type(data: DemoData) -> None:
    for pol in data.policies:
        prices = json.loads(pol.prices_json)
        assert set(prices) == {"TH1", "TH2", "TH3"}
        assert prices["TH3"]["L4"]["hour"] > prices["TH3"]["L1"]["hour"]  # guests pay more than members
        assert pol.version == 1 and pol.agreement_template_md.strip()


def test_no_secret_material_in_the_dataset(data: DemoData) -> None:
    blob = repr(data)
    assert "argon2" not in blob and "password" not in blob.lower()
