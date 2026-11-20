"""Composition root của process `api` (ADR-0004, ADR-0010).

Nơi duy nhất biết mọi module: tạo infrastructure thật, đưa vào usecase,
đưa usecase vào router.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, FastAPI

from app.booking.delivery.router import create_booking_router
from app.booking.domain.ports import CandidateSlotDTO
from app.booking.infrastructure.booking_repository import BookingRepository
from app.booking.usecase.request_parking import RequestParkingUseCase
from app.platform.config.settings import Settings, get_settings
from app.sharing.domain.matching import OpenScope, SizeClass
from app.sharing.infrastructure.sharing_repository import SharingRepository


class SharingCandidateAdapter:
    """Adapter cắm SharingRepository vào CandidateFinderPort của module booking."""

    def __init__(self, sharing_repo: SharingRepository) -> None:
        self.sharing_repo = sharing_repo

    async def find_candidates(
        self,
        conn: Any,
        zone_id: UUID,
        period_start: datetime,
        period_end: datetime,
        vehicle_size: str,
        allowed_scopes: list[str],
        limit: int = 10,
    ) -> list[CandidateSlotDTO]:
        scopes = [OpenScope(s) for s in allowed_scopes]
        v_size = SizeClass(vehicle_size)
        candidates = await self.sharing_repo.find_matching_candidates(
            conn, zone_id, period_start, period_end, v_size, scopes, limit
        )
        return [
            CandidateSlotDTO(
                slot_id=c.slot_id,
                zone_id=c.zone_id,
                building_id=c.building_id,
                slot_type=c.slot_type,
                size_class=c.size_class.value,
                share_window_id=c.share_window_id,
                provider_user_id=c.provider_user_id,
                price_vnd=c.price_vnd,
            )
            for c in candidates
        ]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0")

    # 1. Health check router
    health = APIRouter(prefix="/api/v1", tags=["health"])

    @health.get("/health")
    async def health_check() -> dict[str, str]:
        return {"status": "ok", "env": settings.app_env}

    app.include_router(health)

    # 2. Wire booking module (M5) and sharing candidate discovery (M4)
    booking_repo = BookingRepository()
    sharing_repo = SharingRepository()
    adapter = SharingCandidateAdapter(sharing_repo=sharing_repo)
    booking_use_case = RequestParkingUseCase(
        booking_repo=booking_repo,
        candidate_finder=adapter,
    )
    booking_router = create_booking_router(use_case=booking_use_case)
    app.include_router(booking_router)

    return app


app = create_app()
