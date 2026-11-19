# Từ điển dữ liệu — Thỏa thuận, bằng chứng, thanh toán (M6, M7)

> Thuộc [từ điển dữ liệu](../03-data-dictionary.md). Ràng buộc, index, giá trị enum: [sql/schema.sql](../sql/schema.sql).

## Thỏa thuận và bằng chứng xác nhận (M6)

### agreement

Thỏa thuận điện tử cho lượt TH1/TH2 (FR-08); hiệu lực sau khi đủ hai xác nhận (+ duyệt nếu vượt ngưỡng). Mỗi lần xác nhận cũng ghi một dòng `consent_record` (FR-09). OTP xác nhận nằm trong Redis, không ở đây.  
RLS: **có** (policy: `parties_read`, `zone_staff`)

| Cột | Kiểu | Null | Mặc định | Ý nghĩa |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Khóa chính (UUIDv7, trừ khi kiểu là bigint). |
| `zone_id` | uuid | no |  | Khu sở hữu; dùng cho RLS. Khớp với cha qua FK ghép. |
| `booking_id` | uuid | no |  | Tham chiếu `booking`. |
| `zone_policy_id` | uuid | no |  | Phiên bản nội quy đã định giá. → `zone_policy`. |
| `provider_user_id` | uuid | no |  | Tham chiếu `app_user`. |
| `renter_user_id` | uuid | no |  | Tham chiếu `app_user`. |
| `price_vnd` | bigint | no |  | Số tiền VND (số nguyên, ≥ 0). |
| `body_rendered` | text | no |  | Nội dung chính xác hai bên đã xác nhận. |
| `body_sha256` | bytea | no |  | Hash nội dung thỏa thuận; chép vào `consent_record.evidence.body_sha256` khi từng bên xác nhận. |
| `status` | app.agreement_status | no | 'pending_confirmation'::agreement_status | Giá trị trong tập cố định của kiểu / CHECK (xem ràng buộc). |
| `requires_approval` | boolean | no |  | Rule engine đặt khi giá > ngưỡng. |
| `approval_request_id` | uuid | yes |  | Tham chiếu `approval_request`. |
| `confirm_deadline` | timestamp with time zone | no |  | Quá thời điểm này, thỏa thuận hết hạn. |
| `provider_confirmed_at` | timestamp with time zone | yes |  | Thời điểm xảy ra sự việc mà tên cột mô tả (UTC); NULL = chưa xảy ra. |
| `renter_confirmed_at` | timestamp with time zone | yes |  | Thời điểm xảy ra sự việc mà tên cột mô tả (UTC); NULL = chưa xảy ra. |
| `effective_at` | timestamp with time zone | yes |  | Thời điểm xảy ra sự việc mà tên cột mô tả (UTC); NULL = chưa xảy ra. |
| `created_at` | timestamp with time zone | no | now() | Thời điểm tạo (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Lần cập nhật cuối (trigger `set_updated_at`). |

### consent_record

Bằng chứng đồng ý và xác nhận, chỉ ghi thêm (A-03, BR-09, FR-09, AC-07). Một dòng khi người dùng chấp nhận điều khoản đăng ký hoặc xử lý biển số, khi từng bên xác nhận thỏa thuận, và khi người thuê chấp nhận chuyển chỗ. Thay `app_user.consent_*` và vai trò bằng chứng của sổ cái đã bỏ. Không bao giờ sửa / xóa (trigger `reject_mutation()`; vai trò app chỉ INSERT + SELECT).  
RLS: **có** (policy: `own`, `own_insert`, `system_all`, `zone_manager_read`)

| Cột | Kiểu | Null | Mặc định | Ý nghĩa |
|---|---|---|---|---|
| `id` | bigint | no | identity | Khóa chính (identity); cũng là thứ tự sự kiện. |
| `user_id` | uuid | no |  | Ai đồng ý hoặc xác nhận. → `app_user`. |
| `zone_id` | uuid | yes |  | Khu của đối tượng; NULL với điều khoản toàn chuỗi như đăng ký. → `zone`. BQL khu đó đọc được dòng. |
| `action` | app.consent_action | no |  | `registration_terms` · `plate_processing` · `agreement_confirm` · `accept_relocation`. |
| `subject_type` | text | no |  | Loại bản ghi được đồng ý: `app_user`, `agreement` hoặc `recovery_case` (CHECK). |
| `subject_id` | uuid | no |  | Id của bản ghi đó (đa hình có chủ đích: nhật ký bằng chứng, không FK). |
| `terms_version` | text | no |  | Phiên bản điều khoản hoặc nội dung thỏa thuận đã hiển thị. |
| `decision` | app.consent_decision | no |  | `accepted` · `rejected` · `withdrawn`. |
| `evidence` | jsonb | no | '{}'::jsonb | JSON object chỉ chứa id, hash và số tiền, ví dụ `body_sha256` (hash nội dung thỏa thuận), giá, phiên bản nội quy. Không tên, không biển số. |
| `created_at` | timestamp with time zone | no | now() | Thời điểm tạo (UTC). |

## Thanh toán (M7)

### payment

Thanh toán VietQR mô phỏng (A-05, Ưu tiên 2). `amount_vnd` là khoản thu hoặc hoàn (MVP không có voucher).  
RLS: **có** (policy: `payer`, `zone_staff`)

| Cột | Kiểu | Null | Mặc định | Ý nghĩa |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Khóa chính (UUIDv7, trừ khi kiểu là bigint). |
| `zone_id` | uuid | no |  | Khu sở hữu; dùng cho RLS. Khớp với cha qua FK ghép. |
| `booking_id` | uuid | no |  | Tham chiếu `booking`. |
| `payer_user_id` | uuid | no |  | Tham chiếu `app_user`. |
| `kind` | app.payment_kind | no |  | Giá trị trong tập cố định của kiểu / CHECK (xem ràng buộc). |
| `amount_vnd` | bigint | no |  | Số tiền VND (số nguyên, ≥ 0); cột direction cho biết thu hay hoàn. |
| `direction` | text | yes | 
CASE
    WHEN (kind = 'early_return_refund'::payment_kind) THEN 'refund'::text
    ELSE 'charge'::text
END | Sinh tự động: refund cho early_return_refund, còn lại là charge (D-09). |
| `provider` | text | no | 'vietqr_mock'::text | Chỉ `vietqr_mock` (A-05). |
| `status` | app.payment_status | no | 'pending'::payment_status | Giá trị trong tập cố định của kiểu / CHECK (xem ràng buộc). |
| `idempotency_key` | text | no |  | Khóa do bên gọi cấp (`thread_id:step`); chạy lại sẽ chạm ràng buộc UNIQUE. |
| `paid_at` | timestamp with time zone | yes |  | Thời điểm xảy ra sự việc mà tên cột mô tả (UTC); NULL = chưa xảy ra. |
| `created_at` | timestamp with time zone | no | now() | Thời điểm tạo (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Lần cập nhật cuối (trigger `set_updated_at`). |
