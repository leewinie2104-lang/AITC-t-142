from typing import Any, Protocol
from uuid import UUID

from app.identity.domain.entity import EligibilityView, LoginRecord, User


class UserRepository(Protocol):
    async def find_for_login(self, conn: Any, phone_e164: str) -> LoginRecord | None: ...

    async def record_failed_login(self, conn: Any, user_id: UUID) -> None: ...

    async def reset_failed_logins(self, conn: Any, user_id: UUID) -> None: ...

    async def get_user(self, conn: Any, user_id: UUID) -> User | None: ...


class EligibilityReader(Protocol):
    async def list_for_user(self, conn: Any, user_id: UUID) -> list[EligibilityView]: ...


class TokenIssuer(Protocol):
    def issue(self, user_id: UUID, role: str, zone_ids: list[UUID]) -> tuple[str, int]: ...
