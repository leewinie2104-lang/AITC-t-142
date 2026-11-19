# Từ điển dữ liệu — Đặt chỗ và xử lý chủ về sớm (M5, M9)

> Thuộc [từ điển dữ liệu](../03-data-dictionary.md). Ràng buộc, index, giá trị enum: [sql/schema.sql](../sql/schema.sql).

## Chia sẻ và đặt chỗ (M4, M5)

### booking

Một lượt giữ ô trong một khoảng thời gian. Ràng buộc EXCLUDE làm đặt trùng là không thể. `checked_in_at` / `checked_out_at` ghi lượt đỗ thực tế (N1 đặt từ `lpr_event` khớp).  
RLS: **có** (policy: `parties_read`, `zone_staff`)

| Cột | Kiểu | Null | Mặc định | Ý nghĩa |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Khóa chính (UUIDv7, trừ khi kiểu là bigint). |
| `ref_no` | bigint | no | identity | Số dễ đọc hiển thị trên UI (tiền tố GD- / TC- / HD-). |
| `zone_id` | uuid | no |  | Khu sở hữu; dùng cho RLS. Khớp với cha qua FK ghép. |
| `slot_id` | uuid | no |  | Tham chiếu `slot`. |
| `request_id` | uuid | yes |  | Tham chiếu `parking_request`. |
| `share_window_id` | uuid | yes |  | Khung chia sẻ dùng (TH1/TH2); NULL với TH3. → `share_window`. |
| `provider_user_id` | uuid | yes |  | Người giữ ô (= chủ khung chia sẻ, qua FK ghép). |
| `renter_user_id` | uuid | no |  | Tham chiếu `app_user`. |
| `vehicle_id` | uuid | no |  | Tham chiếu `vehicle`. |
| `period` | tstzrange | no |  | Khoảng thời gian đã đặt `[bắt đầu, kết thúc)`. |
| `eligibility_level` | app.eligibility_level | no |  | Cấp của người thuê tại ô; trigger tính lại và kiểm tra. |
| `price_vnd` | bigint | no |  | Giá do rule engine tính, VND số nguyên. |
| `status` | app.booking_status | no | 'held'::booking_status | held → pending_agreement → pending_approval → confirmed → completed; hoặc relocated/cancelled/expired/rejected. |
| `hold_expires_at` | timestamp with time zone | yes |  | Bắt buộc khi đang held. |
| `checked_in_at` | timestamp with time zone | yes |  | Lúc xe vào, N1 đặt từ một `lpr_event` có `matched_booking_id` là lượt này. NULL = chưa đến. Bảng `parking_session` riêng quay lại cùng W4 quá giờ. |
| `checked_out_at` | timestamp with time zone | yes |  | Lúc xe ra (cùng nguồn). Chỉ đặt sau `checked_in_at` và không sớm hơn (CHECK `booking_check_times`). |
| `relocated_from_booking_id` | uuid | yes |  | Lượt gốc khi đây là lượt TH3 thay thế sau chủ về sớm. → `booking`. |
| `idempotency_key` | text | no |  | Khóa do bên gọi cấp (`thread_id:step`); chạy lại sẽ chạm ràng buộc UNIQUE. |
| `version` | integer | no | 1 | Khóa lạc quan cho chỉnh sửa từ người dùng. |
| `created_at` | timestamp with time zone | no | now() | Thời điểm tạo (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Lần cập nhật cuối (trigger `set_updated_at`). |

### recovery_case

W3 (chủ về sớm, Ưu tiên 2): hồ sơ tìm chỗ khác cho người thuê. Rule engine điền `options` (ô ứng viên và giá); LLM chỉ diễn đạt đề xuất (BR-14). Tối đa một hồ sơ mở mỗi lượt đặt. Mới ở v4.  
RLS: **có** (policy: `parties_read`, `zone_staff`)

| Cột | Kiểu | Null | Mặc định | Ý nghĩa |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Khóa chính (UUIDv7). |
| `zone_id` | uuid | no |  | Khu của lượt đặt; dùng cho RLS. FK ghép giữ mọi dòng liên kết cùng khu. |
| `booking_id` | uuid | no |  | Lượt đặt bị ảnh hưởng bởi việc về sớm. → `booking` (kèm `zone_id`). |
| `trigger` | app.recovery_trigger | no | 'owner_early_return'::recovery_trigger | Lý do mở hồ sơ; MVP chỉ có `owner_early_return`. |
| `new_return_at` | timestamp with time zone | no |  | Giờ về mới, sớm hơn, của chủ chỗ. |
| `options` | jsonb | no | '[]'::jsonb | Mảng JSON các ô ứng viên và giá do rule engine tính; `[]` khi chưa tính. |
| `chosen_slot_id` | uuid | yes |  | Ô người thuê chọn trong các phương án. → `slot` (kèm `zone_id`). |
| `relocated_booking_id` | uuid | yes |  | Lượt đặt thay thế tạo cho người thuê. → `booking`. Bắt buộc khi `status = resolved`. |
| `approval_request_id` | uuid | yes |  | Chuyển lên BQL. → `approval_request`. Bắt buộc khi `status = escalated`. |
| `status` | app.recovery_status | no | 'open'::recovery_status | `open` · `options_ready` · `awaiting_consent` · `resolved` · `escalated` · `cancelled`. `resolved` và `cancelled` đóng hồ sơ. |
| `deadline_at` | timestamp with time zone | no |  | Hạn phải xử lý xong (trước khi chủ về). |
| `resolution_note` | text | yes |  | Ghi chú tự do về kết quả (không có dữ liệu cá nhân). |
| `idempotency_key` | text | no |  | Khóa do bên gọi cấp (`thread_id:step`); chạy lại sẽ chạm ràng buộc UNIQUE. |
| `version` | integer | no | 1 | Khóa lạc quan cho chỉnh sửa. |
| `created_at` | timestamp with time zone | no | now() | Thời điểm tạo (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Lần cập nhật cuối (trigger `set_updated_at`). |
