# Từ điển dữ liệu — Tư cách (M1)

> Thuộc [từ điển dữ liệu](../03-data-dictionary.md). Ràng buộc, index, giá trị enum: [sql/schema.sql](../sql/schema.sql).

## Tư cách (M1)

### asset

Tài sản tạo ra tư cách (căn hộ, shophouse, văn phòng…). Mã căn không rời khỏi khu (BR-17).  
RLS: **có** (policy: `holder_read`, `zone_staff`)

| Cột | Kiểu | Null | Mặc định | Ý nghĩa |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Khóa chính (UUIDv7, trừ khi kiểu là bigint). |
| `zone_id` | uuid | no |  | Khu sở hữu; dùng cho RLS. Khớp với cha qua FK ghép. |
| `building_id` | uuid | yes |  | NULL với shophouse thấp tầng ngoài mọi tòa (A-10 → L2). → `building`. |
| `kind` | app.asset_kind | no |  | Giá trị trong tập cố định của kiểu / CHECK (xem ràng buộc). |
| `code` | text | no |  | Số căn. Chỉ thấy trong khu của nó. |
| `created_at` | timestamp with time zone | no | now() | Thời điểm tạo (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Lần cập nhật cuối (trigger `set_updated_at`). |

### eligibility

Tư cách = (tài sản, vai trò, hạn), do BQL khu có tài sản xác minh. Nguồn của L1–L4.  
RLS: **có** (policy: `holder_claim`, `holder_read`, `zone_staff`)

| Cột | Kiểu | Null | Mặc định | Ý nghĩa |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Khóa chính (UUIDv7, trừ khi kiểu là bigint). |
| `user_id` | uuid | no |  | Tham chiếu `app_user`. |
| `asset_id` | uuid | no |  | Tham chiếu `asset`. |
| `zone_id` | uuid | no |  | Khu sở hữu; dùng cho RLS. Khớp với cha qua FK ghép. |
| `role` | app.eligibility_role | no |  | owner · tenant · authorized · employee. |
| `valid_during` | tstzrange | no |  | Hiệu lực `[từ, đến)`; cận trên mở = không hết hạn. Kiểm tra lúc dùng (BR-16). |
| `status` | app.eligibility_status | no | 'pending'::eligibility_status | pending → verified → revoked/expired. |
| `verified_by` | uuid | yes |  | BQL đã xác minh (bắt buộc khi verified). → `app_user`. |
| `verified_at` | timestamp with time zone | yes |  | Thời điểm xảy ra sự việc mà tên cột mô tả (UTC); NULL = chưa xảy ra. |
| `revoked_at` | timestamp with time zone | yes |  | Thời điểm xảy ra sự việc mà tên cột mô tả (UTC); NULL = chưa xảy ra. |
| `revoke_reason` | text | yes |  | Như tên cột. |
| `created_at` | timestamp with time zone | no | now() | Thời điểm tạo (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Lần cập nhật cuối (trigger `set_updated_at`). |

### slot_holding

Ai giữ quyền sử dụng ô TH1/TH2 theo thời gian (chủ hoặc người thuê dài hạn). Cần có để chia sẻ.  
RLS: **có** (policy: `holder_read`, `zone_staff`)

| Cột | Kiểu | Null | Mặc định | Ý nghĩa |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Khóa chính (UUIDv7, trừ khi kiểu là bigint). |
| `zone_id` | uuid | no |  | Khu sở hữu; dùng cho RLS. Khớp với cha qua FK ghép. |
| `slot_id` | uuid | no |  | Tham chiếu `slot`. |
| `slot_type` | app.slot_type | no |  | Giá trị trong tập cố định của kiểu / CHECK (xem ràng buộc). |
| `user_id` | uuid | no |  | Tham chiếu `app_user`. |
| `kind` | app.holding_kind | no |  | owner (TH1) · lessee (TH2). |
| `held_during` | tstzrange | no |  | Thời gian nắm giữ; không chồng lấn trên một ô (EXCLUDE). |
| `voided_at` | timestamp with time zone | yes |  | Đặt khi dòng nắm giữ nhập nhầm; dòng đã void không còn chặn ô. |
| `void_reason` | text | yes |  | Lý do bắt buộc khi void. |
| `created_at` | timestamp with time zone | no | now() | Thời điểm tạo (UTC). |

## Đối chiếu đăng ký với BQL (FR-38, v7)

### bql_registry_import

Dữ liệu BQL nhập **một lần lúc triển khai** (cư dân, chủ shophouse, ô của từng hộ kèm kích thước, biển số). Mỗi dòng là một dòng của một batch. Khi đăng ký, hệ thống đối chiếu số điện thoại, mã hộ và biển số: khớp duy nhất → `auto_matched` (kích hoạt, không qua BQL); không khớp hoặc khớp nhiều → `needs_bql`. Dữ liệu cá nhân: chỉ nhân viên khu và hệ thống đọc được.  
RLS: **có** (policy: `zone_staff`, vai trò `zone_manager` và `system`)

| Cột | Kiểu | Null | Mặc định | Ý nghĩa |
|---|---|---|---|---|
| `id` | bigint | no | identity | Khóa chính (identity). |
| `zone_id` | uuid | no |  | Khu của dữ liệu BQL; dùng cho RLS. → `zone`. |
| `batch_id` | uuid | no |  | Một lần nhập file. Nhập lại cùng batch không thêm dòng (UNIQUE với `line_no`). |
| `line_no` | integer | no |  | Số thứ tự dòng trong batch (> 0). |
| `role` | text | no |  | `resident` (cư dân) hoặc `shophouse_owner` (CHECK). |
| `full_name` | text | no |  | Họ tên như BQL khai (PII, tối đa 200 ký tự). |
| `phone_e164` | text | yes |  | Số điện thoại E.164; khóa đối chiếu chính. |
| `building_id` | uuid | yes |  | Tòa; NULL với shophouse không thuộc tòa (A-10). → `building` (kèm `zone_id`). |
| `unit_code` | text | no |  | Căn hộ hoặc shophouse; cùng mã với `asset.code`. |
| `slot_code` | text | yes |  | Mã ô của hộ; mỗi ô một dòng (một hộ nhiều dòng). Bắt buộc có `size_class`. |
| `size_class` | app.size_class | yes |  | Kích thước ô: S < M < L < XL. |
| `plate_hash` | bytea | yes |  | HMAC-SHA256 của biển số (32 byte), cùng khóa với `vehicle.plate_hash`. Không lưu biển số rõ. |
| `plate_masked` | text | yes |  | Biển số ẩn để hiển thị (`30A-•••.••`). |
| `match_status` | app.registry_match | no | 'needs_bql'::registry_match | `auto_matched` (khớp duy nhất) · `needs_bql` (chưa khớp hoặc khớp nhiều). |
| `matched_user_id` | uuid | yes |  | Tài khoản đã khớp. → `app_user`. Bắt buộc khi `auto_matched`. |
| `matched_at` | timestamp with time zone | yes |  | Lúc khớp. |
| `created_at` | timestamp with time zone | no | now() | Thời điểm nhập dòng (UTC). |

