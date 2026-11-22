from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class User:
    id: UUID
    full_name: str
    phone_e164: str
    role: str
    staff_zone_id: UUID | None


@dataclass(frozen=True)
class LoginRecord:
    """The app_user row as login needs it. lock_seconds is computed by the DB clock: > 0 while locked."""

    id: UUID
    password_hash: str
    role: str
    status: str
    staff_zone_id: UUID | None
    failed_logins: int
    lock_seconds: int | None


@dataclass(frozen=True)
class EligibilityView:
    zone_id: UUID
    building_id: UUID | None
    asset_kind: str
    role: str
    valid_until: datetime | None
    active: bool
