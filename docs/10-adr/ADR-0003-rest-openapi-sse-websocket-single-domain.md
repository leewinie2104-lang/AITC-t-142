# ADR-0003: REST + OpenAPI; SSE cho chat, WebSocket cho thông báo; một domain CloudFront

- **Status**: Accepted
- **Date**: 2026-11-17
- **Liên quan**: [ADR-0002](ADR-0002-react-vite-spa-on-s3-cloudfront.md) · [ADR-0004](ADR-0004-fastapi-langgraph-arq-on-ec2-docker-compose.md) · [ADR-0006](ADR-0006-self-issued-jwt-auth.md)

## Context

- Client cần ba kiểu giao tiếp với server:
  - Thao tác CRUD và nghiệp vụ: đặt chỗ, chia sẻ, thỏa thuận, duyệt.
  - Stream câu trả lời của Agent theo từng token.
  - Đẩy sự kiện từ server xuống: thông báo, trạng thái ô, hàng chờ BQL duyệt, kết quả ghép.
- Không dùng Supabase Realtime (toàn bộ hạ tầng trên AWS), nên realtime phải tự làm.

## Decision

**API nghiệp vụ**
- Dùng REST, prefix `/api/v1`. FastAPI tự sinh OpenAPI.
- Client sinh type và hook từ OpenAPI bằng `openapi-typescript` + `openapi-fetch` (hoặc orval). CI fail nếu bản sinh ra lệch với bản đã commit.
- Lỗi trả theo một format thống nhất `{code, message, details, trace_id}`. Mã `code` khớp các quy tắc nghiệp vụ, ví dụ `BR-01_SCOPE_VIOLATION`.

**Chat Agent**
- Dùng SSE qua `POST /api/v1/chat/stream`. Client đọc stream bằng `fetch`, vì `EventSource` không gửi được body POST.
- Server gửi ping mỗi 15 giây để CloudFront không cắt kết nối.

**Thông báo**
- Dùng WebSocket tại `/ws`. Client xác thực bằng access token trong message đầu tiên (không đặt token trên query string).
- Mỗi kết nối được gán vào các kênh `user:{id}`, `zone:{id}:bql`.
- Sự kiện được phát giữa các process (API, worker) qua **Redis pub/sub**.
- Client tự kết nối lại với backoff. Sau khi kết nối lại, client gọi REST để lấy các sự kiện đã lỡ, nên WebSocket chỉ là kênh báo, không phải nguồn dữ liệu chính.

**Một domain CloudFront**

| Đường dẫn | Đi tới | Cấu hình |
|-----------|--------|----------|
| `/*` | S3 (client) | Có cache |
| `/api/*` | EC2 | Tắt cache; chuyển tiếp header `Authorization`, cookie, `traceparent` |
| `/ws` | EC2 | Cho phép WebSocket upgrade |

## Consequences

**Tích cực**
- Cùng domain nên không có CORS; refresh token đặt được trong cookie `SameSite=Strict`.
- Contract có type đầy đủ từ server tới client.
- SSE dễ test và dễ đi qua proxy.

**Tiêu cực**
- Phải tự viết lớp quản lý kết nối WebSocket, đăng ký kênh và kết nối lại.
- Thời gian giữ kết nối của CloudFront (mặc định 60s) bắt buộc phải có ping. Stream chat dài cần kiểm tra thực tế.
- Hai cơ chế realtime song song nên test nhiều hơn.

## Observability Impact

**Metric RED** cho HTTP, nhãn chỉ dùng route template (ví dụ `/api/v1/bookings/{id}`), không dùng ID:
- `http_server_request_duration_seconds` (histogram, gắn exemplar `trace_id`)
- `http_server_requests_total`

**Metric WebSocket:**
- `ws_connections_active` (gauge)
- `ws_messages_sent_total{event_type}`

**Metric SSE:**
- `chat_stream_duration_seconds`
- `chat_stream_first_token_seconds`

**Trace:**
- Mỗi sự kiện phát qua Redis mang theo `traceparent`, nên span phía WebSocket nối được với span của tác vụ đã sinh ra sự kiện.
