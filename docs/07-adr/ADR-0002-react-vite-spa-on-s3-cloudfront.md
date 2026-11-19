# ADR-0002: Client là React (Vite) SPA, host trên S3 + CloudFront

- **Status**: Accepted
- **Date**: 2026-11-17
- **Liên quan**: [ADR-0003](ADR-0003-rest-openapi-sse-websocket-single-domain.md) · [Backlog module](../01-product/05-backlog.md#2-tính-năng)

## Context

- Cư dân dùng chủ yếu trên điện thoại; bảo vệ và BQL dùng máy tính (dashboard, hàng chờ duyệt).
- Chức năng chính: chat với Agent, lịch chia sẻ, dashboard. Không cần SEO / SSR vì mọi màn hình đều đăng nhập.
- Đội dùng credit AWS (ADR-0009).

## Decision

- **Framework:** React + TypeScript, build bằng Vite (phiên bản pin trong `client/package.json`); SPA tĩnh, mobile-first, có thể thêm PWA sau.
- **Giao diện:** Tailwind CSS + shadcn/ui. **Gọi API:** TanStack Query + client sinh từ OpenAPI (ADR-0003).
- **Routing:** React Router, tách route theo vai trò: cư dân / người thuê, bảo vệ, BQL khu, vận hành chuỗi.
- **Host:** S3 private (Origin Access Control) + CloudFront; đường dẫn không khớp file tĩnh trả `index.html`.
- **Token:** access token chỉ giữ trong bộ nhớ, không `localStorage`. Refresh token trong cookie httpOnly (ADR-0006); bản demo chỉ có
  access JWT 8 giờ ([ADR-0011](ADR-0011-mvp-simplifications.md)).

## Consequences

**Tích cực**
- Host rẻ, không có server cho client; deploy là sync file lên S3.
- Chung domain CloudFront với API nên không có CORS (ADR-0003). shadcn/ui chép component vào repo, dễ chỉnh.

**Tiêu cực**
- Không SSR: trang đầu tải chậm hơn, chấp nhận được với ứng dụng có đăng nhập.
- Tự làm trạng thái đăng nhập, bảo vệ route; dashboard BQL tự dựng bảng (TanStack Table).

## Observability Impact

- OpenTelemetry Web SDK gắn `traceparent` vào mọi `fetch`, nên trace đi xuyên trình duyệt → API → DB → Bedrock (ADR-0008).
- Lỗi JS gửi về `/api/v1/client-logs`, kèm `trace_id`, không chứa token hay biển số.
