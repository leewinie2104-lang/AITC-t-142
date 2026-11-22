"""N1: ingest a batch of normalized gate-log rows (camera adapters push them, SCRUM-165)."""

from typing import Any

from app.access.domain.entity import LprRow
from app.access.usecase.ingest_lpr_log import IngestLprLogInput


async def n1_ingest_lpr_log(ctx: dict[str, Any], rows: list[dict[str, str]]) -> dict[str, Any]:
    # `ctx["ingest_lpr_log"]` is the use case, put there by main_worker on_startup.
    items = [LprRow(line=n, **row) for n, row in enumerate(rows, start=1)]
    report = await ctx["ingest_lpr_log"].execute(IngestLprLogInput(items, allowed_zone_ids=None))
    return {"received": report.received, "inserted": report.inserted, "duplicate": report.duplicate,
            "rejected": len(report.rejected)}  # fmt: skip
