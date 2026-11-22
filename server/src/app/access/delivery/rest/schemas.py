from pydantic import BaseModel


class RejectedOut(BaseModel):
    line: int
    reason: str


class IngestReportOut(BaseModel):
    received: int
    inserted: int
    duplicate: int
    pending_review: int
    matched_check_in: int
    matched_check_out: int
    owner_exited: int
    rejected: list[RejectedOut]
