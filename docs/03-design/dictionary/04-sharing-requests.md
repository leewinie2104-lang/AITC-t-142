# Từ điển dữ liệu — Chia sẻ và yêu cầu (M4, M5)

> Thuộc [từ điển dữ liệu](../03-data-dictionary.md). Ràng buộc, index, giá trị enum: [sql/schema.sql](../sql/schema.sql).

## Chia sẻ và đặt chỗ (M4, M5)

### share_window

Chủ chỗ đăng khung thời gian vắng; `bookable_period` = khung trừ dự phòng (FR-05/06). v6 (BR-20): chỉ **trống** khi đã đăng và `owner_exited_at` có giá trị.  
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
| `owner_exited_at` | timestamp with time zone | yes |  | v6 (D-35): N1 đặt từ log cổng `out` của xe thuộc chủ, sau lúc đăng. NULL = xe chủ còn trong bãi, chưa ghép. Index `share_window_available_idx`. |
| `idempotency_key` | text | no |  | Chống chạy lại bước đăng lịch (check d). |
| `created_at` | timestamp with time zone | no | now() | Thời điểm tạo (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Lần cập nhật cuối (trigger `set_updated_at`). |

### parking_request

Mọi yêu cầu kèm cấp tính được và kết quả, kể cả yêu cầu bị chặn (KPI, AC-03). v6 (BR-21, D-34): chưa có chỗ phù hợp thì `outcome = 'queued'` và vào hàng chờ của tòa, xếp theo `queued_at`; mỗi người thuê tối đa một yêu cầu `waiting` mỗi tòa.  
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
| `outcome` | app.request_outcome | no |  | matched · redirected_th3 · redirected_public · blocked · no_match · queued (v6). |
| `block_reason` | text | yes |  | Quy tắc đã chặn (BR-xx); bắt buộc khi và chỉ khi bị chặn. |
| `channel` | text | no | 'app'::text | Giá trị trong tập cố định của kiểu / CHECK (xem ràng buộc). |
| `queue_status` | app.queue_status | yes |  | v6: `waiting` → `matched` / `left` / `expired`; có khi và chỉ khi `outcome = 'queued'` (CHECK `parking_request_queue_shape`). |
| `queued_at` | timestamp with time zone | yes |  | v6: lúc vào hàng chờ; thứ tự phục vụ (không theo ETA người thuê). Giờ ra dự kiến = `upper(requested_period)`. |
| `idempotency_key` | text | no |  | Khóa do bên gọi cấp (`thread_id:step`); chạy lại sẽ chạm ràng buộc UNIQUE. |
| `created_at` | timestamp with time zone | no | now() | Thời điểm tạo (UTC). |
| `updated_at` | timestamp with time zone | no | now() | v6: lần cập nhật cuối (trạng thái hàng chờ đổi; trigger `set_updated_at`). |
