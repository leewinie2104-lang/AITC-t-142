"""Caller's own active vehicles with masked plates (SCRUM-88)."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.facility.domain.entity import VehicleView
from app.facility.domain.ports import VehicleRepository
from app.platform.db.session import unit_of_work


@dataclass(frozen=True)
class ListMyVehiclesInput:
    user_id: UUID
    role: str
    zone_ids: list[UUID]


class ListMyVehicles:
    def __init__(
        self,
        repo: VehicleRepository,
        uow: Callable[..., AbstractAsyncContextManager[Any]] = unit_of_work,
    ) -> None:
        self._repo = repo
        self._uow = uow

    async def execute(self, inp: ListMyVehiclesInput) -> list[VehicleView]:
        async with self._uow(user_id=inp.user_id, role=inp.role, zone_ids=inp.zone_ids) as conn:
            return await self._repo.list_active_by_owner(conn, inp.user_id)
