from typing import Any
from uuid import UUID

from app.identity.domain.entity import LoginRecord, User
from app.identity.domain.phone import LOCK_MINUTES, MAX_FAILED_LOGINS


class PostgresUserRepository:
    async def find_for_login(self, conn: Any, phone_e164: str) -> LoginRecord | None:
        row = await conn.fetchrow(
            """
            SELECT id, password_hash, role::text AS role, status::text AS status, staff_zone_id, failed_logins,
                   CASE WHEN locked_until > now()
                        THEN ceil(extract(epoch FROM locked_until - now()))::int END AS lock_seconds
              FROM app.app_user
             WHERE phone_e164 = $1 AND deleted_at IS NULL
            """,
            phone_e164,
        )
        return LoginRecord(**row) if row else None

    async def record_failed_login(self, conn: Any, user_id: UUID) -> None:
        # One atomic statement: concurrent failures cannot lose increments. In SET every right-hand side sees the
        # OLD row, so the new count is spelled out in both columns. An expired lock restarts the count at 1.
        await conn.execute(
            """
            UPDATE app.app_user
               SET failed_logins = CASE WHEN locked_until < now() THEN 1 ELSE failed_logins + 1 END,
                   locked_until = CASE
                       WHEN (CASE WHEN locked_until < now() THEN 1 ELSE failed_logins + 1 END) >= $2
                       THEN now() + make_interval(mins => $3)
                       ELSE locked_until END
             WHERE id = $1
            """,
            user_id,
            MAX_FAILED_LOGINS,
            LOCK_MINUTES,
        )

    async def reset_failed_logins(self, conn: Any, user_id: UUID) -> None:
        await conn.execute("UPDATE app.app_user SET failed_logins = 0, locked_until = NULL WHERE id = $1", user_id)

    async def get_user(self, conn: Any, user_id: UUID) -> User | None:
        row = await conn.fetchrow(
            """
            SELECT id, full_name, phone_e164, role::text AS role, staff_zone_id
              FROM app.app_user WHERE id = $1 AND deleted_at IS NULL
            """,
            user_id,
        )
        return User(**row) if row else None
