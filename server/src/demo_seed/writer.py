"""Idempotent upserts of the demo dataset, in foreign-key order.

Every statement is ``INSERT ... ON CONFLICT (id) DO UPDATE ... WHERE <something changed> RETURNING (xmax = 0)``:
the first run inserts, a re-run with unchanged data touches nothing, and a changed value in ``data.py`` is applied.
``RETURNING`` yields True (inserted), False (updated) or no row (unchanged), which feeds the report.

Parameters only (``$n``), no string-built SQL. ``consent_record`` is append-only (DB trigger), so it only ever inserts.
Passwords are written on insert and never overwritten, so a re-run cannot reset an account the team changed.

RLS (ADR-0005): the shared dev DB connects as ``parksmart_app`` (NOBYPASSRLS), and no single context may write every
table. Facility/policy/asset/eligibility tables accept only staff of the zone (``zone_manager`` + ``app.zone_ids``);
accounts, vehicles and consent evidence accept only ``system``. The seed therefore switches context per group
(transaction-local ``set_config``); share_window and booking use ``system`` scoped to the zones. A superuser/owner connection (local compose) bypasses RLS and is unaffected.
"""

from collections import Counter
from typing import Any

import asyncpg

from app.platform.crypto.plate_cipher import PlateCipher

from .data import DemoData

_ZONE = """
INSERT INTO app.zone (id, code, name) VALUES ($1, $2, $3)
ON CONFLICT (id) DO UPDATE SET code = EXCLUDED.code, name = EXCLUDED.name
WHERE (app.zone.code, app.zone.name) IS DISTINCT FROM (EXCLUDED.code, EXCLUDED.name)
RETURNING (xmax = 0)
"""

_BUILDING = """
INSERT INTO app.building (id, zone_id, subzone_code, code, name, kind)
VALUES ($1, $2, $3, $4, $5, $6::app.building_kind)
ON CONFLICT (id) DO UPDATE SET subzone_code = EXCLUDED.subzone_code, name = EXCLUDED.name, kind = EXCLUDED.kind
WHERE (app.building.subzone_code, app.building.name, app.building.kind)
      IS DISTINCT FROM (EXCLUDED.subzone_code, EXCLUDED.name, EXCLUDED.kind)
RETURNING (xmax = 0)
"""

_POOL = """
INSERT INTO app.slot_pool (id, zone_id, building_id, slot_type, max_open_scope, investor_consent_at)
VALUES ($1, $2, $3, $4::app.slot_type, $5::app.open_scope, $6)
ON CONFLICT (id) DO UPDATE SET max_open_scope = EXCLUDED.max_open_scope,
                               investor_consent_at = EXCLUDED.investor_consent_at
WHERE (app.slot_pool.max_open_scope, app.slot_pool.investor_consent_at)
      IS DISTINCT FROM (EXCLUDED.max_open_scope, EXCLUDED.investor_consent_at)
RETURNING (xmax = 0)
"""

_SLOT = """
INSERT INTO app.slot (id, zone_id, building_id, pool_id, slot_type, level_code, code, size_class)
VALUES ($1, $2, $3, $4, $5::app.slot_type, $6, $7, $8::app.size_class)
ON CONFLICT (id) DO UPDATE SET level_code = EXCLUDED.level_code, size_class = EXCLUDED.size_class
WHERE (app.slot.level_code, app.slot.size_class) IS DISTINCT FROM (EXCLUDED.level_code, EXCLUDED.size_class)
RETURNING (xmax = 0)
"""

_POLICY = """
INSERT INTO app.zone_policy (id, zone_id, version, effective_from, prices, agreement_template_md)
VALUES ($1, $2, $3, $4, $5::jsonb, $6)
ON CONFLICT (id) DO UPDATE SET effective_from = EXCLUDED.effective_from, prices = EXCLUDED.prices,
                               agreement_template_md = EXCLUDED.agreement_template_md
WHERE (app.zone_policy.effective_from, app.zone_policy.prices, app.zone_policy.agreement_template_md)
      IS DISTINCT FROM (EXCLUDED.effective_from, EXCLUDED.prices, EXCLUDED.agreement_template_md)
RETURNING (xmax = 0)
"""

_USER = """
INSERT INTO app.app_user (id, full_name, phone_e164, password_hash, role, staff_zone_id)
VALUES ($1, $2, $3, $4, $5::app.user_role, $6)
ON CONFLICT (id) DO UPDATE SET full_name = EXCLUDED.full_name, phone_e164 = EXCLUDED.phone_e164,
                               role = EXCLUDED.role, staff_zone_id = EXCLUDED.staff_zone_id
WHERE (app.app_user.full_name, app.app_user.phone_e164, app.app_user.role, app.app_user.staff_zone_id)
      IS DISTINCT FROM (EXCLUDED.full_name, EXCLUDED.phone_e164, EXCLUDED.role, EXCLUDED.staff_zone_id)
RETURNING (xmax = 0)
"""

_CONSENT = """
INSERT INTO app.consent_record (user_id, zone_id, action, subject_type, subject_id, terms_version, decision, evidence)
VALUES ($1, NULL, 'registration_terms', 'app_user', $1, 'v1', 'accepted', '{"channel": "app"}'::jsonb)
ON CONFLICT ON CONSTRAINT consent_record_natural_uq DO NOTHING
RETURNING true
"""

_ASSET = """
INSERT INTO app.asset (id, zone_id, building_id, kind, code)
VALUES ($1, $2, $3, $4::app.asset_kind, $5)
ON CONFLICT (id) DO UPDATE SET kind = EXCLUDED.kind
WHERE app.asset.kind IS DISTINCT FROM EXCLUDED.kind
RETURNING (xmax = 0)
"""

_ELIGIBILITY = """
INSERT INTO app.eligibility (id, user_id, asset_id, zone_id, role, valid_during, status, verified_by, verified_at)
VALUES ($1, $2, $3, $4, $5::app.eligibility_role, tstzrange($6::timestamptz, $7::timestamptz),
        $8::app.eligibility_status, $9, now())
ON CONFLICT (id) DO UPDATE SET valid_during = EXCLUDED.valid_during, status = EXCLUDED.status,
                               verified_by = EXCLUDED.verified_by
WHERE (app.eligibility.valid_during, app.eligibility.status, app.eligibility.verified_by)
      IS DISTINCT FROM (EXCLUDED.valid_during, EXCLUDED.status, EXCLUDED.verified_by)
RETURNING (xmax = 0)
"""

_HOLDING = """
INSERT INTO app.slot_holding (id, zone_id, slot_id, slot_type, user_id, kind, held_during)
VALUES ($1, $2, $3, $4::app.slot_type, $5, $6::app.holding_kind, tstzrange($7::timestamptz, NULL))
ON CONFLICT (id) DO UPDATE SET held_during = EXCLUDED.held_during, kind = EXCLUDED.kind
WHERE (app.slot_holding.held_during, app.slot_holding.kind)
      IS DISTINCT FROM (EXCLUDED.held_during, EXCLUDED.kind)
RETURNING (xmax = 0)
"""

# parksmart_app may write but not read plate_ciphertext (column-level GRANT, schema section 20). PostgreSQL also demands
# SELECT on every column an ON CONFLICT DO UPDATE reads through EXCLUDED, so a vehicle is an INSERT ... DO NOTHING
# followed, for an existing row, by a plain UPDATE whose WHERE only reads granted columns. The ciphertext is therefore
# rewritten (fresh nonce, same plate) only when the plate hash, key version, mask, size or active flag differ.
_VEHICLE_INSERT = """
INSERT INTO app.vehicle (id, user_id, plate_ciphertext, plate_key_version, plate_hash, plate_masked, size_class)
VALUES ($1, $2, $3, $4, $5, $6, $7::app.size_class)
ON CONFLICT (id) DO NOTHING
RETURNING true
"""

_VEHICLE_UPDATE = """
UPDATE app.vehicle SET plate_ciphertext = $2, plate_key_version = $3, plate_hash = $4, plate_masked = $5,
                       size_class = $6::app.size_class, is_active = true
WHERE id = $1
  AND (plate_hash, plate_key_version, plate_masked, size_class, is_active)
      IS DISTINCT FROM ($4::bytea, $3::smallint, $5::text, $6::app.size_class, true)
RETURNING false
"""

# A moved window is reopened: the booking guard needs it open to re-check the booking, and _WINDOW_CLOSE closes it again.
# Otherwise status is left alone: a window that moved on (expired, cancelled) keeps its state on a same-day re-run.
_WINDOW = """
INSERT INTO app.share_window (id, zone_id, slot_id, owner_user_id, period, bookable_period, open_scope, idempotency_key,
                              owner_otp_confirmed_at, expires_at)
VALUES ($1, $2, $3, $4, tstzrange($5::timestamptz, $6::timestamptz), tstzrange($7::timestamptz, $8::timestamptz),
        $9::app.open_scope, $10, $11::timestamptz, $12::timestamptz)
ON CONFLICT (id) DO UPDATE SET period = EXCLUDED.period, bookable_period = EXCLUDED.bookable_period,
                               open_scope = EXCLUDED.open_scope, owner_otp_confirmed_at = EXCLUDED.owner_otp_confirmed_at,
                               expires_at = EXCLUDED.expires_at, status = 'open', returned_at = NULL
WHERE (app.share_window.period, app.share_window.bookable_period, app.share_window.open_scope,
       app.share_window.owner_otp_confirmed_at, app.share_window.expires_at)
      IS DISTINCT FROM (EXCLUDED.period, EXCLUDED.bookable_period, EXCLUDED.open_scope,
                        EXCLUDED.owner_otp_confirmed_at, EXCLUDED.expires_at)
RETURNING (xmax = 0)
"""

# The booking guard trigger (BEFORE INSERT) also fires for an ON CONFLICT row and needs an *open* window, which a re-run
# may no longer find; so an existing booking is never offered to INSERT, only UPDATEd when a value changed.
# Owner came home early (v5: status closed_early + returned_at). After the bookings: the guard needs an open window.
_WINDOW_CLOSE = """
UPDATE app.share_window SET status = 'closed_early', returned_at = $2::timestamptz
WHERE id = $1 AND (status, returned_at) IS DISTINCT FROM ('closed_early'::app.share_status, $2::timestamptz)
RETURNING false
"""

_BOOKING_INSERT = """
INSERT INTO app.booking (id, zone_id, slot_id, share_window_id, provider_user_id, renter_user_id, vehicle_id, period,
                         eligibility_level, price_vnd, status, checked_in_at, checked_out_at, idempotency_key)
SELECT $1::uuid, $2::uuid, $3::uuid, $4::uuid, $5::uuid, $6::uuid, $7::uuid,
       tstzrange($8::timestamptz, $9::timestamptz), $10::app.eligibility_level, $11::bigint, $12::app.booking_status,
       $13::timestamptz, $14::timestamptz, $15::text
WHERE NOT EXISTS (SELECT 1 FROM app.booking WHERE id = $1::uuid)
RETURNING true
"""

_BOOKING_UPDATE = """
UPDATE app.booking SET period = tstzrange($2::timestamptz, $3::timestamptz), price_vnd = $4::bigint,
                       status = $5::app.booking_status, checked_in_at = $6::timestamptz,
                       checked_out_at = $7::timestamptz
WHERE id = $1
  AND (period, price_vnd, status, checked_in_at, checked_out_at)
      IS DISTINCT FROM (tstzrange($2::timestamptz, $3::timestamptz), $4::bigint, $5::app.booking_status,
                        $6::timestamptz, $7::timestamptz)
RETURNING false
"""

Report = dict[str, Counter[str]]


async def _as_zone_staff(conn: asyncpg.Connection, data: DemoData) -> None:
    """Act as the BQL of all three zones: required by the write policies of building, slot, pool, policy, asset..."""
    zones = "{" + ",".join(str(z.id) for z in data.zones) + "}"
    await conn.execute(
        "SELECT set_config('app.role', 'zone_manager', true), set_config('app.zone_ids', $1, true)", zones
    )


async def _as_system(conn: asyncpg.Connection) -> None:
    """Act as a system job: required by app_user, vehicle and consent_record."""
    await conn.execute("SELECT set_config('app.role', 'system', true)")


async def _as_system_in_zones(conn: asyncpg.Connection, data: DemoData) -> None:
    """System role scoped to the three zones: share_window / booking policies accept it, and the booking guard trigger
    can then read the renter's vehicle (a BQL cannot until a booking exists)."""
    zones = "{" + ",".join(str(z.id) for z in data.zones) + "}"
    await conn.execute("SELECT set_config('app.role', 'system', true), set_config('app.zone_ids', $1, true)", zones)


async def _run(conn: asyncpg.Connection, report: Report, table: str, sql: str, *args: Any) -> None:
    outcome = await conn.fetchval(sql, *args)
    # True = inserted, False = updated, None = no row returned (unchanged / conflict ignored)
    report.setdefault(table, Counter())[
        "inserted" if outcome is True else "updated" if outcome is False else "unchanged"
    ] += 1


async def write_demo_data(conn: asyncpg.Connection, data: DemoData, cipher: PlateCipher, password_hash: str) -> Report:
    """Write everything inside the caller's transaction (``set_config(..., true)`` is transaction-local)."""
    report: Report = {}

    await _as_system(conn)
    for z in data.zones:
        await _run(conn, report, "zone", _ZONE, z.id, z.code, z.name)
    await _as_zone_staff(conn, data)
    for b in data.buildings:
        await _run(conn, report, "building", _BUILDING, b.id, b.zone_id, b.subzone_code, b.code, b.name, b.kind)
    for p in data.pools:
        await _run(
            conn, report, "slot_pool", _POOL, p.id, p.zone_id, p.building_id, p.slot_type, p.max_open_scope,
            p.investor_consent_at,
        )  # fmt: skip
    for s in data.slots:
        await _run(
            conn, report, "slot", _SLOT, s.id, s.zone_id, s.building_id, s.pool_id, s.slot_type, s.level_code, s.code,
            s.size_class,
        )  # fmt: skip
    for pol in data.policies:
        await _run(
            conn, report, "zone_policy", _POLICY, pol.id, pol.zone_id, pol.version, pol.effective_from,
            pol.prices_json, pol.agreement_template_md,
        )  # fmt: skip
    await _as_system(conn)
    for u in data.users:
        await _run(
            conn, report, "app_user", _USER, u.id, u.full_name, u.phone_e164, password_hash, u.role, u.staff_zone_id
        )
    for u in data.users:
        await _run(conn, report, "consent_record", _CONSENT, u.id)
    await _as_zone_staff(conn, data)
    for a in data.assets:
        await _run(conn, report, "asset", _ASSET, a.id, a.zone_id, a.building_id, a.kind, a.code)
    for e in data.eligibilities:
        await _run(
            conn, report, "eligibility", _ELIGIBILITY, e.id, e.user_id, e.asset_id, e.zone_id, e.role, e.valid_from,
            e.valid_to, e.status, e.verified_by,
        )  # fmt: skip
    for h in data.holdings:
        await _run(
            conn, report, "slot_holding", _HOLDING, h.id, h.zone_id, h.slot_id, h.slot_type, h.user_id, h.kind,
            h.held_from,
        )  # fmt: skip
    await _as_system(conn)
    for v in data.vehicles:
        args = (
            v.id, v.user_id, cipher.encrypt(v.plate), cipher.key_version, cipher.blind_index(v.plate),
            v.plate_masked, v.size_class,
        )  # fmt: skip
        if await conn.fetchval(_VEHICLE_INSERT, *args):
            report.setdefault("vehicle", Counter())["inserted"] += 1
        else:
            await _run(conn, report, "vehicle", _VEHICLE_UPDATE, args[0], *args[2:])
    await _as_system_in_zones(conn, data)
    window_outcomes = [
        await conn.fetchval(
            _WINDOW, w.id, w.zone_id, w.slot_id, w.owner_user_id, w.period_from, w.period_to, w.bookable_from,
            w.bookable_to, w.open_scope, w.idempotency_key, w.otp_confirmed_at, w.expires_at,
        )
        for w in data.windows
    ]  # fmt: skip
    counts = report.setdefault("share_window", Counter())  # keeps the report order: counted after the bookings
    for bk in data.bookings:
        bargs = (
            bk.id, bk.zone_id, bk.slot_id, bk.window_id, bk.provider_user_id, bk.renter_user_id, bk.vehicle_id, bk.period_from,
            bk.period_to, bk.eligibility_level, bk.price_vnd, bk.status, bk.checked_in_at, bk.checked_out_at,
            bk.idempotency_key,
        )  # fmt: skip
        if await conn.fetchval(_BOOKING_INSERT, *bargs):
            report.setdefault("booking", Counter())["inserted"] += 1
        else:
            await _run(conn, report, "booking", _BOOKING_UPDATE, bk.id, *bargs[7:9], *bargs[10:14])
    for w, outcome in zip(data.windows, window_outcomes, strict=True):
        if w.returned_at is not None and await conn.fetchval(_WINDOW_CLOSE, w.id, w.returned_at) is False:
            outcome = outcome or False  # closed now: an update, unless the row was just inserted
        counts["inserted" if outcome is True else "updated" if outcome is False else "unchanged"] += 1
    return report
