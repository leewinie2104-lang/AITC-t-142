"""Guards of the seed entry point: it must refuse to run unless explicitly enabled and fully configured."""

import base64
import os
from unittest.mock import AsyncMock

import pytest

from app.platform.config.settings import Settings
from demo_seed import __main__ as seed_main


def _key() -> str:
    return base64.b64encode(os.urandom(32)).decode()


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "seed_demo": True,
        "seed_demo_password": "pw",
        "plate_enc_key": _key(),
        "plate_hash_key": _key(),
    }
    return Settings(_env_file=None, **{**base, **overrides})


@pytest.fixture
def connect(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Any attempt to open a database connection is a test failure in the guard tests."""
    mock = AsyncMock(side_effect=AssertionError("the seed must not connect to the database here"))
    monkeypatch.setattr(seed_main.asyncpg, "connect", mock)
    return mock


async def test_skips_without_seed_demo_flag(monkeypatch, capsys, connect) -> None:
    monkeypatch.setattr(seed_main, "get_settings", lambda: _settings(seed_demo=False))
    assert await seed_main.run(dry_run=False) == 0
    assert "skipped" in capsys.readouterr().out
    connect.assert_not_called()


@pytest.mark.parametrize("seed_demo", [True, False])
async def test_refuses_in_production_even_with_flag(monkeypatch, capsys, connect, seed_demo: bool) -> None:
    monkeypatch.setattr(seed_main, "get_settings", lambda: _settings(app_env="production", seed_demo=seed_demo))
    assert await seed_main.run(dry_run=False) == 2
    assert "APP_ENV=production" in capsys.readouterr().err
    connect.assert_not_called()


async def test_refuses_without_password(monkeypatch, capsys, connect) -> None:
    monkeypatch.setattr(seed_main, "get_settings", lambda: _settings(seed_demo_password=""))
    assert await seed_main.run(dry_run=False) == 2
    assert "SEED_DEMO_PASSWORD" in capsys.readouterr().err
    connect.assert_not_called()


@pytest.mark.parametrize("missing", ["plate_enc_key", "plate_hash_key"])
async def test_refuses_without_plate_keys(monkeypatch, capsys, connect, missing: str) -> None:
    monkeypatch.setattr(seed_main, "get_settings", lambda: _settings(**{missing: ""}))
    assert await seed_main.run(dry_run=False) == 2
    assert "plate keys" in capsys.readouterr().err
    connect.assert_not_called()


async def test_refuses_keys_that_are_not_valid_base64(monkeypatch, capsys, connect) -> None:
    monkeypatch.setattr(seed_main, "get_settings", lambda: _settings(plate_enc_key="%%%not-base64%%%"))
    assert await seed_main.run(dry_run=False) == 2
    err = capsys.readouterr().err
    assert "PLATE_ENC_KEY" in err and "%%%" not in err
    connect.assert_not_called()


def test_report_lines_contain_only_counts(capsys) -> None:
    from collections import Counter

    seed_main._print_report({"zone": Counter(inserted=3), "vehicle": Counter(unchanged=7)})
    out = capsys.readouterr().out
    assert "zone" in out and "inserted=3" in out and "unchanged=7" in out


class _FakeTransaction:
    async def __aenter__(self) -> None:
        return None

    async def __aexit__(self, *exc: object) -> bool:
        return False


class _FakeConn:
    closed = False

    def transaction(self) -> _FakeTransaction:
        return _FakeTransaction()

    async def close(self) -> None:
        self.closed = True


async def test_missing_schema_gives_an_actionable_message_and_closes_the_connection(monkeypatch, capsys) -> None:
    import asyncpg

    conn = _FakeConn()
    monkeypatch.setattr(seed_main, "get_settings", lambda: _settings())
    monkeypatch.setattr(seed_main.asyncpg, "connect", AsyncMock(return_value=conn))
    monkeypatch.setattr(seed_main, "write_demo_data", AsyncMock(side_effect=asyncpg.UndefinedTableError("no table")))

    assert await seed_main.run(dry_run=False) == 1

    assert "alembic upgrade head" in capsys.readouterr().err
    assert conn.closed is True


async def test_dsn_password_is_redacted_in_output(monkeypatch, capsys) -> None:
    conn = _FakeConn()
    monkeypatch.setattr(
        seed_main, "get_settings", lambda: _settings(database_url="postgresql://u:hunter2@db.example:5432/x")
    )
    monkeypatch.setattr(seed_main.asyncpg, "connect", AsyncMock(return_value=conn))
    monkeypatch.setattr(seed_main, "write_demo_data", AsyncMock(return_value={}))

    assert await seed_main.run(dry_run=False) == 0

    out = capsys.readouterr().out
    assert "hunter2" not in out and "u:***@db.example" in out
