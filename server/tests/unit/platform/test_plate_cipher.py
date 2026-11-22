"""AES-GCM envelope + HMAC blind index for vehicle plates (no DB, no network)."""

import base64
import os

import pytest

from app.platform.config.settings import Settings
from app.platform.crypto.plate_cipher import PlateCipher, PlateCryptoError


def _b64(n: int = 32) -> str:
    return base64.b64encode(os.urandom(n)).decode()


@pytest.fixture
def cipher() -> PlateCipher:
    return PlateCipher(enc_key=os.urandom(32), hash_key=os.urandom(32), key_version=1)


def test_encrypt_decrypt_round_trip(cipher: PlateCipher) -> None:
    blob = cipher.encrypt("30A12345")
    assert cipher.decrypt(blob) == "30A12345"


def test_ciphertext_hides_plate_and_is_randomized(cipher: PlateCipher) -> None:
    a, b = cipher.encrypt("30A12345"), cipher.encrypt("30A12345")
    assert b"30A12345" not in a
    assert a != b  # fresh nonce every time


def test_decrypt_with_other_key_fails(cipher: PlateCipher) -> None:
    other = PlateCipher(enc_key=os.urandom(32), hash_key=os.urandom(32))
    with pytest.raises(PlateCryptoError):
        other.decrypt(cipher.encrypt("30A12345"))


def test_decrypt_detects_tampering(cipher: PlateCipher) -> None:
    blob = bytearray(cipher.encrypt("30A12345"))
    blob[-1] ^= 0x01
    with pytest.raises(PlateCryptoError):
        cipher.decrypt(bytes(blob))


def test_ciphertext_is_bound_to_key_version() -> None:
    enc, hsh = os.urandom(32), os.urandom(32)
    v1 = PlateCipher(enc, hsh, key_version=1)
    v2 = PlateCipher(enc, hsh, key_version=2)
    with pytest.raises(PlateCryptoError):
        v2.decrypt(v1.encrypt("30A12345"))


def test_blind_index_is_32_bytes_and_deterministic(cipher: PlateCipher) -> None:
    h = cipher.blind_index("30A12345")
    assert len(h) == 32  # vehicle.plate_hash CHECK (length = 32)
    assert h == cipher.blind_index("30A12345")
    assert h != cipher.blind_index("30A12346")


def test_blind_index_depends_on_the_hash_key() -> None:
    enc = os.urandom(32)
    a = PlateCipher(enc, os.urandom(32))
    b = PlateCipher(enc, os.urandom(32))
    assert a.blind_index("30A12345") != b.blind_index("30A12345")


@pytest.mark.parametrize(
    ("enc", "hsh", "version"),
    [
        pytest.param(b"short", os.urandom(32), 1, id="short-enc-key"),
        pytest.param(os.urandom(32), b"short", 1, id="short-hash-key"),
        pytest.param(b"k" * 32, b"k" * 32, 1, id="same-key-twice"),
        pytest.param(os.urandom(32), os.urandom(32), 0, id="version-zero"),
    ],
)
def test_rejects_bad_key_material(enc: bytes, hsh: bytes, version: int) -> None:
    with pytest.raises(PlateCryptoError):
        PlateCipher(enc, hsh, version)


def test_from_settings_decodes_base64_keys() -> None:
    enc, hsh = _b64(), _b64()
    s = Settings(_env_file=None, plate_enc_key=enc, plate_hash_key=hsh, plate_key_version=3)
    c = PlateCipher.from_settings(s)
    assert c.key_version == 3
    assert c.enc_key == base64.b64decode(enc)
    assert c.decrypt(c.encrypt("30A12345")) == "30A12345"


@pytest.mark.parametrize(
    ("enc", "hsh", "fragment"),
    [
        pytest.param("", _b64(), "must be set", id="missing-enc"),
        pytest.param(_b64(), "", "must be set", id="missing-hash"),
        pytest.param("not base64!!", _b64(), "PLATE_ENC_KEY", id="enc-not-base64"),
        pytest.param(_b64(), _b64(16), "PLATE_HASH_KEY", id="hash-wrong-length"),
    ],
)
def test_from_settings_reports_misconfiguration_without_echoing_keys(enc: str, hsh: str, fragment: str) -> None:
    s = Settings(_env_file=None, plate_enc_key=enc, plate_hash_key=hsh)
    with pytest.raises(PlateCryptoError) as exc:
        PlateCipher.from_settings(s)
    assert fragment in str(exc.value)
    assert enc not in str(exc.value) or enc == ""
