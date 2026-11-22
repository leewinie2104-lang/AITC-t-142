from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID


class PlateCodec(Protocol):
    def normalize(self, raw: str) -> str:
        """Canonical plate; raises ValueError when it is not a plausible plate."""
        ...

    def mask(self, normalized: str) -> str: ...

    def blind_index(self, normalized: str) -> bytes: ...

    def encrypt(self, normalized: str) -> bytes: ...


class LprRepository(Protocol):
    async def zone_ids_by_code(self, conn: Any, codes: list[str]) -> dict[str, UUID]: ...

    async def ocr_review_threshold(self, conn: Any, zone_id: UUID) -> Decimal: ...

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
        """New event id, or None when (zone, source, source_event_id) already exists."""
        ...

    async def active_vehicle_ids(self, conn: Any, plate_hash: bytes) -> list[UUID]: ...

    async def mark_pending_review(self, conn: Any, event_id: int) -> None: ...

    async def check_in(
        self, conn: Any, vehicle_id: UUID, zone_id: UUID, at: datetime, tolerance: timedelta
    ) -> UUID | None: ...

    async def check_out(self, conn: Any, vehicle_id: UUID, zone_id: UUID, at: datetime) -> UUID | None: ...

    async def owner_exit(self, conn: Any, vehicle_id: UUID, zone_id: UUID, at: datetime) -> bool: ...

    async def link_event(self, conn: Any, event_id: int, vehicle_id: UUID, booking_id: UUID | None) -> None: ...
