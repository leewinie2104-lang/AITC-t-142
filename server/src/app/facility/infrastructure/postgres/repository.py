from typing import Any
from uuid import UUID

from app.facility.domain.entity import VehicleView


class PostgresVehicleRepository:
    async def list_active_by_owner(self, conn: Any, user_id: UUID) -> list[VehicleView]:
        # Explicit columns: parksmart_app has no SELECT on plate_ciphertext, so SELECT * would fail. plate_hash is
        # never exposed. `user_id = $1` is mandatory: RLS zone_staff_read would otherwise show staff others' vehicles.
        rows = await conn.fetch(
            """
            SELECT id, plate_masked, size_class::text AS size_class, created_at
              FROM app.vehicle
             WHERE user_id = $1 AND is_active
             ORDER BY created_at, id
            """,
            user_id,
        )
        return [VehicleView(**r) for r in rows]
