# ADR-0003: REST + OpenAPI; SSE cho chat, WebSocket cho thông báo; một domain CloudFront

- **Status**: Accepted
- **Date**: 2026-11-17
- **Liên quan**: [ADR-0002](ADR-0002-react-vite-spa-on-s3-cloudfront.md) · [ADR-0004](ADR-0004-fastapi-langgraph-arq-on-ec2-docker-compose.md) · [ADR-0006](ADR-0006-self-issued-jwt-auth.md)

## Context

- Client cần ba kiểu giao tiếp: CRUD và nghiệp vụ (đặt chỗ, chia sẻ, thỏa thuận, duyệt); stream câu trả lời Agent theo token; server đẩy
  sự kiện xuống (thông báo, trạng thái ô, hàng chờ duyệt, kết quả ghép).
- Toàn bộ hạ tầng trên AWS, không dùng Supabase Realtime, nên realtime phải tự làm.

## Decision

- **API nghiệp vụ:** REST, prefix `/api/v1`, FastAPI tự sinh OpenAPI. Client sinh type và hook bằng `openapi-typescript` + `openapi-fetch`
  (hoặc orval); CI fail nếu bản sinh lệch bản đã commit. Lỗi theo format `{code, message, details, trace_id}`, `code` khớp quy tắc
  nghiệp vụ (ví dụ `BR-01_SCOPE_VIOLATION`).
- **Chat Agent:** SSE qua `POST /api/v1/chat/stream`, client đọc bằng `fetch` (`EventSource` không gửi được body); server ping mỗi 15 giây.
- **Thông báo:** WebSocket `/ws`, xác thực bằng access token trong message đầu (không đặt trên query string); kênh `user:{id}`, `zone:{id}:bql`;
  phát giữa các process qua **Redis pub/sub**. Client tự kết nối lại có backoff rồi gọi REST lấy sự kiện đã lỡ: WebSocket chỉ là kênh báo,
  không phải nguồn dữ liệu. (4 tuần đầu client polling danh sách thông báo, xem backlog.)
- **Một domain CloudFront:** `/*` → S3 (có cache) · `/api/*` → EC2 (tắt cache, chuyển `Authorization`, cookie, `traceparent`) · `/ws` → EC2 (cho upgrade).

## Consequences

**Tích cực**
- Cùng domain nên không có CORS; cookie `SameSite=Strict` dùng được (demo không có refresh token, [ADR-0011](ADR-0011-mvp-simplifications.md)).
- Contract có type từ server tới client; SSE dễ test, dễ đi qua proxy.

**Tiêu cực**
- Tự viết quản lý kết nối WebSocket, đăng ký kênh, kết nối lại; hai cơ chế realtime song song nên test nhiều hơn.
- CloudFront giữ kết nối mặc định 60 giây nên bắt buộc ping; stream chat dài cần kiểm thực tế.

## Observability Impact

- **RED cho HTTP**, nhãn chỉ dùng route template (`/api/v1/bookings/{id}`): `http_server_request_duration_seconds` (histogram, exemplar
  `trace_id`), `http_server_requests_total`.
- **WebSocket:** `ws_connections_active` (gauge), `ws_messages_sent_total{event_type}`. **SSE:** `chat_stream_duration_seconds`, `chat_stream_first_token_seconds`.
- Sự kiện phát qua Redis mang `traceparent`, nên span phía WebSocket nối được với span đã sinh sự kiện.
