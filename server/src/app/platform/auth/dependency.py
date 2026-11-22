"""FastAPI dependency that turns `Authorization: Bearer <jwt>` into a CurrentUser."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID

from fastapi import Header, HTTPException, status

from app.platform.auth.tokens import TokenError, TokenService


@dataclass(frozen=True)
class CurrentUser:
    user_id: UUID
    role: str
    zone_ids: list[UUID]


def make_current_user(tokens: TokenService) -> Callable[..., Awaitable[CurrentUser]]:
    """Build the dependency around a TokenService, so tests can inject their own keys."""

    async def current_user(authorization: str | None = Header(default=None)) -> CurrentUser:
        unauthorized = HTTPException(
            status.HTTP_401_UNAUTHORIZED, "invalid_token", headers={"WWW-Authenticate": "Bearer"}
        )
        scheme, _, token = (authorization or "").partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            raise unauthorized
        try:
            claims = tokens.verify(token.strip())
            zone_ids = claims.get("zone_ids", [])
            if not isinstance(zone_ids, list):
                raise ValueError("zone_ids must be a list")
            return CurrentUser(
                user_id=UUID(str(claims["sub"])),
                role=str(claims["role"]),
                zone_ids=[UUID(str(z)) for z in zone_ids],
            )
        except (TokenError, KeyError, ValueError) as exc:
            raise unauthorized from exc

    return current_user
