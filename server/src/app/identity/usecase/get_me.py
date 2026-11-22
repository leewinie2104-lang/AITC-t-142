"""Current user's profile plus own eligibilities (SCRUM-86)."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.identity.domain.entity import EligibilityView, User
from app.identity.domain.errors import UserNotFoundError
from app.identity.domain.ports import EligibilityReader, UserRepository
from app.platform.db.session import unit_of_work


@dataclass(frozen=True)
class GetMeInput:
    user_id: UUID
    role: str
    zone_ids: list[UUID]


@dataclass(frozen=True)
class GetMeResult:
    user: User
    eligibilities: list[EligibilityView]


class GetMe:
    def __init__(
        self,
        repo: UserRepository,
        eligibilities: EligibilityReader,
        uow: Callable[..., AbstractAsyncContextManager[Any]] = unit_of_work,
    ) -> None:
        self._repo = repo
        self._eligibilities = eligibilities
        self._uow = uow

    async def execute(self, inp: GetMeInput) -> GetMeResult:
        async with self._uow(user_id=inp.user_id, role=inp.role, zone_ids=inp.zone_ids) as conn:
            user = await self._repo.get_user(conn, inp.user_id)
            if user is None:  # deleted while the token was still valid
                raise UserNotFoundError
            return GetMeResult(user, await self._eligibilities.list_for_user(conn, inp.user_id))
