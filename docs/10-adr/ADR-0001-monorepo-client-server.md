# ADR-0001: Monorepo với hai thư mục `client/` và `server/`

- **Status**: Accepted
- **Date**: 2026-11-17
- **Liên quan**: [Tech stack](../02-architecture/02-tech-stack.md) · [ADR-0003](ADR-0003-rest-openapi-sse-websocket-single-domain.md) · [ADR-0009](ADR-0009-terraform-github-actions-ecr-ssm.md)

## Context

- Đội gồm 4 người, có 4 tuần để làm bản demo ParkSmart AI.
- Repo hiện tại là template Python (FastAPI + LangGraph). Code template đặt ở gốc repo: `src/`, `tests/`, `eval/`, `prompts/`.
- Client và server phải dùng chung contract API (OpenAPI). Một tính năng thường phải sửa cả hai phía cùng lúc.

## Decision

- Giữ **một repo**, chia hai thư mục cấp cao nhất:
  ```
  client/     # React + Vite SPA (ADR-0002)
  server/     # FastAPI + LangGraph + worker arq (ADR-0004); chứa src/, tests/, eval/, prompts/ của template
  infra/      # Terraform (ADR-0009)
  docs/
  ```
- Contract API được sinh từ `server/` (OpenAPI). Type TypeScript sinh ra nằm trong `client/src/api/generated/`.
- CI chạy theo đường dẫn thay đổi: thay đổi trong `client/**` chỉ build client; thay đổi trong `server/**` chỉ build server.
- Việc chuyển code template từ gốc repo vào `server/` đã làm ở plan 007 (2026-11-17). Riêng `eval/` ở lại gốc repo vì BTC chấm `eval/results/report.md`. Cấu trúc chi tiết: [01-server-structure.md](../05-development/01-server-structure.md).

## Consequences

**Tích cực**
- Một PR có thể sửa API và client cùng lúc. Khi đổi schema, CI phát hiện ngay chỗ lệch contract.
- Chỉ có một nơi chứa tài liệu, ADR và quy trình review.

**Tiêu cực**
- Phải sửa đường dẫn trong `Makefile`, `Dockerfile`, `docker-compose.yml`, CLAUDE.md và các lệnh `pytest`, `uvicorn`.
- Mỗi bên có công cụ riêng (npm cho client, pip cho server), nên lệnh chạy ở thư mục gốc cần `Makefile` gom lại.

## Observability Impact

- Tên dịch vụ trong OpenTelemetry thống nhất theo thư mục: `parksmart-server-api`, `parksmart-server-worker`, `parksmart-server-agent-worker` (ADR-0004), `parksmart-client`.
- Image Docker gắn tag theo git SHA. Thuộc tính `service.version` lấy từ SHA, nên một trace luôn truy ngược được về commit.
