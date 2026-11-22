"""Vehicle plate rules shared by vehicle registration (M2) and LPR matching (N1).

Pure functions: no I/O, no crypto. `normalize` is the single canonical form that gets hashed, so the blind index
`vehicle.plate_hash` written by the seed or by M2 equals the one computed when an LPR log line is matched.
"""

import re

_NON_ALNUM = re.compile(r"[^A-Z0-9]")
# Vietnamese plates: 2-digit province code first, 7-10 characters once separators are stripped.
_VALID = re.compile(r"^[0-9]{2}[A-Z0-9]{5,8}$")


class InvalidPlateError(ValueError):
    """The text is not a plausible Vietnamese licence plate."""


def normalize(raw: str) -> str:
    """Upper-case and strip separators: ``"30a-123.45"`` -> ``"30A12345"``."""
    plate = _NON_ALNUM.sub("", raw.upper())
    if not _VALID.match(plate):
        # Never echo the plate: it is PII (BR-09).
        raise InvalidPlateError("not a valid plate")
    return plate


def mask(plate: str) -> str:
    """Display form that hides the middle: ``"30A12345"`` -> ``"30A-•••.45"`` (accepts raw or normalized input)."""
    normalized = normalize(plate)
    return f"{normalized[:3]}-•••.{normalized[-2:]}"
