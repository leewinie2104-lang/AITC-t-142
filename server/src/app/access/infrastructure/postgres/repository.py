from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID


class PostgresLprRepository:
    async def zone_ids_by_code(self, conn: Any, codes: list[str]) -> dict[str, UUID]:
        rows = await conn.fetch("SELECT code, id FROM app.zone WHERE code = ANY($1::text[])", codes)
        return {r["code"]: r["id"] for r in rows}

    async def ocr_review_threshold(self, conn: Any, zone_id: UUID) -> Decimal:
        # Column default (0005) when no policy row is in force yet.
        value = await conn.fetchval("SELECT (app.current_zone_policy($1)).ocr_review_threshold", zone_id)
        return Decimal("0.8") if value is None else value

    async def insert_event(
        self,
        conn: Any,
        *,
        zone_id: UUID,
        source_code: str,
        source_event_id: str,
        gate_code: str,
        direction: str,
        occurred_at: datetime,
        plate_ciphertext: bytes | None,
        plate_hash: bytes | None,
        plate_masked: str | None,
        ocr_confidence: Decimal,
        status: str,
    ) -> int | None:
        # RETURNING id only: parksmart_app has no SELECT on plate_ciphertext. DO NOTHING = BR-13 dedupe.
        return await conn.fetchval(
            """
            INSERT INTO app.lpr_event (zone_id, source_code, source_event_id, gate_code, direction, occurred_at,
                                       plate_ciphertext, plate_hash, plate_masked, ocr_confidence, status)
            VALUES ($1, $2, $3, $4, $5::app.gate_direction, $6, $7, $8, $9, $10, $11::app.lpr_status)
            ON CONFLICT (zone_id, source_code, source_event_id) DO NOTHING
            RETURNING id
            """,
            zone_id, source_code, source_event_id, gate_code, direction, occurred_at,
            plate_ciphertext, plate_hash, plate_masked, ocr_confidence, status,
        )  # fmt: skip

    async def active_vehicle_ids(self, conn: Any, plate_hash: bytes) -> list[UUID]:
        # LIMIT 2: the caller only needs to know "none / one / ambiguous".
        rows = await conn.fetch("SELECT id FROM app.vehicle WHERE plate_hash = $1 AND is_active LIMIT 2", plate_hash)
        return [r["id"] for r in rows]

    async def mark_pending_review(self, conn: Any, event_id: int) -> None:
        await conn.execute(
            "UPDATE app.lpr_event SET status = 'pending_review' WHERE id = $1 AND status = 'accepted'", event_id
        )

    async def check_in(
        self, conn: Any, vehicle_id: UUID, zone_id: UUID, at: datetime, tolerance: timedelta
    ) -> UUID | None:
        # Outer `checked_in_at IS NULL` keeps a concurrent import from overwriting a time already set.
        return await conn.fetchval(
            """
            UPDATE app.booking SET checked_in_at = $3
             WHERE checked_in_at IS NULL AND id = (
                   SELECT id FROM app.booking
                    WHERE vehicle_id = $1 AND zone_id = $2 AND status = 'confirmed' AND checked_in_at IS NULL
                      AND $3 >= lower(period) - $4::interval AND $3 < upper(period)
                    ORDER BY lower(period) LIMIT 1)
            RETURNING id
            """,
            vehicle_id, zone_id, at, tolerance,
        )  # fmt: skip

    async def check_out(self, conn: Any, vehicle_id: UUID, zone_id: UUID, at: datetime) -> UUID | None:
        # No upper bound on `at`: leaving after the period end is the overstay exit.
        return await conn.fetchval(
            """
            UPDATE app.booking SET checked_out_at = $3
             WHERE checked_out_at IS NULL AND id = (
                   SELECT id FROM app.booking
                    WHERE vehicle_id = $1 AND zone_id = $2 AND checked_in_at IS NOT NULL
                      AND checked_out_at IS NULL AND checked_in_at <= $3
                    ORDER BY checked_in_at DESC LIMIT 1)
            RETURNING id
            """,
            vehicle_id, zone_id, at,
        )  # fmt: skip

    async def owner_exit(self, conn: Any, vehicle_id: UUID, zone_id: UUID, at: datetime) -> bool:
        # BR-20: only an open window whose owner already confirmed the OTP, and only inside its period.
        updated = await conn.fetchval(
            """
            UPDATE app.share_window SET owner_exited_at = $3
             WHERE zone_id = $2 AND status = 'open' AND owner_exited_at IS NULL
               AND owner_otp_confirmed_at IS NOT NULL AND $3 >= owner_otp_confirmed_at AND $3 < upper(period)
               AND owner_user_id = (SELECT user_id FROM app.vehicle WHERE id = $1)
            RETURNING id
            """,
            vehicle_id, zone_id, at,
        )  # fmt: skip
        return updated is not None

    async def link_event(self, conn: Any, event_id: int, vehicle_id: UUID, booking_id: UUID | None) -> None:
        await conn.execute(
            "UPDATE app.lpr_event SET matched_vehicle_id = $2, matched_booking_id = $3"
            " WHERE id = $1 AND matched_vehicle_id IS NULL",
            event_id, vehicle_id, booking_id,
        )  # fmt: skip
