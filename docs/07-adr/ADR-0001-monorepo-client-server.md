# ADR-0001: Monorepo với `client/`, `server/`, `infra/`, `docs/`

- **Status**: Accepted
- **Date**: 2026-11-17 · viết lại 2026-11-22 (plan 021)
- **Liên quan**: [Tech stack](../02-architecture/02-tech-stack.md) · [ADR-0002](ADR-0002-react-vite-spa-on-s3-cloudfront.md) · [ADR-0012](ADR-0012-lean-lightsail-prod-and-team-ci-runner.md) · [Cấu trúc server](../04-development/01-server-structure.md)

## Context

- Đội 4 người, 4 tuần. Repo gốc là template Python (FastAPI + LangGraph) đặt ở gốc: `src/`, `tests/`, `eval/`, `prompts/`.
- Client và server dùng chung contract API (OpenAPI); một tính năng thường sửa cả hai phía.

## Decision

- **Một repo**, bốn thư mục cấp cao: `client/` (React + Vite, ADR-0002), `server/` (FastAPI + LangGraph + arq, ADR-0004),
  `infra/` (runbook AWS CLI, ADR-0012, ADR-0013), `docs/`.
- `eval/` ở lại gốc vì ban tổ chức chấm `eval/results/report.md`.
- Type TypeScript sinh từ OpenAPI của `server/` vào `client/src/api/generated/`.
- CI chạy theo đường dẫn thay đổi: `client/**` chỉ build client, `server/**` chỉ build server. Lệnh chung gom trong `Makefile`.

## Consequences

- **Tích cực:** một PR sửa được cả API và client; lệch contract thì CI bắt; tài liệu, ADR, review ở một nơi.
- **Tiêu cực:** đường dẫn trong `Makefile`, `Dockerfile`, compose, lệnh `pytest` phải theo thư mục con; mỗi bên một bộ công cụ (npm, pip).

## Observability Impact

- Tên dịch vụ OTel theo thư mục: `parksmart-server-api`, `parksmart-server-worker`, `parksmart-server-agent-worker`, `parksmart-client`.
- Image gắn tag git SHA; `service.version` = SHA nên trace truy ngược được về commit.
