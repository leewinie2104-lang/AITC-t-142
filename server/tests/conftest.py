"""Fixture dùng chung. Không gọi LLM hay DB thật trong unit test."""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main_api import create_app
from app.platform.config.settings import Settings


@pytest_asyncio.fixture
async def client():
    """HTTP client chạy thẳng vào app, không mở cổng mạng."""
    app = create_app(Settings(_env_file=None, app_env="test"))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
