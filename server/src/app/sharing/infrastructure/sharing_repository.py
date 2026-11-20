"""Sharing Repository for managing share_window and candidate discovery (M4)."""

import logging
from typing import Any
from uuid import UUID

from app.sharing.domain.matching import (
    OpenScope,
    ShareStatus,
    SizeClass,
    SlotCandidate,
    SlotOperationalStatus,
    TimeRange,
)

logger = logging.getLogger(__name__)


class SharingRepository:
    """Repository quản lý truy vấn khung chia sẻ và tìm kiếm ứng viên ô đỗ."""

    async def find_matching_candidates(
        self,
        conn: Any,
        zone_id: UUID,
        period_start: Any,
        period_end: Any,
        vehicle_size: SizeClass,
        allowed_scopes: list[OpenScope],
        limit: int = 10,
    ) -> list[SlotCandidate]:
        """Truy vấn tìm kiếm các ứng viên ô đỗ và khung chia sẻ khả dụng trong khu."""
        query = """
            SELECT
                s.id AS slot_id,
                s.zone_id,
                s.building_id,
                s.slot_type,
                s.size_class,
                s.operational_status,
                w.id AS share_window_id,
                w.owner_user_id AS provider_user_id,
                w.open_scope,
                w.status AS window_status,
                lower(w.bookable_period) AS bookable_start,
                upper(w.bookable_period) AS bookable_end
            FROM app.slot s
            JOIN app.share_window w ON w.slot_id = s.id
            WHERE s.zone_id = $1
              AND s.operational_status = 'active'
              AND w.status = 'open'
              AND w.bookable_period @> tstzrange($2, $3, '[)')
              AND w.open_scope = ANY($4)
              AND NOT EXISTS (
                  SELECT 1 FROM app.booking b
                  WHERE b.slot_id = s.id
                    AND b.period && tstzrange($2, $3, '[)')
                    AND b.status IN ('held', 'pending_agreement', 'pending_approval', 'confirmed')
                    AND (b.status <> 'held' OR b.hold_expires_at > now())
              )
            LIMIT $5;
        """

        scope_values = [s.value for s in allowed_scopes]
        rows = await conn.fetch(
            query,
            zone_id,
            period_start,
            period_end,
            scope_values,
            limit,
        )

        return [
            SlotCandidate(
                slot_id=r["slot_id"],
                zone_id=r["zone_id"],
                building_id=r["building_id"],
                slot_type=r["slot_type"],
                size_class=SizeClass(r["size_class"]),
                operational_status=SlotOperationalStatus(r["operational_status"]),
                open_scope=OpenScope(r["open_scope"]),
                bookable_period=TimeRange(start=r["bookable_start"], end=r["bookable_end"]),
                price_vnd=50_000,
                share_window_id=r["share_window_id"],
                provider_user_id=r["provider_user_id"],
                window_status=ShareStatus(r["window_status"]),
            )
            for r in rows
        ]
