# ADR-0002: Client React (Vite) SPA; API REST + OpenAPI, SSE cho chat, WebSocket cho thông báo, một domain

- **Status**: Accepted (gộp ADR-0003 ngày 2026-11-22, plan 021)
- **Date**: 2026-11-17 · viết lại 2026-11-22
- **Liên quan**: [ADR-0004](ADR-0004-fastapi-langgraph-arq-on-ec2-docker-compose.md) · [ADR-0006](ADR-0006-self-issued-jwt-auth.md) · [ADR-0012](ADR-0012-lean-lightsail-prod-and-team-ci-runner.md) · [Wireframes](../01-product/ux/wireframes/README.md)

## Context

- Cư dân dùng điện thoại; bảo vệ và BQL dùng máy tính. Mọi màn hình đều cần đăng nhập nên không cần SEO / SSR.
- Ba kiểu giao tiếp: nghiệp vụ (đặt chỗ, chia sẻ, duyệt), stream câu trả lời Agent theo token, server đẩy thông báo xuống.

## Decision

- **Client:** React + TypeScript, build bằng Vite; SPA mobile-first. Tailwind + shadcn/ui, TanStack Query, React Router tách route
  theo vai trò (cư dân / người thuê, bảo vệ, BQL khu, vận hành chuỗi).
- **API nghiệp vụ:** REST `/api/v1`, FastAPI sinh OpenAPI; client sinh type bằng `openapi-typescript`; CI fail nếu bản sinh lệch.
  Lỗi theo dạng `{code, message, details, trace_id}`, `code` khớp quy tắc nghiệp vụ (ví dụ `BR-01_SCOPE_VIOLATION`).
- **Chat Agent:** SSE qua `POST /api/v1/chat/stream`, đọc bằng `fetch`; server ping mỗi 15 giây.
- **Thông báo:** demo dùng polling `GET /me/notifications`. Sau đó: WebSocket `/ws` (token trong message đầu), phát giữa các
  process qua Redis pub/sub; WebSocket chỉ là kênh báo, dữ liệu vẫn lấy qua REST.
- **Một domain:** client và API cùng origin nên không cần CORS. Host client: S3 + CloudFront (`/*` → S3, `/api/*`, `/ws` → máy
  app). Chưa deploy: Caddy trên máy prod hiện chỉ phục vụ backend (ADR-0012).
- **Token:** access token chỉ giữ trong bộ nhớ, không `localStorage` (ADR-0006).

## Consequences

- **Tích cực:** host rẻ, deploy là chép file tĩnh; contract có type từ server tới client; SSE dễ test và đi qua proxy.
- **Tiêu cực:** không SSR nên trang đầu chậm hơn; tự làm bảo vệ route; realtime thật (WebSocket) phải tự viết kết nối lại và
  đăng ký kênh; proxy giữ kết nối có giới hạn nên bắt buộc ping.

## Observability Impact

- OTel Web SDK gắn `traceparent` vào mọi `fetch`, trace đi từ trình duyệt → API → DB → LLM.
- RED cho HTTP với nhãn route template (`/api/v1/bookings/{id}`): `http_server_request_duration_seconds` (exemplar), `http_server_requests_total`.
- SSE: `chat_stream_duration_seconds`, `chat_stream_first_token_seconds`. Lỗi JS gửi về `/api/v1/client-logs` kèm `trace_id`, không token, không biển số.
