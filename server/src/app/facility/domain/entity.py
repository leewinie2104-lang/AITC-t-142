from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class VehicleView:
    """A vehicle as its owner sees it: masked plate only, never the hash or ciphertext (BR-09)."""

    id: UUID
    plate_masked: str
    size_class: str
    created_at: datetime
