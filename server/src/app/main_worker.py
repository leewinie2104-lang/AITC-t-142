"""Composition root của process `worker` và `agent-worker` (ADR-0004, ADR-0010).

- Queue `bg`: job N1–N8 (`<module>/delivery/jobs/`), cron, relay outbox. Không gọi LLM.
- Queue `agent`: `run_workflow`, `resume_workflow` (`agent/delivery/jobs/`).

Chạy (khi đã có job): arq app.main_worker.BgWorkerSettings
                      arq app.main_worker.AgentWorkerSettings
"""


class BgWorkerSettings:
    """Cấu hình arq cho queue `bg`. Thêm job N vào `functions` / `cron_jobs`."""

    queue_name = "bg"
    functions: list = []
    cron_jobs: list = []


class AgentWorkerSettings:
    """Cấu hình arq cho queue `agent`. `max_jobs` giới hạn theo quota Bedrock."""

    queue_name = "agent"
    functions: list = []
    max_jobs = 4
