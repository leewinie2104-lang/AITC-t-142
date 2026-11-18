# ADR-0004: Server FastAPI + LangGraph và worker arq + Redis, chạy bằng docker compose trên EC2

- **Status**: Accepted
- **Date**: 2026-11-17
- **Cập nhật 2026-11-17**: tách queue `bg` / `agent` và thêm service `agent-worker`. Lý do: N1 kích hoạt W5, mà W5 có bước gọi LLM ([ADR-0010](ADR-0010-backend-modules-agent-workflows-jobs.md))
- **Liên quan**: [ADR-0003](ADR-0003-rest-openapi-sse-websocket-single-domain.md) · [ADR-0005](ADR-0005-rds-postgres-asyncpg-rls-alembic-sql.md) · [ADR-0010](ADR-0010-backend-modules-agent-workflows-jobs.md) · [Workflow AI Agent](../01-product/backlog/02-agent-workflows.md) · [Workflow nền](../01-product/backlog/03-background-workflows.md)

## Context

- **Agent (W0–W7):**
  - Cần stream câu trả lời.
  - Có bước dừng chờ BQL duyệt (HITL) rồi chạy tiếp, có thể sau vài giờ.
- **Worker nền (N1–N8):** nhận sự kiện LPR, chạy job định kỳ và job hằng đêm.
- **Workflow Agent chạy nền:** một số workflow Agent được kích hoạt từ workflow nền, không có người dùng ngồi chờ:
  - N2 → W4.
  - N1 → W3 / W5.
  - N5 → W6.
  - BQL duyệt xong → resume W2 / W3 / W5 / W6.

  W5 có bước gọi LLM (đọc ảnh, tóm tắt).
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
| `worker` | arq, queue `bg`: N1–N8, cron, relay outbox. **Không gọi LLM.** Cùng image với `api`, khác lệnh khởi động |
| `agent-worker` | arq, queue `agent`: `run_workflow` (W kích hoạt từ N hoặc từ app), `resume_workflow` (sau khi BQL duyệt). Có gọi LLM. Cùng image |
| `redis` | Hàng đợi arq (`bg`, `agent`), pub/sub cho WebSocket, rate limit, cache ngắn hạn |
| `otel-collector` | Agent gom telemetry, đẩy sang EC2 observability (ADR-0008) |

**Nguyên tắc:**
- **Dữ liệu bền nằm ngoài EC2:** Postgres trên RDS (ADR-0005), Redis chỉ giữ dữ liệu có thể mất. Job quan trọng phải idempotent (ví dụ chống trùng theo mã sự kiện LPR) để chạy lại an toàn.
- **Phân tách trách nhiệm:**
  - Queue `bg` không gọi LLM. CI kiểm tra bằng import-linter: job `bg` không được import `platform.llm`.
  - Mọi hành động ảnh hưởng tới người dùng đi qua workflow Agent (theo backlog).
  - Job N chỉ phát sự kiện vào **outbox**. Handler của sự kiện enqueue workflow vào queue `agent`; job N không gọi workflow trực tiếp (ADR-0010).
- **Tách hai queue để:**
  - Job nền nhanh (N1) không phải xếp hàng sau lượt gọi LLM chậm.
  - Đặt được giới hạn đồng thời riêng cho LLM (`max_jobs` của `agent-worker`), tránh vượt quota Bedrock.
- **Resume sau HITL chạy trong `agent-worker`**, không chạy trong HTTP request duyệt. Request duyệt trả về ngay; kết quả báo về client qua WebSocket.
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
- Thêm một container (`agent-worker`) và một relay outbox phải vận hành. Đổi lại, LLM chậm không làm nghẽn job nền.

## Observability Impact

- **Instrumentation tự động:** `opentelemetry-instrumentation-fastapi`, `-asyncpg`, `-redis`, `-httpx`, `-botocore`.
- **Span thủ công:**
  - Mỗi bước workflow: `agent.<wN>.<step>`, ví dụ `agent.w1.check_eligibility`, `agent.w2.match`.
  - Mỗi job arq: `worker.<nN>.<job>`, ví dụ `worker.n1.ingest_lpr`.

  Tên span viết thường, khớp ADR-0010.
- **`traceparent` đi qua hàng đợi:** truyền theo đường outbox row → payload job → metadata của lần chạy LangGraph. Nhờ vậy span của worker và `agent-worker` nối được với span đã tạo job.
- **Metric USE cho tài nguyên** (nhãn `queue` chỉ có `bg` hoặc `agent`):
  - `arq_queue_depth{queue}` (gauge)
  - `arq_job_duration_seconds{queue,job}` (histogram)
  - `arq_job_failures_total{queue,job}`
  - `outbox_lag_seconds` (gauge)
  - CPU, RAM, đĩa của EC2 lấy qua `hostmetrics` receiver của collector.
