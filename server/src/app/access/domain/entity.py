from dataclasses import dataclass, field


@dataclass(frozen=True)
class LprRow:
    """One gate-log line as received (all text); validated by the use case. `line` is its CSV line number."""

    line: int
    source_code: str
    source_event_id: str
    zone_code: str
    gate_code: str
    direction: str
    occurred_at: str
    plate_text: str
    ocr_confidence: str


@dataclass(frozen=True)
class Rejection:
    line: int
    reason: str  # never contains the plate (BR-09)


@dataclass
class IngestReport:
    received: int = 0
    inserted: int = 0
    duplicate: int = 0
    pending_review: int = 0
    matched_check_in: int = 0
    matched_check_out: int = 0
    owner_exited: int = 0
    rejected: list[Rejection] = field(default_factory=list)
