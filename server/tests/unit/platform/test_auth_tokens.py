"""Access JWT (ADR-0006): round trip, rejection of forged / expired tokens, key loading."""

import base64
import hashlib
import hmac
import json
import time
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.platform.auth.tokens import ISSUER, TokenError, TokenService
from app.platform.config.settings import Settings


def _pem_pair() -> tuple[str, str]:
    key = ec.generate_private_key(ec.SECP256R1())
    private = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    public = (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    return private, public


@pytest.fixture(scope="module")
def keys() -> tuple[str, str]:
    return _pem_pair()


@pytest.fixture
def service(keys: tuple[str, str]) -> TokenService:
    return TokenService(keys[0], keys[1], ttl_minutes=15)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def test_issue_then_verify_round_trips_claims(service: TokenService) -> None:
    user_id, zone = uuid4(), uuid4()
    token, expires_in = service.issue(user_id, "bql_staff", [zone])

    claims = service.verify(token)

    assert expires_in == 15 * 60
    assert claims["sub"] == str(user_id)
    assert claims["role"] == "bql_staff"
    assert claims["zone_ids"] == [str(zone)]
    assert claims["iss"] == ISSUER


def test_token_expired_beyond_leeway_is_rejected(service: TokenService, monkeypatch: pytest.MonkeyPatch) -> None:
    real_time = time.time
    with monkeypatch.context() as m:
        m.setattr("app.platform.auth.tokens.time.time", lambda: real_time() - 3600)
        token, _ = service.issue(uuid4(), "resident", [])

    with pytest.raises(TokenError):
        service.verify(token)


def test_tampered_payload_is_rejected(service: TokenService) -> None:
    token, _ = service.issue(uuid4(), "resident", [])
    header, payload, sig = token.split(".")
    flipped = ("A" if payload[5] != "A" else "B").join([payload[:5], payload[6:]])

    with pytest.raises(TokenError):
        service.verify(f"{header}.{flipped}.{sig}")


def test_token_signed_by_another_key_pair_is_rejected(service: TokenService) -> None:
    other_private, other_public = _pem_pair()
    token, _ = TokenService(other_private, other_public, ttl_minutes=15).issue(uuid4(), "resident", [])

    with pytest.raises(TokenError):
        service.verify(token)


def test_hs256_token_signed_with_public_key_is_rejected_key_confusion(keys: tuple[str, str]) -> None:
    _, public = keys
    header = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    now = int(time.time())
    payload = _b64(
        json.dumps({"sub": str(uuid4()), "role": "admin", "iss": ISSUER, "exp": now + 600, "zone_ids": []}).encode()
    )
    signing_input = f"{header}.{payload}".encode()
    sig = _b64(hmac.new(public.encode(), signing_input, hashlib.sha256).digest())

    with pytest.raises(TokenError):
        TokenService(keys[0], public, ttl_minutes=15).verify(f"{header}.{payload}.{sig}")


def test_from_settings_requires_keys_in_production() -> None:
    settings = Settings(_env_file=None, app_env="production")

    with pytest.raises(RuntimeError):
        TokenService.from_settings(settings)


def test_from_settings_loads_pem_with_literal_backslash_n(keys: tuple[str, str]) -> None:
    private, public = keys
    settings = Settings(
        _env_file=None,
        app_env="test",
        jwt_private_key=private.strip().replace("\n", "\\n"),
        jwt_public_key=public.strip().replace("\n", "\\n"),
    )
    assert "\n" not in settings.jwt_private_key

    service = TokenService.from_settings(settings)
    user_id = uuid4()
    token, _ = service.issue(user_id, "resident", [])

    assert service.verify(token)["sub"] == str(user_id)
    # The token verifies with the original, properly formatted public key: the keys really were parsed.
    assert TokenService(private, public, 15).verify(token)["sub"] == str(user_id)
