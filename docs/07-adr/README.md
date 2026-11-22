# 07-adr — Quyết định kiến trúc (ADR)

> **Thư mục này trả lời:** vì sao hệ thống được làm như hiện tại, và quyết định nào đang có hiệu lực.

## Tổng quan

Mỗi ADR ghi **quyết định đang có hiệu lực** cho một chủ đề: bối cảnh, lựa chọn, hệ quả. Khi tài liệu khác mâu thuẫn với ADR
đang Accepted, ADR đúng hơn (code vẫn đúng hơn ADR). Plan 021 (2026-11-22) đã viết lại các ADR thành quyết định hiện hành.
Hiện có **12 ADR Accepted**; ADR-0003 gộp vào 0002, ADR-0009 gộp vào 0012 (hai file cũ chỉ còn dòng trỏ sang). Lịch sử xem git.

## Danh sách

| ADR | Quyết định | Status |
|---|---|---|
| [0001](ADR-0001-monorepo-client-server.md) | Monorepo: `client/`, `server/`, `infra/`, `docs/`; `eval/` ở gốc | Accepted |
| [0002](ADR-0002-react-vite-spa-on-s3-cloudfront.md) | Client React (Vite) SPA; REST + OpenAPI, SSE cho chat, thông báo polling rồi WebSocket; một domain | Accepted |
| [0003](ADR-0003-rest-openapi-sse-websocket-single-domain.md) | *(gộp vào 0002)* | Superseded |
| [0004](ADR-0004-fastapi-langgraph-arq-on-ec2-docker-compose.md) | FastAPI + LangGraph, arq hai queue (`bg` không LLM, `agent`), docker compose | Accepted |
| [0005](ADR-0005-rds-postgres-asyncpg-rls-alembic-sql.md) | Postgres 16 + pgvector, asyncpg SQL-first, RLS theo khu / hộ, Alembic SQL thuần, chỉ CI migrate | Accepted |
| [0006](ADR-0006-self-issued-jwt-auth.md) | JWT tự phát hành (demo 8 giờ), argon2id, OTP thỏa thuận trong Redis | Accepted |
| [0007](ADR-0007-claude-via-amazon-bedrock.md) | LLM: Groq khi dev, Claude qua Bedrock khi demo; ẩn danh trong `LLMPort` | Accepted |
| [0008](ADR-0008-opentelemetry-lgtm-on-dedicated-ec2.md) | OpenTelemetry gửi lên Grafana Cloud free; LGTM tự dựng để sau | Accepted |
| [0009](ADR-0009-terraform-github-actions-ecr-ssm.md) | *(gộp vào 0012)* | Superseded |
| [0010](ADR-0010-backend-modules-agent-workflows-jobs.md) | Server theo module; `agent/` điều phối W0–W7; job N1–N9 là delivery adapter | Accepted |
| [0011](ADR-0011-mvp-simplifications.md) | Schema demo 25 bảng; thêm `ai_decision_log` | Accepted |
| [0012](ADR-0012-lean-lightsail-prod-and-team-ci-runner.md) | Prod một Lightsail, deploy kéo từ ECR qua OIDC, runner CI riêng, AWS CLI theo runbook | Accepted |
| [0013](ADR-0013-dev-env-on-ci-runner-and-groq.md) | Dev: Postgres + Redis dùng chung trên máy runner CI qua Tailscale | Accepted |
| [0014](ADR-0014-eta-location-and-renter-priority-on-early-return.md) | Chủ về sớm: ETA từ vị trí qua port (mock khi demo), người thuê được ưu tiên | Accepted |

Đọc theo nhóm: hạ tầng 0001, 0004, 0012, 0013 · dữ liệu và bảo mật 0005, 0006, 0011 · client và API 0002 · AI 0007, 0010 · nghiệp vụ 0014 · quan sát 0008.

## Cấu trúc một ADR

Tên file `ADR-NNNN-<tên-kebab-case>.md`, số tăng dần, **tối đa 50 dòng**. Mỗi file có **Status**, **Context**, **Decision**,
**Consequences**, **Observability Impact**; thêm *Alternatives considered*, *Cần xác nhận* khi cần. Viết tiếng Việt.

## Khi nào viết ADR mới

- Chọn thư viện, dịch vụ hoặc hạ tầng mới.
- Đổi kiến trúc, mô hình dữ liệu, cách dùng LLM, hoặc một quy tắc nghiệp vụ lớn.
- Muốn đổi một quyết định đã Accepted.

## Quy tắc

- **Đổi quyết định:** viết ADR mới, đánh dấu bản cũ **Superseded by ADR-XXXX**.
- **Bổ sung chi tiết cùng chủ đề:** sửa thẳng ADR đang có hiệu lực để nó luôn nói quyết định hiện hành; không viết "partly superseded".
- Hai ADR trùng chủ đề thì gộp: giữ một file, file kia thành dòng trỏ sang (giữ link cũ).
- Dùng skill `new-adr`; đăng ký vào bảng trên và [docs/README.md](../README.md).
