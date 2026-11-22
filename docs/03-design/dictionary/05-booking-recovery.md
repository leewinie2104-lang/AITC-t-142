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
| `assigned_at` | timestamp with time zone | yes |  | v7 (BR-22): lúc được gán; bắt đầu cửa sổ OTP nhận chỗ (3 phút, `zone_policy.otp_confirm_ttl`). |
| `renter_otp_confirmed_at` | timestamp with time zone | yes |  | v7 (BR-25): lúc người thuê nhập OTP "nhận chỗ, đồng ý bị trừ tiền". Có → khoản `share_booking` được ghi và lượt bắt đầu giữ. Không lưu mã OTP. |
| `hold_expires_at` | timestamp with time zone | yes |  | Bắt buộc khi đang held. v7 (BR-22): trước OTP = `assigned_at` + 3 phút; sau OTP = ETA + `hold_after_eta` (10 phút), tối đa `hold_max` (40), TH3 `th3_hold_max` (60). |
| `no_show_fee_vnd` | bigint | yes |  | v7 (BR-22): phí không tới, chỉ khi `status = 'expired'` và đã có OTP: max(`no_show_fee_rate` × giá, `no_show_min_hours` giờ giá). Phần còn lại hoàn qua `payment` `cancel_refund`. |
| `checked_in_at` | timestamp with time zone | yes |  | Lúc xe vào, N1 đặt từ một `lpr_event` có `matched_booking_id` là lượt này. NULL = chưa đến. Bảng `parking_session` riêng quay lại cùng W4 quá giờ. |
| `checked_out_at` | timestamp with time zone | yes |  | Lúc xe ra (cùng nguồn). Chỉ đặt sau `checked_in_at` và không sớm hơn (CHECK `booking_check_times`). |
| `relocated_from_booking_id` | uuid | yes |  | Lượt gốc khi đây là lượt TH3 thay thế sau chủ về sớm. → `booking`. |
| `idempotency_key` | text | no |  | Khóa do bên gọi cấp (`thread_id:step`); chạy lại sẽ chạm ràng buộc UNIQUE. |
| `version` | integer | no | 1 | Khóa lạc quan cho chỉnh sửa từ người dùng. |
| `created_at` | timestamp with time zone | no | now() | Thời điểm tạo (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Lần cập nhật cuối (trigger `set_updated_at`). |

### recovery_case

W3 (chủ về sớm, Ưu tiên 2). v6 (D-36, ADR-0014): người thuê được ưu tiên. Rule engine điền `options` (ô khác còn trống cho người thuê); LLM chỉ diễn đạt (BR-14). Người thuê `move` → lượt đỗ thay thế; `stay` hoặc không trả lời → chủ nhận ô TH3 dự phòng. Tối đa một hồ sơ mở mỗi lượt đặt.  
RLS: **có** (policy: `parties_read`, `zone_staff`)

| Cột | Kiểu | Null | Mặc định | Ý nghĩa |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Khóa chính (UUIDv7). |
| `zone_id` | uuid | no |  | Khu của lượt đặt; dùng cho RLS. FK ghép giữ mọi dòng liên kết cùng khu. |
| `booking_id` | uuid | no |  | Lượt đặt bị ảnh hưởng bởi việc về sớm. → `booking` (kèm `zone_id`). |
| `trigger` | app.recovery_trigger | no | 'owner_early_return'::recovery_trigger | Lý do mở hồ sơ; MVP chỉ có `owner_early_return`. |
| `new_return_at` | timestamp with time zone | no |  | Giờ về dự kiến (ETA) của chủ; không lưu tọa độ. |
| `eta_source` | app.eta_source | no | 'manual'::eta_source | v7: `gps` (vị trí một lần, có đồng ý `location_share`; đổi tên từ `location`) hoặc `manual` (chủ chọn 15 / 30 / 60 phút). `none` chỉ dùng ở `parking_request`. |
| `renter_decision` | app.relocation_decision | yes |  | v6: `move` / `stay`; NULL tới khi người thuê trả lời (quá `deadline_at` thì W3 ghi `stay`). |
| `owner_buffer_slot_id` | uuid | yes |  | v6: ô TH3 dự phòng cấp cho chủ khi người thuê ở lại; miễn phí. → `slot` (kèm `zone_id`). Không có khi `move` (CHECK `recovery_case_move_has_no_buffer`). |
| `options` | jsonb | no | '[]'::jsonb | Mảng JSON các ô ứng viên và giá do rule engine tính; `[]` khi chưa tính. |
| `chosen_slot_id` | uuid | yes |  | Ô người thuê chọn trong các phương án. → `slot` (kèm `zone_id`). |
| `relocated_booking_id` | uuid | yes |  | Lượt đặt thay thế khi người thuê dời. → `booking`. `resolved` cần (`move` + cột này) hoặc (`stay` + `owner_buffer_slot_id`). |
| `approval_request_id` | uuid | yes |  | Chuyển lên BQL. → `approval_request`. Bắt buộc khi `status = escalated`. |
| `status` | app.recovery_status | no | 'open'::recovery_status | `open` · `options_ready` · `awaiting_consent` · `resolved` · `escalated` · `cancelled`. `resolved` và `cancelled` đóng hồ sơ. |
| `deadline_at` | timestamp with time zone | no |  | Hạn người thuê trả lời (mặc định ETA − 5 phút). |
| `resolution_note` | text | yes |  | Ghi chú tự do về kết quả (không có dữ liệu cá nhân). |
| `idempotency_key` | text | no |  | Khóa do bên gọi cấp (`thread_id:step`); chạy lại sẽ chạm ràng buộc UNIQUE. |
| `version` | integer | no | 1 | Khóa lạc quan cho chỉnh sửa. |
| `created_at` | timestamp with time zone | no | now() | Thời điểm tạo (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Lần cập nhật cuối (trigger `set_updated_at`). |
