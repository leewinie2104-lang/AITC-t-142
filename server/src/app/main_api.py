"""Composition root của process `api` (ADR-0004, ADR-0010).

Nơi duy nhất biết mọi module: tạo infrastructure thật, đưa vào usecase,
đưa usecase vào router. Mỗi module thêm một hàm `wire_<module>(app, ...)`.

Chạy: uvicorn app.main_api:app --app-dir src --reload   (trong thư mục server/)
"""

from fastapi import APIRouter, FastAPI

from app.platform.config.settings import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0")

    health = APIRouter(prefix="/api/v1", tags=["health"])

    @health.get("/health")
    async def health_check() -> dict[str, str]:
        return {"status": "ok", "env": settings.app_env}

    app.include_router(health)
    # wire_sharing(app, ...), wire_booking(app, ...): thêm khi module có code.
    return app


app = create_app()
