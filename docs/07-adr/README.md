# 07-adr — Quyết định kiến trúc (ADR)

> **Thư mục này trả lời:** vì sao hệ thống được làm như hiện tại, và quyết định nào đã chốt.

## Tổng quan

Mỗi ADR ghi lại **một** quyết định quan trọng: bối cảnh, lựa chọn, hệ quả. Khi tài liệu khác mâu thuẫn với một ADR đang Accepted, ADR đúng hơn (code vẫn đúng hơn ADR). Hiện có 11 ADR, đều **Accepted**. ADR-0004, 0005, 0006, 0010 bị thay thế một phần bởi ADR-0011.

## Danh sách

| ADR | Quyết định |
|---|---|
| [0001](ADR-0001-monorepo-client-server.md) | Monorepo, chia `client/` và `server/` |
| [0002](ADR-0002-react-vite-spa-on-s3-cloudfront.md) | Client React (Vite) SPA trên S3 + CloudFront |
| [0003](ADR-0003-rest-openapi-sse-websocket-single-domain.md) | REST + OpenAPI; SSE cho chat; WebSocket cho thông báo; một domain |
| [0004](ADR-0004-fastapi-langgraph-arq-on-ec2-docker-compose.md) | FastAPI + LangGraph, worker arq + Redis, docker compose trên EC2 (partly superseded by 0011: outbox) |
| [0005](ADR-0005-rds-postgres-asyncpg-rls-alembic-sql.md) | RDS PostgreSQL + pgvector, asyncpg, RLS theo khu / hộ, Alembic SQL thuần (partly superseded by 0011: outbox, idempotency_keys, sổ cái hash) |
| [0006](ADR-0006-self-issued-jwt-auth.md) | JWT tự phát hành trong FastAPI (partly superseded by 0011: refresh token, nơi lưu OTP) |
| [0007](ADR-0007-claude-via-amazon-bedrock.md) | Claude qua Amazon Bedrock (region chưa chốt) |
| [0008](ADR-0008-opentelemetry-lgtm-on-dedicated-ec2.md) | OpenTelemetry + LGTM trên EC2 riêng |
| [0009](ADR-0009-terraform-github-actions-ecr-ssm.md) | Terraform; GitHub Actions → ECR → EC2 qua SSM |
| [0010](ADR-0010-backend-modules-agent-workflows-jobs.md) | Server theo module; `agent/` điều phối W0–W7; job N1–N8 là delivery adapter (partly superseded by 0011: outbox) |
| [0011](ADR-0011-mvp-simplifications.md) | Đơn giản hóa schema demo còn 23 bảng; thêm `ai_decision_log` |

Đọc theo nhóm: hạ tầng 0001, 0002, 0004, 0009 · dữ liệu và bảo mật 0005, 0006, 0011 · giao tiếp 0003 · AI 0007, 0010 · quan sát 0008.

## Cấu trúc một ADR

Tên file: `ADR-NNNN-<tên-kebab-case>.md`, số tăng dần. Mỗi file có: **Status** (Proposed / Accepted / Deprecated / Superseded), **Context**, **Decision**, **Consequences**, **Observability Impact**. Nội dung viết tiếng Việt như các ADR hiện có.

## Khi nào viết ADR mới

- Chọn thư viện, dịch vụ hoặc hạ tầng mới.
- Đổi kiến trúc, mô hình dữ liệu, cách dùng LLM.
- Muốn đổi một quyết định đã Accepted.

## Quy tắc

- Không sửa phần quyết định của ADR đã Accepted. Viết ADR mới và đánh dấu bản cũ là **Superseded**.
- Dùng skill `new-adr`: lấy số kế tiếp, theo mẫu, đăng ký vào bảng trên và [docs/README.md](../README.md).
