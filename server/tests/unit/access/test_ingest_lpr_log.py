"""N1 ingest use case with in-memory fakes (SCRUM-109, BR-13, BR-20)."""

from contextlib import asynccontextmanager
from datetime import timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.access.domain.entity import LprRow
from app.access.usecase.ingest_lpr_log import EARLY_ARRIVAL, IngestLprLog, IngestLprLogInput

ZONE_A, ZONE_B = uuid4(), uuid4()
VEHICLE = uuid4()


class FakeCodec:
    def normalize(self, raw: str) -> str:
        plate = "".join(c for c in raw.upper() if c.isalnum())
        if len(plate) < 5:
            raise ValueError("not a plate")
        return plate

    def mask(self, normalized: str) -> str:
        return normalized[:3] + "***"

    def blind_index(self, normalized: str) -> bytes:
        return b"h:" + normalized.encode()

    def encrypt(self, normalized: str) -> bytes:
        return b"c:" + normalized.encode()


class FakeRepo:
    def __init__(self) -> None:
        self.threshold = Decimal("0.8")
        self.vehicles: list[UUID] = []
        self.duplicate = False
        self.events: list[dict[str, Any]] = []
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def zone_ids_by_code(self, conn: Any, codes: list[str]) -> dict[str, UUID]:
        return {c: {"A": ZONE_A, "B": ZONE_B}[c] for c in codes if c in ("A", "B")}

    async def ocr_review_threshold(self, conn: Any, zone_id: UUID) -> Decimal:
        return self.threshold

    async def insert_event(self, conn: Any, **kw: Any) -> int | None:
        self.events.append(kw)
        return None if self.duplicate else len(self.events)

    async def active_vehicle_ids(self, conn: Any, plate_hash: bytes) -> list[UUID]:
        self.calls.append(("active_vehicle_ids", (plate_hash,)))
        return self.vehicles

    async def mark_pending_review(self, conn: Any, event_id: int) -> None:
        self.calls.append(("mark_pending_review", (event_id,)))

    async def check_in(self, conn: Any, vehicle_id: UUID, zone_id: UUID, at: Any, tolerance: timedelta) -> UUID | None:
        self.calls.append(("check_in", (vehicle_id, zone_id, at, tolerance)))
        return BOOKING

    async def check_out(self, conn: Any, vehicle_id: UUID, zone_id: UUID, at: Any) -> UUID | None:
        self.calls.append(("check_out", (vehicle_id, zone_id, at)))
        return BOOKING

    async def owner_exit(self, conn: Any, vehicle_id: UUID, zone_id: UUID, at: Any) -> bool:
        self.calls.append(("owner_exit", (vehicle_id, zone_id, at)))
        return True

    async def link_event(self, conn: Any, event_id: int, vehicle_id: UUID, booking_id: UUID | None) -> None:
        self.calls.append(("link_event", (event_id, vehicle_id, booking_id)))

    def names(self) -> list[str]:
        return [n for n, _ in self.calls]


BOOKING = uuid4()


@asynccontextmanager
async def _uow(**_: Any):
    yield object()


def row(line: int = 2, **kw: str) -> LprRow:
    base = {
        "source_code": "cam-a-in", "source_event_id": f"e{line}", "zone_code": "A", "gate_code": "G1",
        "direction": "in", "occurred_at": "2026-05-01T08:00:00+07:00", "plate_text": "30A-123.45",
        "ocr_confidence": "0.95",
    }  # fmt: skip
    return LprRow(line, **{**base, **kw})


@pytest.fixture
def repo() -> FakeRepo:
    return FakeRepo()


async def run(repo: FakeRepo, *rows: LprRow, allowed: list[UUID] | None = None):
    return await IngestLprLog(repo, FakeCodec(), uow=_uow).execute(IngestLprLogInput(list(rows), allowed))


async def test_duplicate_event_is_counted_and_matches_nothing_br13(repo: FakeRepo) -> None:
    repo.duplicate = True

    report = await run(repo, row())

    assert (report.received, report.inserted, report.duplicate) == (1, 0, 1)
    assert repo.calls == []


async def test_low_ocr_goes_to_pending_review_without_vehicle_lookup_br13(repo: FakeRepo) -> None:
    report = await run(repo, row(ocr_confidence="0.62"))

    assert (report.inserted, report.pending_review) == (1, 1)
    assert repo.events[0]["status"] == "pending_review"
    assert repo.calls == []


@pytest.mark.parametrize("plate", ["", "   ", "??"], ids=["empty", "blank", "not-a-plate"])
async def test_unreadable_plate_is_pending_review_with_no_plate_data(repo: FakeRepo, plate: str) -> None:
    report = await run(repo, row(plate_text=plate, ocr_confidence="0.12"))

    ev = repo.events[0]
    assert ev["status"] == "pending_review"
    assert ev["plate_ciphertext"] is None and ev["plate_hash"] is None and ev["plate_masked"] is None
    assert (report.inserted, report.pending_review) == (1, 1)
    assert repo.calls == []


async def test_unknown_plate_is_kept_but_unmatched(repo: FakeRepo) -> None:
    report = await run(repo, row())

    assert repo.events[0]["status"] == "accepted"
    assert repo.names() == ["active_vehicle_ids"]
    assert (report.inserted, report.pending_review, report.matched_check_in) == (1, 0, 0)


async def test_plate_on_two_accounts_is_marked_pending_review_not_guessed(repo: FakeRepo) -> None:
    repo.vehicles = [uuid4(), uuid4()]

    report = await run(repo, row())

    assert repo.names() == ["active_vehicle_ids", "mark_pending_review"]
    assert report.pending_review == 1 and report.matched_check_in == 0


async def test_direction_in_checks_in_with_30_minute_tolerance(repo: FakeRepo) -> None:
    repo.vehicles = [VEHICLE]

    report = await run(repo, row(direction="in"))

    assert EARLY_ARRIVAL == timedelta(minutes=30)
    name, args = repo.calls[1]
    assert name == "check_in" and args[0] == VEHICLE and args[1] == ZONE_A and args[3] == timedelta(minutes=30)
    assert repo.calls[-1] == ("link_event", (1, VEHICLE, BOOKING))
    assert report.matched_check_in == 1 and "owner_exit" not in repo.names()


async def test_direction_out_checks_out_and_marks_owner_exit_br20(repo: FakeRepo) -> None:
    repo.vehicles = [VEHICLE]

    report = await run(repo, row(direction="out"))

    assert repo.names() == ["active_vehicle_ids", "check_out", "owner_exit", "link_event"]
    assert (report.matched_check_out, report.owner_exited, report.matched_check_in) == (1, 1, 0)


@pytest.mark.parametrize(
    ("kw", "allowed", "reason"),
    [
        ({"occurred_at": "2026-05-01T08:00:00"}, None, "timezone"),
        ({"zone_code": "Z"}, None, "unknown zone_code"),
        ({"zone_code": "B"}, [ZONE_A], "not permitted"),
    ],
    ids=["naive-timestamp", "unknown-zone", "disallowed-zone"],
)
async def test_invalid_rows_are_rejected_with_line_number(repo: FakeRepo, kw, allowed, reason) -> None:
    report = await run(repo, row(7, **kw), allowed=allowed)

    assert [(r.line, reason in r.reason) for r in report.rejected] == [(7, True)]
    assert report.inserted == 0 and repo.events == []


async def test_rows_are_processed_oldest_first_so_in_precedes_out(repo: FakeRepo) -> None:
    late = row(2, source_event_id="out", direction="out", occurred_at="2026-05-01T15:00:00+07:00")
    early = row(3, source_event_id="in", direction="in", occurred_at="2026-05-01T08:00:00+07:00")

    await run(repo, late, early)

    assert [e["source_event_id"] for e in repo.events] == ["in", "out"]
