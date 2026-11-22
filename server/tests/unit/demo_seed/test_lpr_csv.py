"""Gate-log CSV generator: format, plates tied to the seeded vehicles, pilot timeline (plan 007, doc 07 section 7)."""

import csv
import io
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

import demo_seed
from app.facility.domain.plate import normalize
from demo_seed.data import build_demo_data
from demo_seed.lpr_csv import COLUMNS, UNKNOWN_PLATES, build_rows, write_csv

DAY = date(2026, 11, 23)


@pytest.fixture(scope="module")
def rows() -> list[dict[str, str]]:
    return build_rows(DAY)


@pytest.fixture(scope="module")
def data():
    return build_demo_data(DAY - timedelta(days=1))


def test_csv_header_and_field_formats(rows: list[dict[str, str]]) -> None:
    buf = io.StringIO()
    write_csv(rows, buf)
    parsed = list(csv.reader(io.StringIO(buf.getvalue())))
    assert parsed[0] == COLUMNS
    times = []
    for r in rows:
        t = datetime.fromisoformat(r["occurred_at"])
        assert t.utcoffset() == timedelta(hours=7)
        times.append(t)
        assert 0 <= float(r["ocr_confidence"]) <= 1
        assert len(r["ocr_confidence"].split(".")[1]) == 3
        assert r["direction"] == {"in": "in", "out": "out"}[r["source_code"].rsplit("-", 1)[1]]
    assert times == sorted(times)


def test_plates_come_from_seeded_vehicles_with_the_planned_anomalies(rows, data) -> None:
    seeded = {v.plate for v in data.vehicles}
    for r in rows:
        if r["plate_text"] and r["plate_text"] not in UNKNOWN_PLATES:
            assert normalize(r["plate_text"]) in seeded, r["plate_text"]
    assert sum(1 for r in rows if not r["plate_text"]) == 1  # unreadable
    dup = [i for i, n in Counter(r["source_event_id"] for r in rows).items() if n == 2]
    assert len(dup) == 1
    assert len({tuple(r.items()) for r in rows if r["source_event_id"] == dup[0]}) == 1  # BR-13 exact re-send
    assert any(
        float(r["ocr_confidence"]) < 0.8 and normalize(r["plate_text"]) in seeded for r in rows if r["plate_text"]
    )


def test_pilot_events_follow_the_doc_timeline(rows, data) -> None:
    user_of = {v.plate: u.key for u in data.users for v in data.vehicles if v.user_id == u.id}
    pilot = [
        (user_of[normalize(r["plate_text"])], r["direction"], r)
        for r in rows
        if r["source_event_id"].startswith("pilot-")
    ]
    assert [(u, d) for u, d, _ in pilot if u != "chi_a"] == [
        ("anh_c", "out"), ("anh_b", "in"), ("anh_c", "in"), ("anh_b", "out"),
    ]  # fmt: skip
    assert not [1 for u, d, _ in pilot if u == "chi_a" and d == "out"]
    b_end = next(b.period_to for b in data.bookings if b.period_from.date() == data.demo_day)  # b_today
    assert datetime.fromisoformat(pilot[-1][2]["occurred_at"]) > b_end  # overstay of b_today


def test_build_rows_shifts_every_timestamp_by_the_day_difference(rows) -> None:
    later = build_rows(DAY + timedelta(days=5))
    assert len(later) == len(rows)
    for a, b in zip(rows, later, strict=True):
        assert datetime.fromisoformat(b["occurred_at"]) - datetime.fromisoformat(a["occurred_at"]) == timedelta(days=5)


def test_committed_sample_matches_the_generator(rows) -> None:
    sample = Path(demo_seed.__file__).parent / "samples" / "lpr_events_sample.csv"
    buf = io.StringIO()
    write_csv(build_rows(date(2026, 11, 23)), buf)
    assert sample.read_text(encoding="utf-8").replace("\r\n", "\n") == buf.getvalue().replace("\r\n", "\n")
