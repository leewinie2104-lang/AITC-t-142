from typing import Any, Protocol
from uuid import UUID

from app.eligibility.domain.entity import Eligibility


class EligibilityRepository(Protocol):
    async def list_for_user(self, conn: Any, user_id: UUID) -> list[Eligibility]: ...
