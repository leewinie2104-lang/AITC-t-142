# Từ điển dữ liệu — LPR, duyệt, thông báo (M8, M12, M13)

> Thuộc [từ điển dữ liệu](../03-data-dictionary.md). Ràng buộc, index, giá trị enum: [sql/schema.sql](../sql/schema.sql).

## Ra vào / LPR (M8)

### lpr_event

Sự kiện LPR đã chuẩn hóa. Bảng thường (không partition); chống trùng theo `(zone_id, source_code, source_event_id)` (BR-13).  
RLS: **có** (policy: `zone_staff`)

| Cột | Kiểu | Null | Mặc định | Ý nghĩa |
|---|---|---|---|---|
| `id` | bigint | no | identity | Khóa chính (UUIDv7, trừ khi kiểu là bigint). |
| `zone_id` | uuid | no |  | Khu sở hữu; dùng cho RLS. Khớp với cha qua FK ghép. |
| `source_code` | text | no |  | Mã nguồn LPR / hệ thống nhà cung cấp gửi sự kiện (`^[A-Z0-9_-]{1,32}$`); thuộc khóa chống trùng. |
| `source_event_id` | text | no |  | Mã sự kiện của nhà cung cấp; khóa chống trùng cùng khu và nguồn (BR-13). |
| `gate_code` | text | no |  | Mã cổng đã đọc biển số (`^[A-Z0-9_-]{1,32}$`); thay bảng `gate` đã bỏ. |
| `direction` | app.gate_direction | no |  | Giá trị trong tập cố định của kiểu / CHECK (xem ràng buộc). |
| `occurred_at` | timestamp with time zone | no |  | Thời điểm sự kiện tại cổng. |
| `received_at` | timestamp with time zone | no | now() | Thời điểm xảy ra sự việc mà tên cột mô tả (UTC); NULL = chưa xảy ra. |
| `plate_ciphertext` | bytea | yes |  | Biển số đọc được, đã mã hóa; giới hạn theo cột. |
| `plate_hash` | bytea | yes |  | Digest SHA-256 (32 byte); không bao giờ lưu giá trị gốc. |
| `plate_masked` | text | yes |  | Dạng hiển thị của biển số đọc được. |
| `ocr_confidence` | numeric(4,3) | no |  | 0–1. |
| `status` | app.lpr_status | no |  | accepted · pending_review · confirmed_manual · unreadable. |
| `matched_vehicle_id` | uuid | yes |  | Tham chiếu `vehicle`. |
| `matched_booking_id` | uuid | yes |  | Tham chiếu `booking`. |
| `reviewed_by` | uuid | yes |  | Tham chiếu `app_user`. |
| `reviewed_at` | timestamp with time zone | yes |  | Thời điểm xảy ra sự việc mà tên cột mô tả (UTC); NULL = chưa xảy ra. |

## Duyệt (M12)

### approval_request

Mục hàng chờ HITL cho BQL của khu có ô; mang `thread_id` LangGraph (FK tới `agent_thread`) để chạy tiếp. v7 (BR-26): chỉ ca vùng xám hoặc AI đáng ngờ lên BQL; loại mới `booking_review`, `registration_review`.  
RLS: **có** (policy: `zone_staff`)

| Cột | Kiểu | Null | Mặc định | Ý nghĩa |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Khóa chính (UUIDv7, trừ khi kiểu là bigint). |
| `zone_id` | uuid | no |  | Khu sở hữu; dùng cho RLS. Khớp với cha qua FK ghép. |
| `kind` | app.approval_kind | no |  | Giá trị trong tập cố định của kiểu / CHECK (xem ràng buộc). |
| `subject_id` | uuid | no |  | Thỏa thuận, lượt đặt hoặc hồ sơ tranh chấp (`dispute_case.id`) đang xét (theo `kind`: agreement_over_threshold · early_return_escalation · dispute_decision). |
| `thread_id` | text | no |  | Thread LangGraph chạy tiếp sau quyết định. → `agent_thread`. |
| `status` | app.approval_status | no | 'pending'::approval_status | Giá trị trong tập cố định của kiểu / CHECK (xem ràng buộc). |
| `summary` | text | yes |  | Như tên cột. |
| `requested_at` | timestamp with time zone | no | now() | Thời điểm xảy ra sự việc mà tên cột mô tả (UTC); NULL = chưa xảy ra. |
| `rule_result` | app.rule_result | yes |  | v7 (BR-26) lớp 1: `pass` · `reject` (không bao giờ vào hàng này) · `gray` (thiếu dữ liệu hoặc sát ngưỡng). NULL với loại không qua hai lớp. |
| `ai_risk` | app.ai_risk_review | yes |  | v7 (BR-26) lớp 2: `normal` (tự duyệt) · `suspicious` (BQL kèm lý do). AI chỉ siết. |
| `reasons` | jsonb | no | '[]'::jsonb | v7: lý do có nguồn `[{"code","text","source"}]`, đã ẩn danh. |
| `escalated_at` | timestamp with time zone | yes |  | v7: lúc chuyển lên BQL; NULL = quyết định không cần BQL. Chỉ có khi `gray` hoặc `suspicious` (CHECK). |
| `bql_deadline_at` | timestamp with time zone | yes |  | v7 (đổi tên từ `due_at`): `escalated_at` + `bql_review_ttl` (10 phút). Quá hạn → `expired`, `bql_decision = timed_out`, coi như từ chối (BR-26). |
| `bql_decision` | app.bql_decision | yes |  | v7: `approved` · `rejected` · `timed_out`. |
| `decided_by` | uuid | yes |  | Tham chiếu `app_user`. |
| `decided_at` | timestamp with time zone | yes |  | Thời điểm xảy ra sự việc mà tên cột mô tả (UTC); NULL = chưa xảy ra. |
| `decision_note` | text | yes |  | Như tên cột. |
| `updated_at` | timestamp with time zone | no | now() | Lần cập nhật cuối (trigger `set_updated_at`). |

## Thông báo (M13)

### notification

Thông báo trong app (M13). Ghi cùng transaction với thay đổi nghiệp vụ; idempotent qua `idempotency_key`. Đẩy realtime sau commit (4 tuần đầu: client polling).  
RLS: **có** (policy: `own_or_system`)

| Cột | Kiểu | Null | Mặc định | Ý nghĩa |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Khóa chính (UUIDv7, trừ khi kiểu là bigint). |
| `user_id` | uuid | no |  | Tham chiếu `app_user`. |
| `zone_id` | uuid | yes |  | Khu sở hữu; dùng cho RLS. Khớp với cha qua FK ghép. |
| `kind` | text | no |  | Giá trị trong tập cố định của kiểu / CHECK (xem ràng buộc). |
| `title` | text | no |  | Như tên cột. |
| `body` | text | no |  | Như tên cột. |
| `link` | jsonb | yes |  | Đích của deep link, ví dụ {"type":"agreement","id":…}. |
| `idempotency_key` | text | no |  | Khóa do bên gọi cấp (`thread_id:step`); chạy lại sẽ chạm ràng buộc UNIQUE. |
| `read_at` | timestamp with time zone | yes |  | Thời điểm xảy ra sự việc mà tên cột mô tả (UTC); NULL = chưa xảy ra. |
| `created_at` | timestamp with time zone | no | now() | Thời điểm tạo (UTC). |
