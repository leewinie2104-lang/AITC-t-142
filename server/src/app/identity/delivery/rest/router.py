from collections.abc import Awaitable, Callable
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, status

from app.identity.delivery.rest.schemas import EligibilityOut, LoginIn, MeOut, TokenOut
from app.identity.domain.errors import AccountLockedError, InvalidCredentialsError, UserNotFoundError
from app.identity.usecase.get_me import GetMe, GetMeInput
from app.identity.usecase.login import Login, LoginInput
from app.platform.auth.dependency import CurrentUser


def create_identity_router(
    login: Login, get_me: GetMe, current_user: Callable[..., Awaitable[CurrentUser]]
) -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["identity"])

    @router.post("/auth/login", response_model=TokenOut)
    async def login_endpoint(body: LoginIn) -> TokenOut:
        try:
            result = await login.execute(LoginInput(phone=body.phone, password=body.password))
        except InvalidCredentialsError:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid_credentials") from None
        except AccountLockedError as exc:
            raise HTTPException(
                status.HTTP_423_LOCKED, "account_locked", headers={"Retry-After": str(exc.retry_after_seconds)}
            ) from None
        return TokenOut(access_token=result.access_token, expires_in=result.expires_in)

    @router.get("/me", response_model=MeOut)
    async def me_endpoint(user: CurrentUser = Depends(current_user)) -> MeOut:
        try:
            result = await get_me.execute(GetMeInput(user.user_id, user.role, user.zone_ids))
        except UserNotFoundError:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "user_not_found") from None
        u = result.user
        return MeOut(
            id=u.id,
            full_name=u.full_name,
            phone=u.phone_e164,
            role=u.role,
            staff_zone_id=u.staff_zone_id,
            eligibilities=[EligibilityOut(**asdict(e)) for e in result.eligibilities],
        )

    return router
