"""N1: turn gate-log rows into lpr_event + booking check-in/out + owner exit (SCRUM-109, BR-13, BR-20)."""

import re
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from app.access.domain.entity import IngestReport, LprRow, Rejection
from app.access.domain.ports import LprRepository, PlateCodec
from app.platform.db.session import unit_of_work

# Default, confirm with BQL: how long before the booked start a car may enter and still check in.
EARLY_ARRIVAL = timedelta(minutes=30)
_GATE = re.compile(r"^[A-Z0-9_-]{1,32}$")  # same as the lpr_event CHECK


@dataclass(frozen=True)
class IngestLprLogInput:
    rows: list[LprRow]
    allowed_zone_ids: list[UUID] | None  # None = every zone (chain_operator, system jobs)


@dataclass(frozen=True)
class _Valid:
    row: LprRow
    zone_id: UUID
    at: datetime
    confidence: Decimal


class IngestLprLog:
    def __init__(
        self,
        repo: LprRepository,
        plates: PlateCodec,
        uow: Callable[..., AbstractAsyncContextManager[Any]] = unit_of_work,
    ) -> None:
        self._repo = repo
        self._plates = plates
        self._uow = uow

    async def execute(self, inp: IngestLprLogInput) -> IngestReport:
        report = IngestReport(received=len(inp.rows))
        async with self._uow(role="system") as conn:
            zones = await self._repo.zone_ids_by_code(conn, sorted({r.zone_code for r in inp.rows}))
        valid: list[_Valid] = []
        for row in inp.rows:
            item = self._validate(row, zones, inp.allowed_zone_ids)
            if isinstance(item, Rejection):
                report.rejected.append(item)
            else:
                valid.append(item)
        # Oldest first, so an `in` is applied before its `out` when both are in one file.
        for item in sorted(valid, key=lambda v: v.at):
            async with self._uow(role="system", zone_ids=[item.zone_id]) as conn:  # one tx per row
                await self._ingest(conn, item, report)
        return report

    def _validate(self, row: LprRow, zones: dict[str, UUID], allowed: list[UUID] | None) -> _Valid | Rejection:
        zone_id = zones.get(row.zone_code)
        if zone_id is None:
            return Rejection(row.line, "unknown zone_code")
        if allowed is not None and zone_id not in allowed:
            return Rejection(row.line, "zone not permitted for caller")
        if not row.source_code.strip() or len(row.source_code) > 64:
            return Rejection(row.line, "invalid source_code")
        if not 1 <= len(row.source_event_id) <= 128:
            return Rejection(row.line, "invalid source_event_id")
        if not _GATE.match(row.gate_code):
            return Rejection(row.line, "invalid gate_code")
        if row.direction not in ("in", "out"):
            return Rejection(row.line, "direction must be in or out")
        try:
            at = datetime.fromisoformat(row.occurred_at)
        except ValueError:
            return Rejection(row.line, "invalid occurred_at")
        if at.tzinfo is None:  # a vendor timestamp without offset cannot be trusted (edge case 5)
            return Rejection(row.line, "occurred_at needs a timezone offset")
        try:
            confidence = Decimal(row.ocr_confidence)
        except InvalidOperation:
            return Rejection(row.line, "invalid ocr_confidence")
        if not confidence.is_finite() or not Decimal(0) <= confidence <= Decimal(1):
            return Rejection(row.line, "ocr_confidence must be within 0..1")
        return _Valid(row, zone_id, at, confidence)

    async def _ingest(self, conn: Any, v: _Valid, report: IngestReport) -> None:
        row = v.row
        ciphertext = digest = masked = None
        status = "accepted"
        try:
            plate = self._plates.normalize(row.plate_text) if row.plate_text.strip() else None
        except ValueError:
            plate = None
        if plate is None:
            status = "pending_review"  # nothing readable: a human decides
        else:
            ciphertext, digest, masked = (
                self._plates.encrypt(plate),
                self._plates.blind_index(plate),
                self._plates.mask(plate),
            )
            if v.confidence < await self._repo.ocr_review_threshold(conn, v.zone_id):
                status = "pending_review"  # BR-13: low OCR never concludes anything on its own

        event_id = await self._repo.insert_event(
            conn,
            zone_id=v.zone_id,
            source_code=row.source_code,
            source_event_id=row.source_event_id,
            gate_code=row.gate_code,
            direction=row.direction,
            occurred_at=v.at,
            plate_ciphertext=ciphertext,
            plate_hash=digest,
            plate_masked=masked,
            ocr_confidence=v.confidence,
            status=status,
        )
        if event_id is None:
            report.duplicate += 1
            return
        report.inserted += 1
        if status != "accepted" or digest is None:
            report.pending_review += 1
            return

        vehicles = await self._repo.active_vehicle_ids(conn, digest)
        if len(vehicles) > 1:  # same plate on two accounts: do not guess
            await self._repo.mark_pending_review(conn, event_id)
            report.pending_review += 1
            return
        if not vehicles:  # stranger or misread plate: keep the event, match nothing
            return
        vehicle_id = vehicles[0]

        booking_id: UUID | None = None
        if row.direction == "in":
            booking_id = await self._repo.check_in(conn, vehicle_id, v.zone_id, v.at, EARLY_ARRIVAL)
            report.matched_check_in += booking_id is not None
        else:
            booking_id = await self._repo.check_out(conn, vehicle_id, v.zone_id, v.at)
            report.matched_check_out += booking_id is not None
            report.owner_exited += await self._repo.owner_exit(conn, vehicle_id, v.zone_id, v.at)
        await self._repo.link_event(conn, event_id, vehicle_id, booking_id)
