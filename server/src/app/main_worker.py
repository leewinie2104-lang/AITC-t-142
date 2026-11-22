"""Composition root của process `worker` và `agent-worker` (ADR-0004, ADR-0010).

- Queue `bg`: job N1–N8 (`<module>/delivery/jobs/`), cron, relay outbox. Không gọi LLM.
- Queue `agent`: `run_workflow`, `resume_workflow` (`agent/delivery/jobs/`).

Chạy (khi đã có job): arq app.main_worker.BgWorkerSettings
                      arq app.main_worker.AgentWorkerSettings
"""

from typing import Any

from app.access.delivery.jobs.n1_ingest_lpr_log import n1_ingest_lpr_log
from app.access.infrastructure.postgres.repository import PostgresLprRepository
from app.access.usecase.ingest_lpr_log import IngestLprLog
from app.facility.domain import plate as plate_rules
from app.platform.config.settings import Settings, get_settings
from app.platform.crypto.plate_cipher import PlateCipher


class PlateCodecAdapter:
    """facility.domain.plate + PlateCipher as access's PlateCodec port; shared by the API and the worker."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._cipher: PlateCipher | None = None

    def _get_cipher(self) -> PlateCipher:
        # Lazy: missing plate keys must not stop the app from booting; the import endpoint answers 503 instead.
        if self._cipher is None:
            self._cipher = PlateCipher.from_settings(self._settings)
        return self._cipher

    def normalize(self, raw: str) -> str:
        self._get_cipher()  # fail on the first plate (PlateCryptoError) instead of half-way through a row
        return plate_rules.normalize(raw)

    def mask(self, normalized: str) -> str:
        return plate_rules.mask(normalized)

    def blind_index(self, normalized: str) -> bytes:
        return self._get_cipher().blind_index(normalized)

    def encrypt(self, normalized: str) -> bytes:
        return self._get_cipher().encrypt(normalized)


async def bg_startup(ctx: dict[str, Any]) -> None:
    ctx["ingest_lpr_log"] = IngestLprLog(repo=PostgresLprRepository(), plates=PlateCodecAdapter(get_settings()))


class BgWorkerSettings:
    """Cấu hình arq cho queue `bg`. Thêm job N vào `functions` / `cron_jobs`."""

    queue_name = "bg"
    on_startup = bg_startup
    functions: list = [n1_ingest_lpr_log]
    cron_jobs: list = []


class AgentWorkerSettings:
    """Cấu hình arq cho queue `agent`. `max_jobs` giới hạn theo quota Bedrock."""

    queue_name = "agent"
    functions: list = []
    max_jobs = 4
