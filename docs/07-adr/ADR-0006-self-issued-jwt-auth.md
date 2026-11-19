# ADR-0006: Xác thực bằng JWT tự phát hành trong FastAPI

- **Status**: Accepted · **Partly superseded by [ADR-0011](ADR-0011-mvp-simplifications.md) (2026-11-18)**: demo bỏ refresh token (chỉ access JWT 8 giờ, không thu hồi); OTP xác nhận lưu trong Redis
- **Date**: 2026-11-17
- **Liên quan**: [ADR-0003](ADR-0003-rest-openapi-sse-websocket-single-domain.md) · [ADR-0005](ADR-0005-rds-postgres-asyncpg-rls-alembic-sql.md) · [PRD §3](../01-product/02-prd.md#3-đối-tượng-người-dùng-và-tư-cách)

## Context

- 5 vai trò: cư dân, người thuê, bảo vệ, BQL khu, vận hành chuỗi. Quyền thật còn phụ thuộc **tư cách** (tài sản, vai trò, hạn), thay đổi theo
  thời gian và nằm trong DB.
- Đội không dùng Cognito để kiểm soát hoàn toàn và không phụ thuộc thêm dịch vụ.

## Decision

- **Mật khẩu:** **argon2id** (`argon2-cffi`), độ dài tối thiểu; quên mật khẩu bằng link một lần qua email (SES), hạn 30 phút.
- **Access token:** JWT ký **ES256**, khóa riêng trong SSM SecureString; sống 15 phút (demo: 8 giờ, ADR-0011), chỉ giữ trong bộ nhớ client.
  Claim tối thiểu `sub`, `role`, `zone_ids` (khu BQL quản lý), `jti`, `exp`. **Không** đưa cấp L1–L4 vào token: luôn tính từ DB (BR-15, BR-16).
- **Refresh token:** chuỗi ngẫu nhiên, lưu hash; cookie `httpOnly; Secure; SameSite=Strict; Path=/api/v1/auth`; sống 14 ngày, **xoay vòng mỗi
  lần dùng**, phát hiện dùng lại thì thu hồi cả chuỗi. (Không có trong demo.)
- **Chống brute force:** rate limit theo IP và tài khoản bằng Redis; khóa tạm sau nhiều lần sai.
- **FastAPI:** dependency `current_user` xác minh JWT rồi đặt ngữ cảnh RLS (`SET LOCAL app.user_id…`); vai trò kiểm bằng decorator, tư cách do rule engine kiểm.
- **WebSocket:** token trong message đầu; đóng kết nối khi token hết hạn mà client không gửi token mới.
- **OTP xác nhận thỏa thuận (W2):** mã 6 số, lưu hash, có hạn, giới hạn lần thử; demo hiển thị qua thông báo trong app thay SMS.

## Consequences

**Tích cực**
- Không thêm dịch vụ; quyền và tư cách cùng DB, dễ viết policy RLS; toàn quyền định nghĩa claim và luồng đăng nhập.

**Tiêu cực**
- Đội tự chịu trách nhiệm băm, xoay vòng, thu hồi, chống brute force, quản lý khóa. Chưa có MFA, đăng nhập mạng xã hội.
- Bắt buộc bộ test auth: token hết hạn, refresh dùng lại, sai vai trò, user khu A truy cập dữ liệu khu B.

## Observability Impact

- Metric (không nhãn email hay user id): `auth_login_attempts_total{result="success|invalid|locked"}`, `auth_token_refresh_total{result}`,
  `auth_refresh_reuse_detected_total` (hai metric refresh không có trong demo).
- Log sự kiện auth kèm `trace_id`, `user_id`; **không bao giờ** ghi mật khẩu, token, header `Authorization`, cookie (middleware tự che).
- Span request có `enduser.role`, không có thông tin định danh cá nhân.
