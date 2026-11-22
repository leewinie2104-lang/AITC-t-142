# Tech stack ban đầu — ParkSmart AI

> Chốt ngày 2026-11-17, qua phỏng vấn đội (4 người, 4 tuần). Mỗi quyết định có một ADR trong [docs/07-adr/](../07-adr/).
> Sơ đồ: [01-architecture-diagram.md](01-architecture-diagram.md) · Backlog: [05-backlog.md](../01-product/05-backlog.md)

![Tech stack ban đầu](../images/ParkSmartAI-arch-tech-stack.png)

**Các ảnh khác:**
- [Kiến trúc tổng quan trên AWS](../images/ParkSmartAI-arch-overview.png)
- [Client ↔ server giao tiếp thế nào](../images/ParkSmartAI-arch-communication.png)
- [CI/CD và hạ tầng](../images/ParkSmartAI-arch-cicd.png)
- [Quan sát hệ thống](../images/ParkSmartAI-arch-observability.png)
- [Cấu trúc thư mục server + ví dụ module sharing/](../images/ParkSmartAI-arch-backend-folders.png)

## Stack theo lớp

| Lớp | Lựa chọn | ADR |
|-----|----------|-----|
| Repo | Monorepo: `client/`, `server/`, `infra/`, `docs/` | [0001](../07-adr/ADR-0001-monorepo-client-server.md) |
| Client | React + TypeScript + Vite (SPA); Tailwind + shadcn/ui; TanStack Query; React Router | [0002](../07-adr/ADR-0002-react-vite-spa-on-s3-cloudfront.md) |
| Host client | S3 (private, OAC) + CloudFront | [0002](../07-adr/ADR-0002-react-vite-spa-on-s3-cloudfront.md) |
| API | REST `/api/v1` + OpenAPI; client TypeScript sinh từ OpenAPI | [0002](../07-adr/ADR-0002-react-vite-spa-on-s3-cloudfront.md) |
| Realtime | SSE cho chat Agent; WebSocket `/ws` cho thông báo, phát qua Redis pub/sub | [0002](../07-adr/ADR-0002-react-vite-spa-on-s3-cloudfront.md) |
| Domain | Một domain: `/` → client (S3 + CloudFront, chưa deploy), `/api/*` và `/ws` → máy app | [0002](../07-adr/ADR-0002-react-vite-spa-on-s3-cloudfront.md) |
| Server | FastAPI + uvicorn; LangGraph chạy trong process | [0004](../07-adr/ADR-0004-fastapi-langgraph-arq-on-ec2-docker-compose.md) |
| Worker | arq + Redis, hai queue: `bg` (N1–N9, không gọi LLM) và `agent` (W chạy nền, resume sau HITL) | [0004](../07-adr/ADR-0004-fastapi-langgraph-arq-on-ec2-docker-compose.md) |
| Cấu trúc server | Module Clean Architecture (M1–M14); `agent/` điều phối W0–W7; job N1–N9 là delivery adapter; import-linter; demo không có outbox, dùng port `publish()` ([ADR-0011](../07-adr/ADR-0011-mvp-simplifications.md)) | [0010](../07-adr/ADR-0010-backend-modules-agent-workflows-jobs.md) |
| Runtime | Demo: docker compose trên một Lightsail (caddy, api, redis, postgres; worker sau profile `workers`). Dev: api / worker chạy trên máy dev | [0004](../07-adr/ADR-0004-fastapi-langgraph-arq-on-ec2-docker-compose.md) · [0012](../07-adr/ADR-0012-lean-lightsail-prod-and-team-ci-runner.md) · [0013](../07-adr/ADR-0013-dev-env-on-ci-runner-and-groq.md) |
| DB | PostgreSQL 16 + pgvector, pgcrypto, btree_gist. Demo: container trên Lightsail; dev: container dùng chung trên máy runner CI (Tailscale). RDS khi có người dùng thật | [0005](../07-adr/ADR-0005-rds-postgres-asyncpg-rls-alembic-sql.md) · [0012](../07-adr/ADR-0012-lean-lightsail-prod-and-team-ci-runner.md) · [0013](../07-adr/ADR-0013-dev-env-on-ci-runner-and-groq.md) |
| Truy cập dữ liệu | asyncpg + SQL viết tay (ORM chỉ cho CRUD đơn giản); RLS theo khu / hộ | [0005](../07-adr/ADR-0005-rds-postgres-asyncpg-rls-alembic-sql.md) |
| Migration | Alembic, nội dung viết bằng SQL thuần | [0005](../07-adr/ADR-0005-rds-postgres-asyncpg-rls-alembic-sql.md) |
| Checkpointer Agent | `langgraph-checkpoint-postgres` (psycopg 3, pool riêng) | [0005](../07-adr/ADR-0005-rds-postgres-asyncpg-rls-alembic-sql.md) |
| Auth | JWT tự phát hành (ES256, argon2id, demo: chỉ access JWT hạn 8 giờ, không refresh token, theo [ADR-0011](../07-adr/ADR-0011-mvp-simplifications.md)) | [0006](../07-adr/ADR-0006-self-issued-jwt-auth.md) |
| LLM | Dev: Groq qua API tương thích OpenAI (`ChatOpenAI` + `LLM_BASE_URL`). Demo dự kiến: Claude qua Amazon Bedrock (Opus 5.5, Sonnet 5.5 làm judge) | [0007](../07-adr/ADR-0007-claude-via-amazon-bedrock.md) |
| Quan sát hệ thống | Chưa có OTel. Khi thêm: OpenTelemetry → Grafana Cloud free (không dựng LGTM riêng); trace LLM: LangSmith | [0008](../07-adr/ADR-0008-opentelemetry-lgtm-on-dedicated-ec2.md) · [0012](../07-adr/ADR-0012-lean-lightsail-prod-and-team-ci-runner.md) |
| Hạ tầng | AWS CLI theo runbook trong `infra/` (lightsail, ci-runner, dev-db), chưa Terraform | [0012](../07-adr/ADR-0012-lean-lightsail-prod-and-team-ci-runner.md) |
| CI/CD | GitHub Actions trên runner riêng `team-142` (EC2); merge `main` → OIDC → ECR, Lightsail tự kéo image; merge `dev` → migrate DB dev | [0012](../07-adr/ADR-0012-lean-lightsail-prod-and-team-ci-runner.md) · [0013](../07-adr/ADR-0013-dev-env-on-ci-runner-and-groq.md) |
| Bí mật | Prod: `/opt/parksmart/.env` trên máy (chmod 600). Dev: `.env` từng máy, chia qua Bitwarden. CI: GitHub secrets | [0012](../07-adr/ADR-0012-lean-lightsail-prod-and-team-ci-runner.md) · [0013](../07-adr/ADR-0013-dev-env-on-ci-runner-and-groq.md) |

## Môi trường

| Môi trường | Thành phần | Ghi chú |
|------------|-----------|---------|
| `dev` | api / worker chạy trên máy dev (`make run`); Postgres + Redis dùng chung trên máy runner CI qua Tailscale ([infra/dev-db](../../infra/dev-db/README.md)); client chạy `vite dev` | LLM qua Groq; chỉ CI migrate DB dùng chung ([ADR-0013](../07-adr/ADR-0013-dev-env-on-ci-runner-and-groq.md)) |
| `local` | docker compose ở gốc repo: api, worker, agent-worker, redis, postgres (pgvector); mẫu cho demo/prod, dùng khi thử migration | Cùng biến `.env`; compose ghi đè `DATABASE_URL` / `REDIS_URL` sang container |
| `demo` | Một Lightsail `small_3_0`: caddy, api, redis, postgres ([infra/lightsail](../../infra/lightsail/README.md)) | Dựng bằng AWS CLI theo runbook (plan 015); `pg_dump` hằng đêm lên S3 |

## Rủi ro và việc cần xác nhận

| # | Nội dung | Ảnh hưởng | Xử lý |
|---|----------|-----------|-------|
| R1 | (Khi chuyển sang Bedrock) Haiku / Sonnet / Opus 5.5 có ở region đã chọn không, có cần cross-region inference không; quota | Không gọi được LLM, hoặc vướng tuân thủ dữ liệu | Kiểm tra trong tuần 1; xin tăng quota sớm (ADR-0007) |
| R2 | SSE / WebSocket qua CloudFront bị cắt khi chờ lâu | Chat bị ngắt giữa chừng | Gửi ping 15s; test sớm trên môi trường `demo` |
| R3 | Hai driver Postgres (asyncpg + psycopg 3) cùng dùng giới hạn kết nối của Postgres (`max_connections`, máy 2 GB) | Hết kết nối | Đặt giới hạn pool cụ thể; theo dõi `db_client_connections_in_use` |
| R4 | Auth tự viết | Lỗ hổng bảo mật | Bộ test auth bắt buộc; review riêng (ADR-0006) |
| R5 | Một Lightsail là điểm hỏng duy nhất, DB cùng máy | Demo chết nếu máy chết | Runbook dựng lại; khôi phục từ `pg_dump` đêm trước trên S3 (ADR-0012) |
| R6 | ~~Code template còn ở gốc repo~~ **Đã xử lý (plan 007)** | — | Code ở `server/src/app/`; xem [01-server-structure.md](../04-development/01-server-structure.md) |
| R7 | LangGraph chạy lại toàn bộ node chứa `interrupt()` khi resume sau HITL | Giữ chỗ, ghi xác nhận (`consent_record`) hoặc thanh toán bị chạy hai lần | Node chờ duyệt không có tác dụng phụ; `idempotency_key = thread_id:step` có unique constraint ở từng bảng đích (ADR-0010, ADR-0011) |

## Gợi ý chia việc (4 người)

| Vai trò | Phụ trách |
|---------|-----------|
| **Server core** | Schema, RLS, migration, auth, rule engine, API REST, bằng chứng xác nhận |
| **AI Agent** | W0–W7, LLM (Groq khi dev, Bedrock khi demo), ẩn danh, checkpointer / HITL, RAG nội quy, eval |
| **Client** | SPA cho cư dân và BQL, client sinh từ OpenAPI, SSE; thông báo bằng polling trong 4 tuần (WebSocket sau) |
| **Hạ tầng và vận hành** | Runner CI, deploy Lightsail, DB dev dùng chung, worker N1, N2, N9 (N3–N8 sau 4 tuần), bộ log LPR mô phỏng |

Thứ tự triển khai tính năng theo [backlog](../01-product/05-backlog.md): làm hết **Ưu tiên 1** (hết tuần 2) trước, sau đó **Ưu tiên 2** (trước demo); **Ưu tiên 3** chỉ làm nếu còn thời gian. Việc từng người theo tuần: lọc theo cột trong [Backlog §2](../01-product/05-backlog.md#2-tính-năng).
