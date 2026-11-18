# ADR-0006: Xác thực bằng JWT tự phát hành trong FastAPI

- **Status**: Accepted
- **Date**: 2026-11-17
- **Liên quan**: [ADR-0003](ADR-0003-rest-openapi-sse-websocket-single-domain.md) · [ADR-0005](ADR-0005-rds-postgres-asyncpg-rls-alembic-sql.md) · [PRD §3 Tư cách](../01-product/02-prd.md#3-đối-tượng-người-dùng-và-tư-cách)

## Context

- Hệ thống có 5 vai trò: cư dân, người thuê, bảo vệ, BQL khu, đơn vị vận hành chuỗi (khớp [backlog module M1](../01-product/backlog/01-modules.md)).
- Quyền thật sự còn phụ thuộc **tư cách** (tài sản, vai trò, hạn hiệu lực). Tư cách thay đổi theo thời gian và nằm trong DB.
- Đội chọn không dùng Cognito, để kiểm soát hoàn toàn và không phụ thuộc thêm dịch vụ.

## Decision

**Mật khẩu**
- Băm bằng **argon2id** (`argon2-cffi`). Có yêu cầu độ dài tối thiểu.
- Quên mật khẩu: gửi link một lần qua email (SES), hết hạn sau 30 phút.

**Access token**
- JWT ký **ES256**. Khóa riêng lưu trong SSM Parameter Store (SecureString), không commit vào repo.
- Sống 15 phút, chỉ giữ trong bộ nhớ của client.
- Claim tối thiểu: `sub`, `role`, `zone_ids` (khu mà người dùng quản lý, chỉ có ở vai trò BQL), `jti`, `exp`.
- **Không** đưa tư cách L1–L4 vào token. Tư cách có hạn hiệu lực nên luôn tính từ DB (BR-15, BR-16).

**Refresh token**
- Chuỗi ngẫu nhiên, lưu hash trong DB.
- Gửi qua cookie `httpOnly; Secure; SameSite=Strict; Path=/api/v1/auth`.
- Sống 14 ngày, **xoay vòng mỗi lần dùng**. Nếu phát hiện token cũ bị dùng lại, thu hồi cả chuỗi token.

**Bảo vệ đăng nhập**
- Rate limit theo IP và theo tài khoản bằng Redis. Khóa tạm sau nhiều lần sai.

**FastAPI**
- Dependency `current_user` xác minh JWT, rồi đặt ngữ cảnh RLS (`SET LOCAL app.user_id…`).
- Kiểm tra vai trò bằng decorator. Kiểm tra tư cách do rule engine làm.

**WebSocket**
- Xác thực bằng access token trong message đầu tiên. Đóng kết nối khi token hết hạn, nếu client không gửi token mới.

**OTP xác nhận thỏa thuận (W2)**
- Là một cơ chế riêng: mã 6 số, lưu hash, có hạn, giới hạn số lần thử.
- Trong demo hiển thị qua thông báo trong app thay cho SMS.

## Consequences

**Tích cực**
- Không phụ thuộc thêm dịch vụ; quyền và tư cách nằm cùng DB, dễ viết policy RLS.
- Toàn quyền định nghĩa claim và luồng đăng nhập.

**Tiêu cực**
- Đội phải tự chịu trách nhiệm bảo mật: băm, xoay vòng, thu hồi, chống brute force, quản lý khóa.
- Chưa có MFA và đăng nhập mạng xã hội. Để giai đoạn sau nếu cần.
- Bắt buộc có bộ test riêng cho auth: token hết hạn, refresh bị dùng lại, sai vai trò, user khu A truy cập dữ liệu khu B.

## Observability Impact

**Metric** (không gắn nhãn email hay user id):
- `auth_login_attempts_total{result="success|invalid|locked"}`
- `auth_token_refresh_total{result}`
- `auth_refresh_reuse_detected_total`

**Log:** sự kiện auth ghi kèm `trace_id` và `user_id`. **Không bao giờ** ghi mật khẩu, token, header `Authorization` hay cookie. Middleware log tự che các header này.

**Span:** span của request có thuộc tính `enduser.role`, không có thông tin định danh cá nhân.
