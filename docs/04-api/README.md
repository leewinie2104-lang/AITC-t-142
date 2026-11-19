# 04-api — Giao diện lập trình

> **Thư mục này trả lời:** client và hệ thống ngoài gọi server bằng endpoint nào, gửi gì, nhận gì.

## Tổng quan

**Chưa có tài liệu.** Theo [ADR-0003](../10-adr/ADR-0003-rest-openapi-sse-websocket-single-domain.md), server có ba kênh, tất cả qua một domain CloudFront:

| Kênh | Dùng cho |
|---|---|
| **REST + OpenAPI** | Mọi thao tác nghiệp vụ; client sinh từ OpenAPI |
| **SSE** | Chat với Agent, trả lời dạng stream |
| **WebSocket `/ws`** | Thông báo realtime (M13) |

Xác thực bằng JWT tự phát hành ([ADR-0006](../10-adr/ADR-0006-self-issued-jwt-auth.md)).

## Nguồn sự thật

Spec OpenAPI được FastAPI sinh từ code. Khi chạy local: `http://localhost:8000/docs`. Tài liệu ở đây chỉ bổ sung phần OpenAPI không tự nói được; khi lệch, code đúng hơn.

## Nên có

| File gợi ý | Nội dung |
|---|---|
| `01-conventions.md` | Quy ước URL, phân trang, định dạng lỗi, mã HTTP cho từng loại lỗi domain |
| `02-auth.md` | Đăng nhập (demo: chỉ access JWT hạn 8 giờ, không refresh token, xem [ADR-0011](../10-adr/ADR-0011-mvp-simplifications.md)), vai trò và phạm vi khu trong token |
| `03-chat-sse.md` | Định dạng sự kiện SSE của chat, cách hiển thị khi chờ BQL duyệt |
| `04-websocket.md` | Các loại thông báo qua `/ws` và payload |
| `05-lpr-ingest.md` | Định dạng log LPR (CSV mô phỏng, webhook / MQTT ở Ưu tiên 3) |

## Liên quan

- Màn hình dùng API: [wireframes](../01-product/ux/wireframes/README.md).
- Router và schema: `server/src/app/<module>/delivery/rest/` (xem [01-server-structure](../05-development/01-server-structure.md)).

## Quy ước

- File đánh số `NN-`; thêm file thì cập nhật bảng trên và [docs/README.md](../README.md).
- Đổi giao thức hoặc kênh thì viết ADR mới.
