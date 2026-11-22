"""Demo seed against a real Postgres that already has the schema (migrations, or docs/03-design/sql/schema.sql).

Needs ``TEST_DATABASE_URL`` pointing at a scratch database; skipped otherwise, so ``make check`` stays offline.
Every test runs in a transaction that is rolled back, so the database stays empty (consent_record is append-only
and cannot be cleaned up any other way). The database must hold no demo rows when the tests start.
"""

import base64
import os
from collections.abc import AsyncIterator
from datetime import datetime

import asyncpg
import pytest
import pytest_asyncio
from argon2 import PasswordHasher

from app.facility.domain.plate import normalize
from app.platform.config.settings import Settings
from app.platform.crypto.plate_cipher import PlateCipher
from demo_seed import __main__ as seed_main
from demo_seed.data import ICT, build_demo_data
from demo_seed.ids import demo_id
from demo_seed.lpr_csv import UNKNOWN_PLATES, build_rows
from demo_seed.writer import write_demo_data

pytestmark = pytest.mark.integration

DSN = os.environ.get("TEST_DATABASE_URL", "")
if not DSN:
    pytest.skip("TEST_DATABASE_URL not set", allow_module_level=True)

EXPECTED_ROWS = {
    "zone": 3,
    "building": 6,
    "slot_pool": 6,
    "slot": 10,
    "zone_policy": 3,
    "app_user": 15,
    "consent_record": 15,
    "asset": 10,
    "eligibility": 10,
    "slot_holding": 6,
    "vehicle": 10,
    "share_window": 4,
    "booking": 3,
}


@pytest.fixture(scope="module")
def cipher() -> PlateCipher:
    return PlateCipher(enc_key=os.urandom(32), hash_key=os.urandom(32), key_version=1)


@pytest.fixture(scope="module")
def password_hash() -> str:
    return PasswordHasher().hash("test-password")


@pytest_asyncio.fixture
async def conn() -> AsyncIterator[asyncpg.Connection]:
    """A connection inside a transaction that is always rolled back."""
    c = await asyncpg.connect(DSN)
    tx = c.transaction()
    await tx.start()
    try:
        if await c.fetchval("SELECT count(*) FROM app.zone WHERE code IN ('A', 'B', 'C')"):
            pytest.skip("database already holds demo zones; point TEST_DATABASE_URL at an empty scratch database")
        yield c
    finally:
        await tx.rollback()
        await c.close()


def _totals(report: dict, key: str) -> dict[str, int]:
    return {table: counts[key] for table, counts in report.items()}


async def test_first_run_inserts_every_row(conn, cipher, password_hash) -> None:
    report = await write_demo_data(conn, build_demo_data(), cipher, password_hash)
    assert _totals(report, "inserted") == EXPECTED_ROWS
    assert not any(counts["updated"] or counts["unchanged"] for counts in report.values())
    for table in EXPECTED_ROWS:
        assert await conn.fetchval(f"SELECT count(*) FROM app.{table}") == EXPECTED_ROWS[table]  # noqa: S608


async def test_second_run_changes_nothing(conn, cipher, password_hash) -> None:
    data = build_demo_data()
    await write_demo_data(conn, data, cipher, password_hash)
    ciphertexts = {
        r["id"]: r["plate_ciphertext"] for r in await conn.fetch("SELECT id, plate_ciphertext FROM app.vehicle")
    }

    report = await write_demo_data(conn, data, cipher, password_hash)

    assert _totals(report, "unchanged") == EXPECTED_ROWS  # includes consent_record: ON CONFLICT DO NOTHING
    assert not any(counts["inserted"] or counts["updated"] for counts in report.values())
    for row in await conn.fetch("SELECT id, plate_ciphertext FROM app.vehicle"):
        assert row["plate_ciphertext"] == ciphertexts[row["id"]]  # random-nonce ciphertext is not rewritten


async def test_drifted_row_is_repaired_and_reported_as_updated(conn, cipher, password_hash) -> None:
    data = build_demo_data()
    await write_demo_data(conn, data, cipher, password_hash)
    slot = data.slots[0]
    await conn.execute("UPDATE app.slot SET size_class = 'XL' WHERE id = $1", slot.id)
    await conn.execute("UPDATE app.zone SET name = 'renamed' WHERE code = 'B'")

    report = await write_demo_data(conn, data, cipher, password_hash)

    assert report["slot"]["updated"] == 1 and report["slot"]["unchanged"] == EXPECTED_ROWS["slot"] - 1
    assert report["zone"]["updated"] == 1
    assert await conn.fetchval("SELECT size_class::text FROM app.slot WHERE id = $1", slot.id) == slot.size_class
    assert await conn.fetchval("SELECT name FROM app.zone WHERE code = 'B'") == "Khu B"


async def test_plates_are_encrypted_hashed_and_masked(conn, cipher, password_hash) -> None:
    data = build_demo_data()
    await write_demo_data(conn, data, cipher, password_hash)
    for v in data.vehicles:
        row = await conn.fetchrow("SELECT * FROM app.vehicle WHERE id = $1", v.id)
        assert row is not None
        assert bytes(row["plate_hash"]) == cipher.blind_index(v.plate)
        assert len(row["plate_hash"]) == 32
        assert cipher.decrypt(bytes(row["plate_ciphertext"])) == v.plate
        assert v.plate.encode() not in bytes(row["plate_ciphertext"])
        assert row["plate_masked"] == v.plate_masked
        assert row["plate_key_version"] == cipher.key_version and row["is_active"] is True


async def test_vehicle_is_found_by_blind_index_of_any_plate_spelling(conn, cipher, password_hash) -> None:
    data = build_demo_data()
    await write_demo_data(conn, data, cipher, password_hash)
    # What the LPR matcher (N1) will do: normalize the OCR text, hash, look up.
    for spelling in ("30a-123.45", "30A 123 45", "30A12345"):
        found = await conn.fetchval(
            "SELECT user_id FROM app.vehicle WHERE plate_hash = $1", cipher.blind_index(normalize(spelling))
        )
        assert found == data.user("lan").id


async def test_rotating_the_plate_key_version_rewrites_ciphertext(conn, cipher, password_hash) -> None:
    data = build_demo_data()
    await write_demo_data(conn, data, cipher, password_hash)
    v2 = PlateCipher(cipher.enc_key, cipher.hash_key, key_version=2)

    report = await write_demo_data(conn, data, v2, password_hash)

    assert report["vehicle"]["updated"] == EXPECTED_ROWS["vehicle"]
    blob = await conn.fetchval("SELECT plate_ciphertext FROM app.vehicle WHERE id = $1", data.vehicles[0].id)
    assert v2.decrypt(bytes(blob)) == data.vehicles[0].plate


async def test_passwords_are_argon2id_and_not_overwritten_on_rerun(conn, cipher, password_hash) -> None:
    data = build_demo_data()
    await write_demo_data(conn, data, cipher, password_hash)
    stored = await conn.fetchval("SELECT password_hash FROM app.app_user WHERE id = $1", data.user("lan").id)
    assert stored.startswith("$argon2id$")
    assert PasswordHasher().verify(stored, "test-password")

    await write_demo_data(conn, data, cipher, PasswordHasher().hash("someone-changed-seed-password"))

    again = await conn.fetchval("SELECT password_hash FROM app.app_user WHERE id = $1", data.user("lan").id)
    assert again == stored


async def test_registration_consent_is_one_row_per_user_and_append_only(conn, cipher, password_hash) -> None:
    data = build_demo_data()
    await write_demo_data(conn, data, cipher, password_hash)
    await write_demo_data(conn, data, cipher, password_hash)
    rows = await conn.fetch("SELECT user_id, action::text, decision::text, zone_id FROM app.consent_record")
    assert len(rows) == len(data.users)
    assert {r["user_id"] for r in rows} == {u.id for u in data.users}
    assert all(
        r["action"] == "registration_terms" and r["decision"] == "accepted" and r["zone_id"] is None for r in rows
    )
    sp = conn.transaction()
    await sp.start()
    with pytest.raises(asyncpg.PostgresError):
        await conn.execute("UPDATE app.consent_record SET terms_version = 'v2'")
    await sp.rollback()


async def test_ac22_tenant_eligibility_range_ends_at_local_midnight(conn, cipher, password_hash) -> None:
    data = build_demo_data()
    await write_demo_data(conn, data, cipher, password_hash)
    upper = await conn.fetchval(
        "SELECT upper(valid_during) FROM app.eligibility WHERE id = $1",
        next(e.id for e in data.eligibilities if e.role == "tenant"),
    )
    assert upper.astimezone(ICT).time() == datetime.min.time()
    owner_upper_inf = await conn.fetchval(
        "SELECT upper_inf(valid_during) FROM app.eligibility WHERE id = $1",
        demo_id("eligibility", "lan", "lan", "owner"),
    )
    assert owner_upper_inf is True


async def test_seed_works_as_the_non_owner_app_role_with_rls_enforced(conn, cipher, password_hash) -> None:
    """The shared dev DB connects as parksmart_app (NOBYPASSRLS): the per-group RLS contexts must be enough to write."""
    if not await conn.fetchval("SELECT 1 FROM pg_roles WHERE rolname = 'parksmart_app'"):
        pytest.skip("role parksmart_app not present")
    await conn.execute("SET LOCAL ROLE parksmart_app")
    report = await write_demo_data(conn, build_demo_data(), cipher, password_hash)
    assert _totals(report, "inserted") == EXPECTED_ROWS
    await conn.execute("RESET ROLE")


async def test_without_a_zone_context_rls_blocks_facility_writes(conn) -> None:
    """Proves the test above is meaningful: as parksmart_app with no app.role / app.zone_ids a building is rejected."""
    if not await conn.fetchval("SELECT 1 FROM pg_roles WHERE rolname = 'parksmart_app'"):
        pytest.skip("role parksmart_app not present")
    zone_id = await conn.fetchval("INSERT INTO app.zone (code, name) VALUES ('Z', 'rls probe') RETURNING id")
    await conn.execute("SET LOCAL ROLE parksmart_app")
    sp = conn.transaction()
    await sp.start()
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await conn.execute(
            "INSERT INTO app.building (zone_id, code, name, kind) VALUES ($1, 'X', 'probe', 'public_lot')", zone_id
        )
    await sp.rollback()
    await conn.execute("RESET ROLE")


async def test_dry_run_reports_counts_and_leaves_no_rows(monkeypatch, capsys, cipher) -> None:
    settings = Settings(
        _env_file=None,
        database_url=DSN,
        seed_demo=True,
        seed_demo_password="pw-for-dry-run",
        plate_enc_key=_b64(cipher.enc_key),
        plate_hash_key=_b64(cipher.hash_key),
    )
    monkeypatch.setattr(seed_main, "get_settings", lambda: settings)
    probe = await asyncpg.connect(DSN)
    try:
        if await probe.fetchval("SELECT count(*) FROM app.zone WHERE code IN ('A', 'B', 'C')"):
            pytest.skip("database already holds demo zones")
        code = await seed_main.run(dry_run=True)
        assert code == 0
        assert await probe.fetchval("SELECT count(*) FROM app.zone") == 0
        assert await probe.fetchval("SELECT count(*) FROM app.consent_record") == 0
    finally:
        await probe.close()
    out = capsys.readouterr().out
    assert "dry run" in out and "inserted=3" in out and "vehicle" in out
    assert "pw-for-dry-run" not in out and "30A" not in out  # no secrets or plates in the output


async def test_pilot_windows_and_gate_log_plates_resolve_in_the_database(conn, cipher, password_hash) -> None:
    data = build_demo_data()
    await write_demo_data(conn, data, cipher, password_hash)
    status = {
        r["id"]: (r["status"], r["returned_at"])
        for r in await conn.fetch("SELECT id, status::text, returned_at FROM app.share_window")
    }
    c_hist = status[demo_id("share_window", "c_hist")]
    assert c_hist[0] == "closed_early" and c_hist[1] is not None
    assert [s for k, (s, _) in status.items() if k != demo_id("share_window", "c_hist")] == ["open"] * 3

    sql = "SELECT count(*) FROM app.vehicle WHERE plate_hash = $1 AND is_active"
    seeded = {v.plate for v in data.vehicles}
    for row in build_rows(data.demo_day):
        text = row["plate_text"]
        if not text:
            continue
        found = await conn.fetchval(sql, cipher.blind_index(normalize(text)))
        assert found == (0 if text in UNKNOWN_PLATES else 1), text
        assert (normalize(text) in seeded) == (text not in UNKNOWN_PLATES)


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode()
