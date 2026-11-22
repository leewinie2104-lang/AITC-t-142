from typing import Any, Protocol
from uuid import UUID

from app.facility.domain.entity import VehicleView


class VehicleRepository(Protocol):
    async def list_active_by_owner(self, conn: Any, user_id: UUID) -> list[VehicleView]: ...
