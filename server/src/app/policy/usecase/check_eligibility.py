"""Use case thẩm định quyền thuê ô đỗ theo Rule Engine (M3, ADR-0010)."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from app.policy.domain.engine import evaluate_rental_eligibility
from app.policy.domain.models import (
    OpenScope,
    RentalEligibilityResult,
    TargetSlotContext,
    UserEligibilityRecord,
)


@dataclass(frozen=True)
class CheckEligibilityCommand:
    """Lệnh yêu cầu thẩm định quyền thuê."""

    user_id: UUID
    slot_id: UUID
    slot_code: str
    building_id: UUID
    zone_id: UUID
    slot_kind: str = "TH1"
    open_scope: OpenScope = OpenScope.BUILDING
    as_of: datetime | None = None
    eligibilities: list[UserEligibilityRecord] | None = None


class CheckEligibilityUseCase:
    """Thực thi thẩm định quyền thuê bằng Rule Engine domain thuần túy."""

    async def execute(self, cmd: CheckEligibilityCommand) -> RentalEligibilityResult:
        as_of = cmd.as_of or datetime.now(UTC)
        target_slot = TargetSlotContext(
            slot_id=cmd.slot_id,
            slot_code=cmd.slot_code,
            building_id=cmd.building_id,
            zone_id=cmd.zone_id,
            slot_kind=cmd.slot_kind,
            open_scope=cmd.open_scope,
        )

        return evaluate_rental_eligibility(
            user_id=cmd.user_id,
            eligibilities=cmd.eligibilities or [],
            target_slot=target_slot,
            as_of=as_of,
        )
