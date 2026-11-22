"""Sign and verify the self-issued access JWT (ADR-0006): ES256, no refresh token, not revocable."""

import logging
import time
from uuid import UUID, uuid4

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.platform.config.settings import Settings

logger = logging.getLogger(__name__)

ISSUER = "parksmart"
_ALGORITHM = "ES256"
_LEEWAY_SECONDS = 30  # clock skew between api instances

_ephemeral_keys: tuple[str, str] | None = None


class TokenError(Exception):
    """The token is missing a claim, expired, or fails signature / issuer checks."""


def _ephemeral_key_pair() -> tuple[str, str]:
    """One P-256 pair per process, so every TokenService in it signs and verifies with the same keys."""
    global _ephemeral_keys
    if _ephemeral_keys is None:
        key = ec.generate_private_key(ec.SECP256R1())
        _ephemeral_keys = (
            key.private_bytes(
                serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
            ).decode(),
            key.public_key()
            .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
            .decode(),
        )
        logger.warning("JWT keys not configured: using an ephemeral key pair, tokens die on restart")
    return _ephemeral_keys


class TokenService:
    def __init__(self, private_key: str, public_key: str, ttl_minutes: int) -> None:
        self._private_key = private_key
        self._public_key = public_key
        self._ttl_seconds = ttl_minutes * 60

    @classmethod
    def from_settings(cls, settings: Settings) -> "TokenService":
        # Env files hold the PEM on one line with literal backslash-n separators.
        private_key = settings.jwt_private_key.replace("\\n", "\n")
        public_key = settings.jwt_public_key.replace("\\n", "\n")
        if not (private_key and public_key):
            # Test shares the development fallback so create_app(Settings(app_env="test")) works without keys.
            if settings.app_env == "production":
                raise RuntimeError("JWT_PRIVATE_KEY and JWT_PUBLIC_KEY are required in production")
            private_key, public_key = _ephemeral_key_pair()
        return cls(private_key, public_key, settings.jwt_ttl_minutes)

    def issue(self, user_id: UUID, role: str, zone_ids: list[UUID]) -> tuple[str, int]:
        """Return (token, expires_in seconds)."""
        now = int(time.time())
        claims = {
            "sub": str(user_id),
            "role": role,
            "zone_ids": [str(z) for z in zone_ids],
            "jti": str(uuid4()),
            "iat": now,
            "exp": now + self._ttl_seconds,
            "iss": ISSUER,
        }
        return jwt.encode(claims, self._private_key, algorithm=_ALGORITHM), self._ttl_seconds

    def verify(self, token: str) -> dict[str, object]:
        try:
            return jwt.decode(
                token,
                self._public_key,
                algorithms=[_ALGORITHM],  # pinned: no "none" / HS256 key confusion
                issuer=ISSUER,
                leeway=_LEEWAY_SECONDS,
                options={"require": ["exp", "sub", "iss"]},
            )
        except jwt.PyJWTError as exc:
            raise TokenError(str(exc)) from exc
