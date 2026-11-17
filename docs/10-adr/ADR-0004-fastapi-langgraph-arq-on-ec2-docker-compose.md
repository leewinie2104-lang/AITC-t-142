# ADR-0004: Server FastAPI + LangGraph và worker arq + Redis, chạy bằng docker compose trên EC2

- **Status**: Accepted
- **Date**: 2026-11-17
- **Liên quan**: [ADR-0003](ADR-0003-rest-openapi-sse-websocket-single-domain.md) · [ADR-0005](ADR-0005-rds-postgres-asyncpg-rls-alembic-sql.md) · [Workflow AI Agent](../01-product/backlog/agent-workflows.md) · [Workflow nền](../01-product/backlog/background-workflows.md)

## Context

- **Agent (W0–W7):**
  - Cần stream câu trả lời.
  - Có bước dừng chờ BQL duyệt (HITL) rồi chạy tiếp, có thể sau vài giờ.
- **Worker nền (N1–N8):** nhận sự kiện LPR, chạy job định kỳ và job hằng đêm.
- **Ràng buộc:** template sẵn có là FastAPI + LangGraph; đội có 4 tuần.
- **Các lựa chọn đã cân nhắc:**
  - App Runner: request timeout 120s, không hợp worker chạy lâu dài.
  - Lambda: cold start, giới hạn 15 phút.
  - ECS Fargate: tốn công dựng ALB và VPC.
  - EC2 + docker compose: đội chọn phương án này vì đơn giản và dễ debug.

## Decision

**Một EC2 cho ứng dụng** (khởi điểm t3.large, AMI Amazon Linux 2023), chạy docker compose gồm:

| Service | Vai trò |
|---------|---------|
| `caddy` | Reverse proxy, HTTPS tự động (Let's Encrypt) làm origin cho CloudFront; chuyển tiếp `/api/*` và `/ws` |
| `api` | FastAPI + uvicorn (2–4 worker process); REST, SSE, WebSocket; chạy LangGraph trong process |
| `worker` | arq: N1–N8, cron; cùng image với `api`, khác lệnh khởi động |
| `redis` | Hàng đợi arq, pub/sub cho WebSocket, rate limit, cache ngắn hạn |
| `otel-collector` | Agent gom telemetry, đẩy sang EC2 observability (ADR-0008) |

**Nguyên tắc:**
- **Dữ liệu bền nằm ngoài EC2:** Postgres trên RDS (ADR-0005), Redis chỉ giữ dữ liệu có thể mất. Job quan trọng phải idempotent (ví dụ chống trùng theo mã sự kiện LPR) để chạy lại an toàn.
- **Phân tách trách nhiệm:** worker không gọi LLM. Mọi hành động ảnh hưởng tới người dùng đi qua workflow Agent (theo backlog).
- **Bước chờ duyệt:** dùng checkpointer Postgres của LangGraph, nên checkpoint không mất khi khởi động lại container.
- **Local giống production:** cùng file compose, chỉ thêm `postgres` (image pgvector) thay cho RDS.

## Consequences

**Tích cực**
- Dựng nhanh, rẻ, debug dễ (SSH qua SSM, `docker compose logs`). Môi trường local gần giống hệt production.
- Không bị giới hạn thời gian request, phù hợp với SSE và WebSocket.

**Tiêu cực**
- Một máy là một điểm hỏng duy nhất; không tự scale. Chấp nhận được cho demo.
- Đội phải tự lo vá hệ điều hành, dung lượng đĩa, xoay vòng log và khởi động lại khi máy reboot (`restart: unless-stopped`).
- Mở rộng ra nhiều máy sau này cần thêm ALB và sticky session cho WebSocket. Nhờ Redis pub/sub nên không phải đổi code.

## Observability Impact

- **Instrumentation tự động:** `opentelemetry-instrumentation-fastapi`, `-asyncpg`, `-redis`, `-httpx`, `-botocore`.
- **Span thủ công** cho mỗi node LangGraph (`agent.W1.route`, `agent.W2.match`…) và mỗi job arq (`worker.N1.ingest_lpr`).
- **`trace_id` đi qua hàng đợi:** truyền trong payload job, nên span của worker nối được với span của API đã tạo job.
- **Metric USE cho tài nguyên:**
  - `arq_queue_depth` (gauge)
  - `arq_job_duration_seconds{job}` (histogram)
  - `arq_job_failures_total{job}`
  - CPU, RAM, đĩa của EC2 lấy qua `hostmetrics` receiver của collector.
