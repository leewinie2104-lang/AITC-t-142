# ADR-0004: Server FastAPI + LangGraph và worker arq + Redis, chạy bằng docker compose trên EC2

- **Status**: Accepted · **Partly superseded by [ADR-0011](ADR-0011-mvp-simplifications.md) (2026-11-18)**: relay outbox và việc job N phát sự kiện vào outbox không có trong demo
- **Date**: 2026-11-17 (cập nhật cùng ngày: tách queue `bg` / `agent`, thêm `agent-worker`, vì W5 do N1 kích hoạt có bước gọi LLM)
- **Liên quan**: [ADR-0003](ADR-0003-rest-openapi-sse-websocket-single-domain.md) · [ADR-0005](ADR-0005-rds-postgres-asyncpg-rls-alembic-sql.md) · [ADR-0010](ADR-0010-backend-modules-agent-workflows-jobs.md) · [Backlog](../01-product/05-backlog.md)

## Context

- **Agent (W0–W7):** stream câu trả lời; có bước dừng chờ BQL duyệt (HITL) rồi chạy tiếp, có thể sau vài giờ.
- **Worker nền (N1–N8):** nhận sự kiện LPR, job định kỳ, job hằng đêm. Một số workflow Agent do job nền kích hoạt, không có người chờ (N2 → W4, N1 → W3 / W5, N5 → W6, BQL duyệt xong → resume W2 / W3 / W5 / W6); W5 có bước gọi LLM.
- Template sẵn là FastAPI + LangGraph; đội có 4 tuần.
- **Đã cân nhắc:** App Runner (timeout 120 giây), Lambda (cold start, giới hạn 15 phút), ECS Fargate (tốn công dựng ALB, VPC); chọn EC2 + docker compose vì đơn giản, dễ debug.

## Decision

**Một EC2 ứng dụng** (khởi điểm t3.large, Amazon Linux 2023), docker compose gồm:
`caddy` (reverse proxy, HTTPS tự động, origin của CloudFront) · `api` (FastAPI + uvicorn 2–4 worker; REST, SSE, WebSocket; chạy LangGraph
trong process) · `worker` (arq queue `bg`: N1–N8, cron; **không gọi LLM**; cùng image) · `agent-worker` (arq queue `agent`: `run_workflow`,
`resume_workflow`; có gọi LLM; cùng image) · `redis` (hàng đợi, pub/sub, rate limit, cache ngắn) · `otel-collector` (ADR-0008).

- **Dữ liệu bền ngoài EC2:** Postgres trên RDS (ADR-0005); Redis chỉ giữ dữ liệu mất được. Job quan trọng phải idempotent.
- **Phân tách:** queue `bg` không gọi LLM (import-linter kiểm job `bg` không import `platform.llm`); mọi hành động ảnh hưởng người dùng đi qua workflow Agent; job N không gọi workflow trực tiếp (ADR-0010).
- **Hai queue** để job nhanh không xếp sau lượt gọi LLM chậm, và đặt giới hạn đồng thời riêng cho LLM (`max_jobs` của `agent-worker`).
- **Resume sau HITL** chạy trong `agent-worker`, không trong HTTP request duyệt; checkpointer Postgres của LangGraph giữ trạng thái qua restart.
- **Local giống production:** cùng file compose, thêm `postgres` (image pgvector) thay RDS.

## Consequences

**Tích cực:** Dựng nhanh, rẻ, debug dễ (SSM, `docker compose logs`); không giới hạn thời gian request, hợp SSE và WebSocket. · LLM chậm không làm nghẽn job nền.

**Tiêu cực:** Một máy là điểm hỏng duy nhất, không tự scale (chấp nhận cho demo); đội tự lo vá OS, đĩa, xoay log, `restart: unless-stopped`. · Mở rộng nhiều máy cần ALB và sticky session cho WebSocket (code không đổi nhờ Redis pub/sub); thêm container `agent-worker` phải vận hành.

## Observability Impact

- Instrumentation tự động: `opentelemetry-instrumentation-fastapi`, `-asyncpg`, `-redis`, `-httpx`, `-botocore`.
- Span thủ công: `agent.<wN>.<step>` (ví dụ `agent.w1.check_eligibility`), `worker.<nN>.<job>` (ví dụ `worker.n1.ingest_lpr`).
- `traceparent` đi qua payload job → metadata lần chạy LangGraph, nên span của worker nối được với span đã tạo job.
- Metric (nhãn `queue` chỉ `bg` / `agent`): `arq_queue_depth{queue}`, `arq_job_duration_seconds{queue,job}`, `arq_job_failures_total{queue,job}`; CPU, RAM, đĩa EC2 qua `hostmetrics`. (`outbox_lag_seconds` hoãn cùng outbox.)
