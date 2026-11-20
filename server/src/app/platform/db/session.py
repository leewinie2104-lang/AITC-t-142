"""Database session and RLS Unit of Work (ADR-0005).

Cung cấp kết nối asyncpg, thiết lập ngữ cảnh RLS (SET LOCAL app.user_id, app.role, app.zone_ids),
và quản lý transaction nguyên tử.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, nullcontext
from typing import Any
from uuid import UUID

import asyncpg

from app.platform.config.settings import get_settings

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None


async def init_db_pool(dsn: str | None = None, min_size: int = 2, max_size: int = 10) -> asyncpg.Pool:
    """Khởi tạo connection pool asyncpg cho tiến trình API hoặc Worker."""
    global _pool
    if _pool is not None:
        return _pool

    settings = get_settings()
    target_dsn = dsn or settings.database_url
    logger.info("Initializing asyncpg pool to %s", target_dsn)
    _pool = await asyncpg.create_pool(
        dsn=target_dsn,
        min_size=min_size,
        max_size=max_size,
        statement_cache_size=0,  # Tương thích với PGBouncer nếu có
    )
    return _pool


async def close_db_pool() -> None:
    """Đóng pool khi shutdown ứng dụng."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def get_db_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        return await init_db_pool()
    return _pool


@asynccontextmanager
async def unit_of_work(
    conn_or_pool: asyncpg.Connection | asyncpg.Pool | None = None,
    user_id: UUID | None = None,
    role: str = "resident",
    zone_ids: list[UUID] | None = None,
) -> AsyncIterator[asyncpg.Connection]:
    """Mở một transaction và thiết lập biến ngữ cảnh RLS (ADR-0005).

    Đảm bảo mọi truy vấn trong khối lệnh chạy với quyền và phạm vi khu chuẩn xác.
    """
    pool = await get_db_pool() if conn_or_pool is None else conn_or_pool
    conn_cm = pool.acquire() if isinstance(pool, asyncpg.Pool) else nullcontext(pool)
    async with conn_cm as conn, conn.transaction():
        await _apply_rls_context(conn, user_id, role, zone_ids)
        yield conn


async def _apply_rls_context(
    conn: Any,
    user_id: UUID | None,
    role: str,
    zone_ids: list[UUID] | None,
) -> None:
    """Đặt các biến cấu hình session SET LOCAL cho RLS."""
    if user_id:
        await conn.execute("SET LOCAL app.user_id = $1;", str(user_id))
    if role:
        await conn.execute("SET LOCAL app.role = $1;", role)
    if zone_ids:
        # Format mảng PostgreSQL ví dụ: '{uuid1,uuid2}'
        zone_str = "{" + ",".join(str(z) for z in zone_ids) + "}"
        await conn.execute("SET LOCAL app.zone_ids = $1;", zone_str)
