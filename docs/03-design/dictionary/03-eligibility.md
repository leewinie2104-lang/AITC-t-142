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
