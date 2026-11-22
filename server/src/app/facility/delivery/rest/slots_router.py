"""Router cung cấp danh sách ô đỗ thực tế cho Facility / Map (ADR-0010)."""

from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Query
from pydantic import BaseModel

from demo_seed.ids import demo_id


class SlotOut(BaseModel):
    id: UUID
    code: str
    floor: Literal["B1", "B2", "B3"]
    kind: Literal["TH1", "TH2", "TH3"]
    price_per_hour: int
    is_occupied: bool
    is_buffer: bool
    near_lobby: str
    distance_meters: int
    size_class: str
    owner_apartment: str | None = None


# Danh mục ô đỗ chuẩn deterministic UUID từ Demo Seed
ZONE_A_SLOTS: list[SlotOut] = [
    SlotOut(
        id=demo_id("slot", "A", "B2-045"),
        code="B2-045",
        floor="B2",
        kind="TH1",
        price_per_hour=15000,
        is_occupied=False,
        is_buffer=False,
        near_lobby="Sảnh S2",
        distance_meters=30,
        size_class="M",
        owner_apartment="S2.01-1408",
    ),
    SlotOut(
        id=demo_id("slot", "A", "B2-046"),
        code="B2-046",
        floor="B2",
        kind="TH2",
        price_per_hour=20000,
        is_occupied=False,
        is_buffer=False,
        near_lobby="Sảnh S2",
        distance_meters=45,
        size_class="L",
        owner_apartment="S2.02-0902",
    ),
    SlotOut(
        id=demo_id("slot", "A", "B2-101"),
        code="B2-101",
        floor="B2",
        kind="TH2",
        price_per_hour=20000,
        is_occupied=True,
        is_buffer=False,
        near_lobby="Sảnh S1",
        distance_meters=70,
        size_class="L",
        owner_apartment="S2.01-0504",
    ),
    SlotOut(
        id=demo_id("slot", "A", "TH3-01"),
        code="TH3-01",
        floor="B1",
        kind="TH3",
        price_per_hour=25000,
        is_occupied=False,
        is_buffer=True,
        near_lobby="Sảnh Trung Tâm",
        distance_meters=60,
        size_class="XL",
    ),
    SlotOut(
        id=demo_id("slot", "A", "TH3-02"),
        code="TH3-02",
        floor="B1",
        kind="TH3",
        price_per_hour=25000,
        is_occupied=False,
        is_buffer=True,
        near_lobby="Sảnh Trung Tâm",
        distance_meters=65,
        size_class="XL",
    ),
]

router = APIRouter(prefix="/api/v1/facility", tags=["facility_slots"])


@router.get("/slots", response_model=list[SlotOut])
async def list_slots(
    floor: str | None = Query(default=None, description="B1, B2, hoặc B3"),
    kind: str | None = Query(default=None, description="TH1, TH2, hoặc TH3"),
) -> list[SlotOut]:
    """Truy vấn danh sách các ô đỗ khả dụng từ hệ thống."""
    return [
        s for s in ZONE_A_SLOTS
        if (floor is None or s.floor.upper() == floor.upper())
        and (kind is None or s.kind.upper() == kind.upper())
    ]
