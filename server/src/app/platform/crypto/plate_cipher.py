"""Licence-plate protection (ADR-0005, docs/06-operations/02-database-security.md §3).

- ``encrypt`` / ``decrypt``: AES-256-GCM envelope stored in ``vehicle.plate_ciphertext`` (nonce || ciphertext || tag).
- ``blind_index``: HMAC-SHA256 with a separate key, stored in ``vehicle.plate_hash`` so a plate can be looked up
  without decrypting every row.

Callers pass the *normalized* plate (``app.facility.domain.plate.normalize``); this module has no plate rules.
Keys come from settings (local/demo: env; production: SSM/KMS later, D-07).
"""

import base64
import binascii
import hashlib
import hmac
import os
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.platform.config.settings import Settings, get_settings

_NONCE_BYTES = 12
_KEY_BYTES = 32


class PlateCryptoError(Exception):
    """Misconfigured key, or ciphertext that cannot be decrypted with it."""


def _decode_key(name: str, value: str) -> bytes:
    try:
        key = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise PlateCryptoError(f"{name} must be base64") from exc
    if len(key) != _KEY_BYTES:
        raise PlateCryptoError(f"{name} must decode to {_KEY_BYTES} bytes")
    return key


@dataclass(frozen=True)
class PlateCipher:
    enc_key: bytes
    hash_key: bytes
    key_version: int = 1

    def __post_init__(self) -> None:
        if len(self.enc_key) != _KEY_BYTES or len(self.hash_key) != _KEY_BYTES:
            raise PlateCryptoError(f"keys must be {_KEY_BYTES} bytes")
        if self.enc_key == self.hash_key:
            raise PlateCryptoError("encryption and hash keys must differ")
        if self.key_version < 1:
            raise PlateCryptoError("key_version must be >= 1")

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "PlateCipher":
        s = settings or get_settings()
        if not s.plate_enc_key or not s.plate_hash_key:
            raise PlateCryptoError("PLATE_ENC_KEY and PLATE_HASH_KEY must be set (see .env.example)")
        return cls(
            enc_key=_decode_key("PLATE_ENC_KEY", s.plate_enc_key),
            hash_key=_decode_key("PLATE_HASH_KEY", s.plate_hash_key),
            key_version=s.plate_key_version,
        )

    def _aad(self) -> bytes:
        # Binds the ciphertext to its key version so a row cannot be replayed under another version.
        return f"plate:v{self.key_version}".encode()

    def encrypt(self, normalized_plate: str) -> bytes:
        nonce = os.urandom(_NONCE_BYTES)
        return nonce + AESGCM(self.enc_key).encrypt(nonce, normalized_plate.encode(), self._aad())

    def decrypt(self, blob: bytes) -> str:
        nonce, body = blob[:_NONCE_BYTES], blob[_NONCE_BYTES:]
        try:
            return AESGCM(self.enc_key).decrypt(nonce, body, self._aad()).decode()
        except InvalidTag as exc:
            raise PlateCryptoError("cannot decrypt plate (wrong key or tampered data)") from exc

    def blind_index(self, normalized_plate: str) -> bytes:
        return hmac.new(self.hash_key, normalized_plate.encode(), hashlib.sha256).digest()
