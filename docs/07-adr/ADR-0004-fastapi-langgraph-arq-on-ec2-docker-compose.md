# ADR-0004: Server FastAPI + LangGraph, worker arq hai queue, chạy bằng docker compose

- **Status**: Accepted
- **Date**: 2026-11-17 · viết lại 2026-11-22 (plan 021: gộp phần liên quan của ADR-0011, 0012, 0013)
- **Liên quan**: [ADR-0005](ADR-0005-rds-postgres-asyncpg-rls-alembic-sql.md) · [ADR-0010](ADR-0010-backend-modules-agent-workflows-jobs.md) · [ADR-0012](ADR-0012-lean-lightsail-prod-and-team-ci-runner.md) · [ADR-0013](ADR-0013-dev-env-on-ci-runner-and-groq.md)

## Context

- Workflow Agent (W0–W7) stream câu trả lời và có bước dừng chờ BQL duyệt (HITL), có khi vài giờ sau mới chạy tiếp.
- Job nền (N1–N9) xử lý log cổng, chạy định kỳ; một số job kích hoạt workflow không có người chờ (N2 → W4, N1 → W3 / W5).
- Đã cân nhắc App Runner (timeout 120 giây), Lambda (giới hạn 15 phút), ECS Fargate (tốn công dựng ALB, VPC).

## Decision

- **Docker compose, cùng một image server:** `caddy` (reverse proxy, HTTPS) · `api` (FastAPI + uvicorn: REST, SSE; LangGraph chạy
  trong process) · `worker` (arq queue `bg`: N1–N9, cron, **không gọi LLM**) · `agent-worker` (arq queue `agent`: `run_workflow`,
  `resume_workflow`, có gọi LLM) · `redis` (hàng đợi, pub/sub, cache ngắn) · `postgres` (pgvector, ADR-0005).
- **Hai queue** để job nhanh không xếp sau lượt gọi LLM chậm; giới hạn đồng thời LLM bằng `max_jobs` của `agent-worker`.
- **Resume sau HITL** chạy trong `agent-worker`, không trong HTTP request duyệt; checkpointer Postgres giữ trạng thái qua restart.
- Redis chỉ giữ dữ liệu mất được; job ghi dữ liệu phải idempotent. Job N không gọi workflow trực tiếp mà phát sự kiện qua port
  `platform.publish()` (không có outbox trong demo, ADR-0011).
- **Chạy ở đâu:** prod demo trên một Lightsail, worker bật sau profile `workers` (ADR-0012); dev chạy api / worker trên laptop,
  Postgres + Redis dùng chung trên máy runner CI (ADR-0013).

## Consequences

- **Tích cực:** dựng nhanh, debug dễ (`docker compose logs`); không giới hạn thời gian request nên hợp SSE; LLM chậm không chặn job nền.
- **Tiêu cực:** một máy là điểm hỏng duy nhất, không tự scale; đội tự vá OS, xoay log. Lên nhiều máy cần load balancer và sticky
  session cho WebSocket (code giữ nguyên nhờ Redis pub/sub).

## Observability Impact

- Instrumentation tự động: `opentelemetry-instrumentation-fastapi`, `-asyncpg`, `-redis`, `-httpx`.
- Span thủ công `agent.<wN>.<step>`, `worker.<nN>.<job>`; `traceparent` đi theo payload job nên span worker nối với span tạo job.
- Metric (nhãn `queue` chỉ `bg` / `agent`): `arq_queue_depth{queue}`, `arq_job_duration_seconds{queue,job}`, `arq_job_failures_total{queue,job}`.
