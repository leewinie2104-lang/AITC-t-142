import re

from app.identity.domain.errors import InvalidPhoneError

# Defaults, confirm with BQL (like zone_policy). The repository SQL applies them as bind parameters.
MAX_FAILED_LOGINS = 5
LOCK_MINUTES = 15

_E164 = re.compile(r"^\+[1-9][0-9]{7,14}$")


def normalize_phone(raw: str) -> str:
    """`0901 000-001` -> `+84901000001`; anything that is not E.164 afterwards is rejected."""
    phone = re.sub(r"[ \-.]", "", raw)
    if phone.startswith("0"):
        phone = "+84" + phone[1:]
    if not _E164.match(phone):
        raise InvalidPhoneError
    return phone
