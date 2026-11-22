from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class VehicleOut(BaseModel):
    id: UUID
    plate_masked: str
    size_class: str
    created_at: datetime
