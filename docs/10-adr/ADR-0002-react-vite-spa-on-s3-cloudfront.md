# ADR-0002: Client là React (Vite) SPA, host trên S3 + CloudFront

- **Status**: Accepted
- **Date**: 2026-11-17
- **Liên quan**: [ADR-0003](ADR-0003-rest-openapi-sse-websocket-single-domain.md) · [Backlog module](../01-product/backlog/modules.md)

## Context

- **Người dùng và thiết bị:**
  - Cư dân dùng chủ yếu trên điện thoại.
  - Bảo vệ và BQL dùng trên máy tính (dashboard, hàng chờ duyệt).
- **Chức năng chính:** chat với Agent, lịch chia sẻ, sơ đồ bãi, dashboard.
- **SEO và SSR:** không cần, vì mọi màn hình đều phải đăng nhập.
- **Hạ tầng:** đội dùng credit AWS (ADR-0009).

## Decision

- **Framework:** React + TypeScript, build bằng Vite. Phiên bản cụ thể được pin trong `client/package.json` khi khởi tạo. Ứng dụng là SPA tĩnh, mobile-first, có thể thêm manifest PWA sau.
- **Giao diện:** Tailwind CSS + shadcn/ui.
- **Gọi API:** TanStack Query + client sinh tự động từ OpenAPI (ADR-0003).
- **Routing:** React Router. Route được tách theo vai trò: cư dân / người thuê, bảo vệ, BQL khu, đơn vị vận hành chuỗi.
- **Host:** S3 (private, truy cập qua Origin Access Control) + CloudFront. Mọi đường dẫn không khớp file tĩnh đều trả về `index.html`.
- **Token:** access token chỉ giữ trong bộ nhớ, không lưu vào `localStorage`. Refresh token nằm trong cookie httpOnly (ADR-0006).

## Consequences

**Tích cực**
- Host rẻ, không có server cho client, deploy chỉ là sync file lên S3.
- Dùng chung một domain CloudFront với API nên không phải xử lý CORS (ADR-0003).
- shadcn/ui copy component vào repo, dễ chỉnh cho cả màn hình di động lẫn dashboard.

**Tiêu cực**
- Không có SSR: tải trang đầu chậm hơn. Chấp nhận được với ứng dụng có đăng nhập.
- Phải tự làm trạng thái đăng nhập, bảo vệ route và làm mới token.
- Dashboard BQL phải tự dựng bảng (TanStack Table) thay vì có sẵn như Ant Design.

## Observability Impact

- Client dùng OpenTelemetry Web SDK, tự gắn header `traceparent` vào mọi request `fetch`. Trace của một thao tác vì vậy đi xuyên từ trình duyệt → API → DB → Bedrock (ADR-0008).
- Lỗi JS gửi về endpoint `/api/v1/client-logs`. Log này kèm `trace_id` và không chứa token hay biển số.
