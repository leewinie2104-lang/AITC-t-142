"""Idempotent upserts of the demo dataset, in foreign-key order.

Every statement is ``INSERT ... ON CONFLICT (id) DO UPDATE ... WHERE <something changed> RETURNING (xmax = 0)``:
the first run inserts, a re-run with unchanged data touches nothing, and a changed value in ``data.py`` is applied.
``RETURNING`` yields True (inserted), False (updated) or no row (unchanged), which feeds the report.

Parameters only (``$n``), no string-built SQL. ``consent_record`` is append-only (DB trigger), so it only ever inserts.
Passwords are written on insert and never overwritten, so a re-run cannot reset an account the team changed.

RLS (ADR-0005): the shared dev DB connects as ``parksmart_app`` (NOBYPASSRLS), and no single context may write every
table. Facility/policy/asset/eligibility tables accept only staff of the zone (``zone_manager`` + ``app.zone_ids``);
accounts, vehicles and consent evidence accept only ``system``. The seed therefore switches context per group
(transaction-local ``set_config``). A superuser/owner connection (local compose) bypasses RLS and is unaffected.
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
    return report
