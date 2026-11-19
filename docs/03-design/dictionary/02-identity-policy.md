# Từ điển dữ liệu — Tài khoản và nội quy (M1, M3)

> Thuộc [từ điển dữ liệu](../03-data-dictionary.md). Ràng buộc, index, giá trị enum: [sql/schema.sql](../sql/schema.sql).

## Tài khoản (M1)

### app_user

Một tài khoản cho cả chuỗi (FR-23). Xóa mềm. Thành viên BQL hoặc bảo vệ gắn với một khu qua `staff_zone_id`. Đồng ý xử lý biển số / ảnh là một dòng `consent_record`, không phải cột ở đây (A-03, BR-09).  
RLS: **có** (policy: `auth_and_system`, `self`, `zone_manager_read`)

| Cột | Kiểu | Null | Mặc định | Ý nghĩa |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Khóa chính (UUIDv7, trừ khi kiểu là bigint). |
| `full_name` | text | no |  | Dữ liệu cá nhân. Được thay bằng mã giả trước mọi lần gọi LLM (BR-14). |
| `phone_e164` | text | yes |  | Định danh đăng nhập, E.164. Duy nhất trong các tài khoản chưa xóa. |
| `email` | text | yes |  | Dữ liệu cá nhân, tùy chọn; duy nhất (không phân biệt hoa thường) trong tài khoản còn dùng. |
| `password_hash` | text | no |  | Chỉ lưu hash argon2id (CHECK). |
| `role` | app.user_role | no | 'resident'::user_role | Vai trò ứng dụng (ADR-0006). Tư cách là chuyện khác, không bao giờ nằm trong token. |
| `status` | app.user_status | no | 'active'::user_status | Giá trị trong tập cố định của kiểu / CHECK (xem ràng buộc). |
| `failed_logins` | smallint | no | 0 | Bộ đếm để khóa tạm. |
| `locked_until` | timestamp with time zone | yes |  | Khóa tạm sau nhiều lần đăng nhập sai. |
| `deleted_at` | timestamp with time zone | yes |  | Dấu xóa mềm; tương đương status = deleted. |
| `staff_zone_id` | uuid | yes |  | Khu duy nhất mà thành viên BQL (`zone_manager`) hoặc bảo vệ phụ trách; nguồn của claim JWT `zone_ids` = `{staff_zone_id}`. NULL với cư dân, người thuê và vận hành chuỗi. CHECK `app_user_staff_zone_role`: chỉ `guard` / `zone_manager` được đặt. Thay bảng nối `staff_zone` (ADR-0011). |
| `created_at` | timestamp with time zone | no | now() | Thời điểm tạo (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Lần cập nhật cuối (trigger `set_updated_at`). |

### vehicle

Xe của người dùng. Biển số lưu dạng mã hóa + hash có khóa + bản ẩn; vai trò app không đọc được cột bản mã (MVP chỉ hiển thị biển số ẩn).  
RLS: **có** (policy: `own_or_system`, `zone_staff_read`)

| Cột | Kiểu | Null | Mặc định | Ý nghĩa |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Khóa chính (UUIDv7, trừ khi kiểu là bigint). |
| `user_id` | uuid | no |  | Tham chiếu `app_user`. |
| `plate_ciphertext` | bytea | yes |  | Biển số đã mã hóa. Vai trò app không SELECT được (quyền theo cột). |
| `plate_key_version` | smallint | no | 1 | Phiên bản khóa để xoay vòng. |
| `plate_hash` | bytea | yes |  | HMAC-SHA256 của biển số đã chuẩn hóa với pepper bí mật; dùng để khớp LPR. |
| `plate_masked` | text | no |  | Dạng hiển thị, ví dụ 30A-•••.45. |
| `size_class` | app.size_class | no |  | Hạng kích thước xe (S < M < L < XL); phải `<=` hạng của ô mới đặt được (BR-11). |
| `is_active` | boolean | no | true | Cờ ngừng dùng (xóa mềm); dòng vẫn được lịch sử tham chiếu. |
| `created_at` | timestamp with time zone | no | now() | Thời điểm tạo (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Lần cập nhật cuối (trigger `set_updated_at`). |

## Nội quy và cấu hình (M3)

### zone_policy

Nội quy khu có phiên bản: dự phòng, ngưỡng, thời hạn, ngưỡng OCR, bảng giá và mẫu thỏa thuận. Thỏa thuận ghim phiên bản đã dùng.  
RLS: **có** (policy: `manage_zone`, `read_authenticated`)

| Cột | Kiểu | Null | Mặc định | Ý nghĩa |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Khóa chính (UUIDv7, trừ khi kiểu là bigint). |
| `zone_id` | uuid | no |  | Khu sở hữu; dùng cho RLS. Khớp với cha qua FK ghép. |
| `version` | integer | no |  | Tăng dần theo khu; mỗi thay đổi là một dòng mới. |
| `effective_from` | timestamp with time zone | no |  | Thời điểm phiên bản bắt đầu hiệu lực. |
| `buffer_before` | interval | no | '00:15:00'::interval | Dự phòng ở đầu khung chia sẻ (FR-06). |
| `buffer_after` | interval | no | '00:30:00'::interval | Dự phòng trước khi chủ chỗ về (BR-07). |
| `approval_threshold_vnd` | bigint | no | 1000000 | Trên mức này, thỏa thuận cần BQL duyệt (BR-12). |
| `hold_ttl` | interval | no | '00:10:00'::interval | Thời hạn giữ chỗ tạm. |
| `agreement_confirm_ttl` | interval | no | '00:30:00'::interval | Thời gian để hai bên xác nhận. |
| `eligibility_grace_max` | interval | yes | '7 days'::interval | BR-16: thời gian tối đa một lượt đặt đang chạy được giữ sau khi tư cách hết hạn (TBD; NULL = đến hết lượt). |
| `early_return_cost_rule` | text | no | 'renter_pays_th3_relocated'::text | Ai trả khi chủ chỗ về sớm; chỉ cài `renter_pays_th3_relocated` (D-09). |
| `ocr_review_threshold` | numeric(4,3) | no | 0.800 | Biển số đọc với độ tin cậy OCR dưới mức này vào hàng chờ kiểm tra (0–1, mặc định 0.800; D-21). |
| `prices` | jsonb | no |  | Bảng giá dạng JSON object, cấu trúc `{"TH1":{"L1":{"hour":10000,"day":50000},…},…}` (loại ô → cấp tư cách → đơn giá, VND). Rule engine (Pydantic) kiểm tra; SQL chỉ kiểm `jsonb_typeof = 'object'`. |
| `agreement_template_md` | text | no |  | Mẫu thỏa thuận Markdown của phiên bản nội quy (không rỗng); có phiên bản cùng nội quy, nên thỏa thuận ghim `zone_policy_id` cũng ghim nội dung. |
| `created_by` | uuid | yes |  | Tham chiếu `app_user`. |
| `created_at` | timestamp with time zone | no | now() | Thời điểm tạo (UTC). |
