from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.sharing.domain.matching import (
    OpenScope,
    SizeClass,
)
from app.sharing.infrastructure.sharing_repository import SharingRepository


def _dt(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 11, 20, hour, minute, tzinfo=UTC)


@pytest.fixture
def repo() -> SharingRepository:
    return SharingRepository()


@pytest.fixture
def mock_conn() -> AsyncMock:
    return AsyncMock()


@pytest.mark.asyncio
async def test_find_matching_candidates(repo: SharingRepository, mock_conn: AsyncMock):
    zone_id = uuid4()
    slot_id = uuid4()
    window_id = uuid4()

    mock_conn.fetch.return_value = [
        {
            "slot_id": slot_id,
            "zone_id": zone_id,
            "building_id": uuid4(),
            "slot_type": "TH1",
            "size_class": "L",
            "operational_status": "active",
            "share_window_id": window_id,
            "provider_user_id": uuid4(),
            "open_scope": "zone",
            "window_status": "open",
            "bookable_start": _dt(8, 0),
            "bookable_end": _dt(17, 0),
        }
    ]

    candidates = await repo.find_matching_candidates(
        conn=mock_conn,
        zone_id=zone_id,
        period_start=_dt(9, 0),
        period_end=_dt(12, 0),
        vehicle_size=SizeClass.M,
        allowed_scopes=[OpenScope.building, OpenScope.zone],
        limit=5,
    )

    assert len(candidates) == 1
    c = candidates[0]
    assert c.slot_id == slot_id
    assert c.size_class == SizeClass.L
    assert c.open_scope == OpenScope.zone
