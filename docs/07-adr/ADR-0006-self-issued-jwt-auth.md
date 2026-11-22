# ADR-0006: Xác thực bằng JWT tự phát hành trong FastAPI

- **Status**: Accepted
- **Date**: 2026-11-17 · viết lại 2026-11-22 (plan 021: gộp phần auth của ADR-0011)
- **Liên quan**: [ADR-0002](ADR-0002-react-vite-spa-on-s3-cloudfront.md) · [ADR-0005](ADR-0005-rds-postgres-asyncpg-rls-alembic-sql.md) · [ADR-0011](ADR-0011-mvp-simplifications.md) · [PRD §3](../01-product/02-prd.md#3-đối-tượng-người-dùng-và-tư-cách)

## Context

- 5 vai trò: cư dân, người thuê, bảo vệ, BQL khu, vận hành chuỗi. Quyền thật còn phụ thuộc **tư cách** (tài sản, vai trò, hạn)
  nằm trong DB và đổi theo thời gian.
- Đội không dùng Cognito để tự kiểm soát luồng và không thêm dịch vụ ngoài.

## Decision

- **Mật khẩu:** argon2id (`argon2-cffi`); khóa tạm sau nhiều lần sai (`failed_logins`, `locked_until`), rate limit bằng Redis.
- **Access token:** JWT ký ES256, sống **8 giờ** trong demo, không thu hồi; chỉ giữ trong bộ nhớ client. Claim `sub`, `role`,
  `zone_ids`, `jti`, `exp`. **Không** đưa cấp L1–L4 vào token: luôn tính từ DB (BR-15, BR-16).
- **FastAPI:** dependency `current_user` xác minh JWT rồi đặt ngữ cảnh RLS (ADR-0005); vai trò kiểm ở router, tư cách do rule engine kiểm.
- **OTP xác nhận thỏa thuận:** mã 6 số, lưu hash trong **Redis** có hạn và giới hạn lần thử; DB chỉ giữ `agreement.*_confirmed_at`
  và một dòng `consent_record`. Demo hiển thị OTP qua thông báo trong app thay SMS.
- **Khi có người dùng thật:** access token 15 phút + refresh token xoay vòng (cookie `httpOnly; Secure; SameSite=Strict`, phát hiện
  dùng lại thì thu hồi cả chuỗi), quên mật khẩu qua email.

## Consequences

- **Tích cực:** không thêm dịch vụ; quyền và tư cách cùng DB nên policy RLS đơn giản; toàn quyền định nghĩa claim.
- **Tiêu cực:** token lộ dùng được tới 8 giờ; đội tự lo băm, khóa, chống brute force; chưa có MFA. Bắt buộc test: token hết hạn,
  sai vai trò, user khu A đọc dữ liệu khu B.

## Observability Impact

- Metric (không nhãn email hay user id): `auth_login_attempts_total{result="success|invalid|locked"}`.
- Log sự kiện auth kèm `trace_id`; **không** ghi mật khẩu, token, header `Authorization`, cookie (middleware tự che).
- Span request có `enduser.role`, không có thông tin định danh cá nhân.
