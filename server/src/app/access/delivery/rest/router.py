import csv
import io
from collections.abc import Awaitable, Callable
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.access.delivery.rest.schemas import IngestReportOut
from app.access.domain.entity import LprRow, Rejection
from app.access.usecase.ingest_lpr_log import IngestLprLog, IngestLprLogInput
from app.platform.auth.dependency import CurrentUser
from app.platform.crypto.plate_cipher import PlateCryptoError

# Normalized gate-log format (demo_seed/lpr_csv.py); vendor adapters convert into it.
HEADER = [
    "source_code", "source_event_id", "zone_code", "gate_code", "direction", "occurred_at", "plate_text", "ocr_confidence",
]  # fmt: skip
MAX_BYTES = 1_000_000
MAX_ROWS = 5000


def create_access_router(ingest: IngestLprLog, current_user: Callable[..., Awaitable[CurrentUser]]) -> APIRouter:
    router = APIRouter(prefix="/api/v1/dev", tags=["access"])

    @router.post("/lpr-events/import", response_model=IngestReportOut)
    async def import_lpr_events(request: Request, user: CurrentUser = Depends(current_user)) -> IngestReportOut:
        if user.role not in ("zone_manager", "guard", "chain_operator"):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "forbidden")
        body = await request.body()
        if len(body) > MAX_BYTES:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "body_too_large")
        try:
            reader = csv.reader(io.StringIO(body.decode("utf-8-sig")))
            if next(reader, None) != HEADER:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "bad_header")
            rows: list[LprRow] = []
            malformed: list[Rejection] = []
            for fields in reader:
                if len(rows) + len(malformed) >= MAX_ROWS:
                    raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "too_many_rows")
                if len(fields) == len(HEADER):
                    rows.append(LprRow(reader.line_num, *fields))
                else:
                    malformed.append(Rejection(reader.line_num, "wrong number of columns"))
        except (UnicodeDecodeError, csv.Error) as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "bad_csv") from exc

        allowed = None if user.role == "chain_operator" else user.zone_ids
        try:
            report = await ingest.execute(IngestLprLogInput(rows, allowed))
        except PlateCryptoError as exc:  # plate keys not configured: nothing sensible to import without them
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "plate_keys_unavailable") from exc
        report.received += len(malformed)
        report.rejected = sorted(report.rejected + malformed, key=lambda r: r.line)
        return IngestReportOut(**asdict(report))

    return router
