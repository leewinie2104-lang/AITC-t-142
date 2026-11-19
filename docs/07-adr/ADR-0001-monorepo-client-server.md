# ADR-0001: Monorepo với hai thư mục `client/` và `server/`

- **Status**: Accepted
- **Date**: 2026-11-17
- **Liên quan**: [Tech stack](../02-architecture/02-tech-stack.md) · [ADR-0003](ADR-0003-rest-openapi-sse-websocket-single-domain.md) · [ADR-0009](ADR-0009-terraform-github-actions-ecr-ssm.md)

## Context

- Đội 4 người, 4 tuần làm bản demo. Repo ban đầu là template Python (FastAPI + LangGraph) đặt ở gốc: `src/`, `tests/`, `eval/`, `prompts/`.
- Client và server dùng chung contract API (OpenAPI); một tính năng thường sửa cả hai phía cùng lúc.

## Decision

- Giữ **một repo**, bốn thư mục cấp cao: `client/` (React + Vite, ADR-0002), `server/` (FastAPI + LangGraph + worker arq, ADR-0004;
  chứa `src/`, `tests/`, `prompts/` của template), `infra/` (Terraform, ADR-0009), `docs/`.
- Contract API sinh từ `server/` (OpenAPI); type TypeScript sinh vào `client/src/api/generated/`.
- CI chạy theo đường dẫn thay đổi: `client/**` chỉ build client, `server/**` chỉ build server.
- Code template đã chuyển vào `server/` ở plan 007; riêng `eval/` ở lại gốc vì ban tổ chức chấm `eval/results/report.md`.
  Cấu trúc chi tiết: [01-server-structure](../04-development/01-server-structure.md).

## Consequences

**Tích cực**
- Một PR sửa được cả API và client; đổi schema thì CI bắt ngay chỗ lệch contract.
- Một nơi chứa tài liệu, ADR và quy trình review.

**Tiêu cực**
- Phải sửa đường dẫn trong `Makefile`, `Dockerfile`, `docker-compose.yml`, `CLAUDE.md`, lệnh `pytest`, `uvicorn`.
- Mỗi bên có công cụ riêng (npm, pip), nên lệnh ở gốc cần `Makefile` gom lại.

## Observability Impact

- Tên dịch vụ OTel theo thư mục: `parksmart-server-api`, `parksmart-server-worker`, `parksmart-server-agent-worker`, `parksmart-client`.
- Image Docker gắn tag git SHA; `service.version` lấy từ SHA nên mọi trace truy ngược được về commit.
