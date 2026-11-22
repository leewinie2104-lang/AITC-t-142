from typing import Any
from uuid import UUID

from app.eligibility.domain.entity import Eligibility


class PostgresEligibilityRepository:
    async def list_for_user(self, conn: Any, user_id: UUID) -> list[Eligibility]:
        rows = await conn.fetch(
            """
            SELECT e.zone_id, a.building_id, a.kind::text AS asset_kind, e.role::text AS role,
                   upper(e.valid_during) AS valid_until,
                   (e.status = 'verified' AND e.valid_during @> now()) AS active
              FROM app.eligibility e
              JOIN app.asset a ON a.id = e.asset_id
             WHERE e.user_id = $1
             ORDER BY e.created_at
            """,
            user_id,
        )
        return [Eligibility(**r) for r in rows]
