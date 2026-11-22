from collections.abc import Awaitable, Callable
from dataclasses import asdict

from fastapi import APIRouter, Depends

from app.facility.delivery.rest.schemas import VehicleOut
from app.facility.usecase.list_my_vehicles import ListMyVehicles, ListMyVehiclesInput
from app.platform.auth.dependency import CurrentUser


def create_facility_router(
    list_my_vehicles: ListMyVehicles, current_user: Callable[..., Awaitable[CurrentUser]]
) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["facility"])

    @router.get("/me/vehicles", response_model=list[VehicleOut])
    async def my_vehicles_endpoint(user: CurrentUser = Depends(current_user)) -> list[VehicleOut]:
        vehicles = await list_my_vehicles.execute(ListMyVehiclesInput(user.user_id, user.role, user.zone_ids))
        return [VehicleOut(**asdict(v)) for v in vehicles]

    return router
