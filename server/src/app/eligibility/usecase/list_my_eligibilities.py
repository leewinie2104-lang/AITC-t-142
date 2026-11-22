"""List the caller's own eligibilities (SCRUM-86, shown by GET /me)."""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.eligibility.domain.entity import Eligibility
from app.eligibility.domain.ports import EligibilityRepository


@dataclass(frozen=True)
class ListMyEligibilitiesInput:
    user_id: UUID


class ListMyEligibilities:
    def __init__(self, repo: EligibilityRepository) -> None:
        self._repo = repo

    async def execute(self, inp: ListMyEligibilitiesInput, conn: Any) -> list[Eligibility]:
        """`conn` belongs to the caller's unit of work, so RLS already scopes rows to that user."""
        return await self._repo.list_for_user(conn, inp.user_id)
