"""Gate-log CSV for a demo day: ``python -m demo_seed.lpr_csv [--date YYYY-MM-DD] [--out PATH]`` (stdout by default).

One normalized format, 1:1 with ``app.lpr_event`` before encryption; vendor adapters (SCRUM-165) convert into it and
job N1 (SCRUM-109) consumes it. Plates come from the seeded vehicles (``data.py``), so they never drift from the DB;
the only others are the tagged ``UNKNOWN_PLATES``. All fake. Clock times: ``data.CLOCK``.
"""

import argparse
import csv
import sys
from datetime import date, datetime, timedelta
from typing import TextIO

from .data import CLOCK, ICT, DemoData, build_demo_data

COLUMNS = ["source_code", "source_event_id", "zone_code", "gate_code", "direction", "occurred_at", "plate_text",
           "ocr_confidence"]  # fmt: skip
UNKNOWN_PLATES = {"51A-000.01"}  # a stranger's car: matches no seeded vehicle on purpose
_LANE = {"A": "a1", "B": "b1", "C": "c1"}  # one camera per direction and zone: direction comes from the lane

# (clock key, zone, direction, seeded user key or literal plate, ocr confidence); a user key is looked up in data
_ZONES: list[tuple[str, str, str, str, float]] = [
    ("gate_hoa_in", "B", "in", "hoa", 0.972),
    ("gate_lan_in", "A", "in", "lan", 0.961),  # sent twice by the vendor (BR-13)
    ("gate_minh_in", "C", "in", "minh", 0.934),
    ("gate_lowocr", "A", "in", "binh", 0.62),  # below the 0.8 review threshold
    ("gate_minh_out", "C", "out", "minh", 0.951),
    ("gate_unreadable", "B", "out", "", 0.12),  # OCR read nothing
    ("gate_unknown", "C", "in", "51A-000.01", 0.912),
    ("gate_lan_out", "A", "out", "lan", 0.958),
    ("gate_hoa_out", "B", "out", "hoa", 0.944),
]
_DUPLICATED = "gate_lan_in"
# Pilot timeline (docs/01-product/07-pilot-mot-toa.md section 7); anh_b leaves after the planned 15:00: the overstay exit
_PILOT: list[tuple[str, str, str, str, float]] = [
    ("gate_a_in", "A", "in", "chi_a", 0.968),  # chi_a posted her slot but her car never goes out: not free yet
    ("gate_c_out", "A", "out", "anh_c", 0.953),  # anh_c posted and drove out: his slot is free, anh_b gets it
    ("gate_b_in", "A", "in", "anh_b", 0.931),
    ("gate_c_back", "A", "in", "anh_c", 0.957),  # anh_c comes home early, anh_b is still parked
    ("gate_b_out", "A", "out", "anh_b", 0.944),  # overstay of booking b_today (planned 15:00)
]


def human_plate(plate: str) -> str:
    """``30A12345`` -> ``30A-123.45``: how a camera prints it, so N1 must normalize."""
    return f"{plate[:-5]}-{plate[-5:-2]}.{plate[-2:]}"


def _rows(prefix: str, spec: list[tuple[str, str, str, str, float]], day: date, data: DemoData) -> list[dict[str, str]]:
    plate_of = {u.key: v.plate for u in data.users for v in reversed(data.vehicles) if v.user_id == u.id}  # first wins
    rows = []
    for n, (clock, zone, direction, who, conf) in enumerate(spec, start=1):
        lane = f"cam-{_LANE[zone]}-{direction}"
        plate = human_plate(plate_of[who]) if who in plate_of else who
        rows.append({
            "source_code": lane,
            "source_event_id": f"{prefix}-{n:04d}",
            "zone_code": zone,
            "gate_code": "G1",
            "direction": direction,
            "occurred_at": datetime.combine(day, CLOCK[clock], tzinfo=ICT).isoformat(timespec="seconds"),
            "plate_text": plate,
            "ocr_confidence": f"{conf:.3f}",
        })  # fmt: skip
        if clock == _DUPLICATED and prefix == "zones":
            rows.append(dict(rows[-1]))  # exact re-send: same source_event_id on purpose
    return rows


def build_rows(day: date) -> list[dict[str, str]]:
    """All events of the demo day ``day``, sorted by time (stable, so the re-send stays next to its original)."""
    data = build_demo_data(day - timedelta(days=1))
    rows = _rows("zones", _ZONES, day, data) + _rows("pilot", _PILOT, day, data)
    return sorted(rows, key=lambda r: r["occurred_at"])


def write_csv(rows: list[dict[str, str]], out: TextIO) -> None:
    writer = csv.DictWriter(out, COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(prog="demo_seed.lpr_csv", description="Gate-log CSV for a demo day.")
    parser.add_argument("--date", type=date.fromisoformat, help="demo day, local time (default: tomorrow)")
    parser.add_argument("--out", help="file to write (default: stdout)")
    args = parser.parse_args()
    day = args.date or datetime.now(ICT).date() + timedelta(days=1)
    rows = build_rows(day)
    if args.out is None:
        write_csv(rows, sys.stdout)
    else:
        with open(args.out, "w", encoding="utf-8", newline="") as f:
            write_csv(rows, f)


if __name__ == "__main__":
    main()
