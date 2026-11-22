"""Composition root của process `api` (ADR-0004, ADR-0010).

Nơi duy nhất biết mọi module: tạo infrastructure thật, đưa vào usecase,
đưa usecase vào router.
"""

from dataclasses import asdict
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, FastAPI

from app.access.delivery.rest.router import create_access_router
from app.access.infrastructure.postgres.repository import PostgresLprRepository
from app.access.usecase.ingest_lpr_log import IngestLprLog
from app.agreement.delivery.router import create_agreement_router
from app.agreement.infrastructure.agreement_repository import AgreementRepository
from app.agreement.infrastructure.otp_service import RedisOtpService
from app.agreement.usecase.confirm_agreement import ConfirmAgreementUseCase
from app.agreement.usecase.generate_agreement import GenerateAgreementUseCase
from app.agreement.usecase.get_agreement import GetAgreementUseCase
from app.agreement.usecase.send_agreement_otp import SendAgreementOtpUseCase
from app.approval.delivery.rest.router import router as approval_router
from app.booking.delivery.router import create_booking_router
from app.booking.domain.ports import CandidateSlotDTO
from app.booking.infrastructure.booking_repository import BookingRepository
from app.booking.usecase.request_parking import RequestParkingUseCase
from app.eligibility.infrastructure.postgres.repository import PostgresEligibilityRepository
from app.eligibility.usecase.list_my_eligibilities import ListMyEligibilities, ListMyEligibilitiesInput
from app.facility.delivery.rest.router import create_facility_router
from app.facility.delivery.rest.slots_router import router as slots_router
from app.facility.infrastructure.postgres.repository import PostgresVehicleRepository
from app.facility.usecase.list_my_vehicles import ListMyVehicles
from app.identity.delivery.rest.router import create_identity_router
from app.identity.domain.entity import EligibilityView
from app.identity.infrastructure.postgres.repository import PostgresUserRepository
from app.identity.usecase.get_me import GetMe
from app.identity.usecase.login import Login
from app.main_worker import PlateCodecAdapter
from app.platform.auth.dependency import make_current_user
from app.platform.auth.tokens import TokenService
from app.platform.config.settings import Settings, get_settings
from app.policy.delivery.rest.router import create_policy_router
from app.policy.usecase.check_eligibility import CheckEligibilityUseCase
from app.sharing.delivery.rest.router import router as sharing_router
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


class EligibilityReaderAdapter:
    """Adapter cắm use case của eligibility vào EligibilityReader port của module identity."""

    def __init__(self, use_case: ListMyEligibilities) -> None:
        self.use_case = use_case

    async def list_for_user(self, conn: Any, user_id: UUID) -> list[EligibilityView]:
        items = await self.use_case.execute(ListMyEligibilitiesInput(user_id=user_id), conn)
        return [EligibilityView(**asdict(i)) for i in items]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0")

    # 1. Health check router
    health = APIRouter(prefix="/api/v1", tags=["health"])

    @health.get("/health")
    async def health_check() -> dict[str, str]:
        return {"status": "ok", "env": settings.app_env}

    app.include_router(health)

    # 2. Identity (M1): login + GET /me; `current_user` is for any router that needs the caller
    tokens = TokenService.from_settings(settings)
    user_repo = PostgresUserRepository()
    eligibility_reader = EligibilityReaderAdapter(ListMyEligibilities(PostgresEligibilityRepository()))
    current_user = make_current_user(tokens)
    app.include_router(
        create_identity_router(
            login=Login(repo=user_repo, tokens=tokens),
            get_me=GetMe(repo=user_repo, eligibilities=eligibility_reader),
            current_user=current_user,
        )
    )

    # 2b. Facility (M2): own vehicles with masked plates
    app.include_router(
        create_facility_router(
            list_my_vehicles=ListMyVehicles(repo=PostgresVehicleRepository()), current_user=current_user
        )
    )

    # 3. Wire booking module (M5) and sharing candidate discovery (M4)
    booking_repo = BookingRepository()
    sharing_repo = SharingRepository()
    adapter = SharingCandidateAdapter(sharing_repo=sharing_repo)
    booking_use_case = RequestParkingUseCase(
        booking_repo=booking_repo,
        candidate_finder=adapter,
    )
    booking_router = create_booking_router(use_case=booking_use_case)
    app.include_router(booking_router)

    agreement_repo = AgreementRepository()
    otp_service = RedisOtpService(redis_url=settings.redis_url)
    app.include_router(
        create_agreement_router(
            get_use_case=GetAgreementUseCase(repo=agreement_repo),
            generate_use_case=GenerateAgreementUseCase(repo=agreement_repo),
            confirm_use_case=ConfirmAgreementUseCase(repo=agreement_repo, otp_service=otp_service),
            send_otp_use_case=SendAgreementOtpUseCase(repo=agreement_repo, otp_service=otp_service),
            repo=agreement_repo,
        )
    )

    # 4. Facility Slots router (cung cấp danh sách ô đỗ thực tế cho sơ đồ hầm)
    app.include_router(slots_router)

    # 5. Sharing router (quản lý lịch chia sẻ chủ chỗ & cơ chế W3 về sớm)
    app.include_router(sharing_router)

    # 6. Approval router (hàng đợi thẩm định M12 của BQL)
    app.include_router(approval_router)

    # 7. Policy router (M3 Rule Engine: thẩm định quyền thuê L1-L4 và phạm vi mở BR-01, BR-15, BR-16)
    policy_use_case = CheckEligibilityUseCase()
    app.include_router(create_policy_router(use_case=policy_use_case))
    # 7. Access (M8): N1 gate-log import, dev/demo only (the real feed is the N1 job, SCRUM-165)
    if settings.app_env != "production":
        app.include_router(
            create_access_router(
                ingest=IngestLprLog(repo=PostgresLprRepository(), plates=PlateCodecAdapter(settings)),
                current_user=current_user,
            )
        )

    return app


app = create_app()
