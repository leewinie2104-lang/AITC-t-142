"""DSN được che mật khẩu trước khi ghi log (không có secret trong log)."""

import pytest

from app.platform.db.session import redact_dsn


@pytest.mark.parametrize(
    ("dsn", "expected"),
    [
        pytest.param(
            "postgresql://parksmart_app:s3cret@parksmart-ci-runner:15432/parksmart",
            "postgresql://parksmart_app:***@parksmart-ci-runner:15432/parksmart",
            id="user-password-port",
        ),
        pytest.param(
            "postgresql://u:p%40ss@db.example.com/app?sslmode=require",
            "postgresql://u:***@db.example.com/app?sslmode=require",
            id="encoded-password-query-kept",
        ),
        pytest.param(
            "postgresql://localhost:5432/parksmart",
            "postgresql://localhost:5432/parksmart",
            id="no-password-unchanged",
        ),
    ],
)
def test_redact_dsn_hides_password(dsn: str, expected: str) -> None:
    assert redact_dsn(dsn) == expected
