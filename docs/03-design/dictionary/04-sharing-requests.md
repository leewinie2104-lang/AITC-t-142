# Từ điển dữ liệu — Chia sẻ và yêu cầu (M4, M5)

> Thuộc [từ điển dữ liệu](../03-data-dictionary.md). Ràng buộc, index, giá trị enum: [sql/schema.sql](../sql/schema.sql).

## Chia sẻ và đặt chỗ (M4, M5)

### share_window

Chủ chỗ đăng khung thời gian vắng; `bookable_period` = khung trừ dự phòng (FR-05/06).  
RLS: **có** (policy: `open_read`, `owner`, `zone_staff`)

| Cột | Kiểu | Null | Mặc định | Ý nghĩa |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Khóa chính (UUIDv7, trừ khi kiểu là bigint). |
| `zone_id` | uuid | no |  | Khu sở hữu; dùng cho RLS. Khớp với cha qua FK ghép. |
| `slot_id` | uuid | no |  | Tham chiếu `slot`. |
| `owner_user_id` | uuid | no |  | Tham chiếu `app_user`. |
| `period` | tstzrange | no |  | Khung thời gian chủ chỗ vắng. |
| `bookable_period` | tstzrange | no |  | Khung trừ dự phòng; lượt đặt phải nằm trong đây. |
| `open_scope` | app.open_scope | no |  | Phạm vi chủ chỗ chọn ≤ mức tối đa của pool (AC-23). |
| `status` | app.share_status | no | 'open'::share_status | Giá trị trong tập cố định của kiểu / CHECK (xem ràng buộc). |
| `returned_at` | timestamp with time zone | yes |  | Thời điểm về sớm (W3). |
| `idempotency_key` | text | no |  | Chống chạy lại bước đăng lịch (check d). |
| `created_at` | timestamp with time zone | no | now() | Thời điểm tạo (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Lần cập nhật cuối (trigger `set_updated_at`). |

### parking_request

Mọi yêu cầu kèm cấp tính được và kết quả, kể cả yêu cầu bị chặn (KPI, AC-03).  
RLS: **có** (policy: `requester`, `zone_staff`)

| Cột | Kiểu | Null | Mặc định | Ý nghĩa |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Khóa chính (UUIDv7, trừ khi kiểu là bigint). |
| `zone_id` | uuid | no |  | Khu sở hữu; dùng cho RLS. Khớp với cha qua FK ghép. |
| `building_id` | uuid | no |  | Tham chiếu `building`. |
| `requester_user_id` | uuid | no |  | Tham chiếu `app_user`. |
| `vehicle_id` | uuid | no |  | Tham chiếu `vehicle`. |
| `requested_period` | tstzrange | no |  | Khoảng thời gian yêu cầu; tối đa 31 ngày. |
| `computed_level` | app.eligibility_level | no |  | Cấp tính lúc yêu cầu (L1–L4). |
| `outcome` | app.request_outcome | no |  | matched · redirected_th3 · redirected_public · blocked · no_match. |
| `block_reason` | text | yes |  | Quy tắc đã chặn (BR-xx); bắt buộc khi và chỉ khi bị chặn. |
| `channel` | text | no | 'app'::text | Giá trị trong tập cố định của kiểu / CHECK (xem ràng buộc). |
| `idempotency_key` | text | no |  | Khóa do bên gọi cấp (`thread_id:step`); chạy lại sẽ chạm ràng buộc UNIQUE. |
| `created_at` | timestamp with time zone | no | now() | Thời điểm tạo (UTC). |
