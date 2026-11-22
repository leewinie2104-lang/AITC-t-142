"""FastAPI Router for Policy & Rule Engine (M3, ADR-0010)."""

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, status
from pydantic import BaseModel

from app.policy.domain.models import OpenScope, UserEligibilityRecord
from app.policy.usecase.check_eligibility import (
    CheckEligibilityCommand,
    CheckEligibilityUseCase,
)


class UserEligibilityIn(BaseModel):
    id: UUID
    asset_id: UUID
    zone_id: UUID
    building_id: UUID | None = None
    role: str = "resident"
    status: str = "verified"
    valid_from: datetime
    valid_to: datetime | None = None


class CheckEligibilityIn(BaseModel):
    user_id: UUID
    slot_id: UUID
    slot_code: str
    building_id: UUID
    zone_id: UUID
    slot_kind: str = "TH1"
    open_scope: OpenScope = OpenScope.BUILDING
    as_of: datetime | None = None
    eligibilities: list[UserEligibilityIn] | None = None


class CheckEligibilityOut(BaseModel):
    user_id: UUID
    target_slot_id: UUID
    effective_tier: str
    is_eligible: bool
    decision: str
    reason_code: str
    message: str
    valid_until: datetime | None = None


def create_policy_router(use_case: CheckEligibilityUseCase | None = None) -> APIRouter:
    router = APIRouter(prefix="/api/v1/policy", tags=["policy"])
    uc = use_case or CheckEligibilityUseCase()

    @router.post(
        "/check-eligibility",
        response_model=CheckEligibilityOut,
        status_code=status.HTTP_200_OK,
        summary="Thẩm định quyền thuê theo Rule Engine (BR-01, BR-15, BR-16)",
    )
    async def check_eligibility(payload: CheckEligibilityIn) -> CheckEligibilityOut:
        eligibility_records = [
            UserEligibilityRecord(user_id=payload.user_id, **item.model_dump()) for item in payload.eligibilities or []
        ]

        cmd = CheckEligibilityCommand(
            user_id=payload.user_id,
            slot_id=payload.slot_id,
            slot_code=payload.slot_code,
            building_id=payload.building_id,
            zone_id=payload.zone_id,
            slot_kind=payload.slot_kind,
            open_scope=payload.open_scope,
            as_of=payload.as_of or datetime.now(UTC),
            eligibilities=eligibility_records,
        )

        result = await uc.execute(cmd)

        return CheckEligibilityOut(
            user_id=result.user_id,
            target_slot_id=result.target_slot_id,
            effective_tier=result.effective_tier.value,
            is_eligible=result.is_eligible,
            decision=result.decision.value,
            reason_code=result.reason_code,
            message=result.message,
            valid_until=result.valid_until,
        )

    return router
