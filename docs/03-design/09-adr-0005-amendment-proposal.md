# Đề xuất: sửa ADR-0005 — mã hóa biển số ở ứng dụng, không ở PostgreSQL

- **Status**: Proposed (chưa chấp nhận). ADR-0005 giữ nguyên cho đến khi nhóm đồng ý.
- **Date**: 2026-11-18
- **Ảnh hưởng**: [ADR-0005](../07-adr/ADR-0005-rds-postgres-asyncpg-rls-alembic-sql.md), mục "Hạ tầng DB" (pgcrypto mã hóa biển số).
  Nhật ký quyết định: [D-07](07-db-decision-log.md), cùng D-14 (xóa dữ liệu) và D-25 (LPR là dữ liệu nhạy cảm).
- **Nếu chấp nhận**: agent docs-keeper sửa ADR-0005 (hoặc viết ADR mới thay mục đó; ADR-0011 đã dùng cho đơn giản hóa MVP) và
  `docs/README.md`. Schema trong `docs/03-design/sql/schema.sql` đã theo đề xuất này.

## Context

ADR-0005 bật `pgcrypto` để mã hóa biển số. Với pgcrypto, khóa được gửi tới PostgreSQL trong mỗi câu lệnh mã hóa / giải mã, ví dụ
`pgp_sym_decrypt(col, $key)`, nên có thể lộ qua:

- log server (`log_min_duration_statement`, lỗi có `DETAIL`, `auto_explain`);
- `pg_stat_activity.query` khi câu lệnh đang chạy;
- RDS Performance Insights và công cụ ghi truy vấn;
- backup và replica, nơi có cả bản mã *và* bản sao khóa đã lọt vào log.

Trong khi đó PDPL 91/2025/QH15 và NĐ 356/2025/NĐ-CP (hiệu lực từ 2026-01-01, thay NĐ 13/2023) yêu cầu mã hóa và kiểm soát truy cập chặt
với dữ liệu nhạy cảm. Sự kiện LPR gắn biển số với vị trí và thời điểm chính xác, nên thiết kế coi là nhạy cảm (D-25). Băm cũng không cần
pgcrypto: PostgreSQL ≥ 11 có sẵn hàm `sha256()`.

## Decision (đề xuất)

1. **Biển số mã hóa ở ứng dụng** bằng **AES-256-GCM** với **envelope encryption**: AWS KMS sinh khóa dữ liệu (`GenerateDataKey`), cache trong
   bộ nhớ có thời hạn. Chỉ lưu khóa đã bọc và phiên bản khóa. Mỗi bản mã gồm `version ‖ nonce (96 bit, ngẫu nhiên) ‖ ciphertext ‖ tag`;
   AAD gắn id dòng và tên cột.
2. **Tra cứu không giải mã** bằng **blind index**: `plate_hash = HMAC-SHA256(normalise(plate), K_index)`. `K_index` là khóa riêng (KMS / SSM),
   không phải khóa mã hóa. `normalise` = NFKC, chữ hoa, chỉ giữ `[A-Z0-9]` (một hàm dùng chung cho đăng ký và N1).
3. **PostgreSQL không bao giờ thấy khóa.** DB lưu `plate_ciphertext bytea`, `plate_key_version smallint`, `plate_hash bytea`, `plate_masked text`.
   Vai trò app không `SELECT plate_ciphertext` được (quyền theo cột). Đường đọc duy nhất là `app.reveal_lpr_plate` / `app.reveal_vehicle_plate`
   (kiểm vai trò, khu, ghi `plate_access_log` cùng transaction). **MVP chưa có hai hàm này nên chỉ hiển thị biển số ẩn** ([08](08-deferred-tables.md)).
4. **pgcrypto vẫn cài** cho test, seed; code production không gọi `pgp_sym_*`.
5. **Xoay khóa:** ghi mới dùng phiên bản khóa mới nhất; job nền mã hóa lại các dòng `plate_key_version < current` theo lô. Xoay `K_index` cần
   băm lại toàn bộ (một lượt qua `vehicle`; `lpr_event` tự hết sau 90 ngày, D-05).
6. **Xóa dữ liệu** (D-14) đặt `plate_ciphertext` và `plate_hash` về NULL.

## Consequences

**Tích cực**
- Khóa không bao giờ xuất hiện trong log DB, nội dung truy vấn, giám sát hay backup.
- Một cài đặt mã hóa duy nhất, có unit test bằng Python (`AESGCM` của thư viện cryptography); KMS có dấu vết dùng khóa.
- Khớp biển số cho LPR (N1) chạy qua blind index, không cần giải mã.

**Tiêu cực**
- Không tìm trên bản rõ bằng SQL (không `LIKE`, không so khớp mờ). So khớp mờ (FR-16a) chạy trong app trên tập ứng viên nhỏ.
- Độ trễ và chi phí KMS khi cache trượt; cần cache có TTL và giới hạn số lần dùng mỗi khóa dữ liệu.
- Blind index lộ tính bằng nhau (cùng biển số ra cùng hash). Chấp nhận: tính năng khớp cần đúng điều đó; khóa index riêng và xoay được.
- Cần một người trong đội phụ trách xoay khóa và job mã hóa lại.

## Alternatives considered

| Phương án | Vì sao không chọn |
|-----------|-------------------|
| pgcrypto `pgp_sym_encrypt`, khóa truyền theo câu lệnh (ADR-0005 hiện tại) | Các đường lộ khóa ở trên; khó kiểm toán việc dùng khóa |
| Chỉ mã hóa lưu trữ RDS (KMS at rest) | Đã bật, nhưng chỉ bảo vệ đĩa và backup, không bảo vệ trước user DB hay log |
| Mã hóa tất định (AES-SIV) thay HMAC riêng | Một khóa cho cả tìm kiếm và bảo mật; xoay khóa phải mã hóa lại mọi thứ |
| Dịch vụ token hóa / vault riêng | Quá nhiều hạ tầng cho đội 4 người và một bản demo; có thể thêm sau mà giữ nguyên cột |

## Verification

- Unit test: mã hóa / giải mã khứ hồi, sai AAD thì lỗi, sửa tag thì lỗi, bảng chuẩn hóa (`30A-123.45`, `30a12345`, chữ số full-width).
- Test tích hợp (`docs/03-design/sql/seed-and-tests.sql`): vai trò app không select được `plate_ciphertext`.
- Vận hành: cảnh báo CloudWatch khi tần suất KMS `Decrypt` bất thường; grep log DB tìm `pgp_sym` phải rỗng.
