from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class Eligibility:
    """One of the caller's entitlements. The asset's unit code is deliberately absent (BR-17)."""

    zone_id: UUID
    building_id: UUID | None
    asset_kind: str
    role: str
    valid_until: datetime | None  # None = no expiry
    active: bool  # verified and valid now
