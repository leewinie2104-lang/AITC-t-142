# Từ điển dữ liệu — Tranh chấp (M10, W5; v5)

> Thuộc [từ điển dữ liệu](../03-data-dictionary.md). Ràng buộc, index, giá trị enum: [sql/schema.sql](../sql/schema.sql).
> Hai bảng thay bốn bảng `dispute_*` của v2 ([08-deferred-tables](../08-deferred-tables.md), [D-33](../07-db-decision-log.md#d-33)).

### dispute_case

Hồ sơ tranh chấp do cư dân báo tại ô S; nằm trong khu của S nên đến đúng BQL (BR-18). AI chỉ gợi ý (BR-14); BQL quyết định qua `approval_request` loại `dispute_decision`. `description` lưu sau khi ẩn biển số (BR-09).  
RLS: **có** (policy: `zone_staff`, `system_all`, `parties_read`, `reporter_insert`)

| Cột | Kiểu | Null | Mặc định | Ý nghĩa |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Khóa chính. |
| `ref_no` | bigint | no | identity | Số hiển thị (TC-0031); UNIQUE. |
| `zone_id` | uuid | no |  | Khu của ô; dùng cho RLS. FK ghép `(slot_id, zone_id)`, `(booking_id, zone_id)`, `(approval_request_id, zone_id)`. |
| `slot_id` | uuid | no |  | Ô bị báo. |
| `booking_id` | uuid | yes |  | Lượt đặt liên quan (nếu có). |
| `reporter_user_id` | uuid | no |  | Người báo. → `app_user`. |
| `respondent_user_id` | uuid | yes |  | Bên bị báo, suy ra từ booking / khớp LPR (hash biển số); khác người báo. |
| `category` | app.dispute_category | no |  | slot_occupied · overstay · wrong_vehicle · damage · other. |
| `description` | text | no |  | Mô tả, không rỗng, đã ẩn biển số. |
| `status` | app.dispute_status | no | 'open' | open · collecting_evidence · awaiting_decision · resolved · dismissed. |
| `ai_summary` | text | yes |  | Tóm tắt gợi ý đã ẩn danh; không phải phán quyết. |
| `ai_confidence` | numeric(4,3) | yes |  | 0–1. |
| `thread_id` | text | yes |  | Thread W5. → `agent_thread`. |
| `approval_request_id` | uuid | yes |  | Quyết định HITL của BQL. |
| `ready_at` | timestamptz | yes |  | Hồ sơ đủ bằng chứng; bắt buộc từ `awaiting_decision`; đo KPI thời gian lập hồ sơ. |
| `resolution_code` | text | yes |  | fee_waived · upheld · rejected · other; chỉ khi `resolved` / `dismissed`. `fee_waived`: payment `overstay_fee` chuyển `cancelled`. |
| `resolution_note` | text | yes |  | Ghi chú của BQL. |
| `resolved_by` | uuid | yes |  | BQL quyết định; cùng `resolved_at`, có đúng khi `resolved` / `dismissed`. |
| `resolved_at` | timestamptz | yes |  | Thời điểm quyết định. |
| `idempotency_key` | text | no |  | UNIQUE (`thread_id:step` hoặc mã yêu cầu của client). |
| `version` | integer | no | 1 | Khóa lạc quan. |
| `created_at` | timestamptz | no | now() | Thời điểm tạo (UTC). |
| `updated_at` | timestamptz | no | now() | Lần cập nhật cuối (trigger `set_updated_at`). |

RLS `reporter_insert`: cư dân chỉ tạo hồ sơ `open` cho chính mình, không đặt được `respondent_user_id`, trường AI hay trường quyết định; chỉ gắn booking mà họ là một bên và `agent_thread` của chính họ; W5 / system suy ra bên bị báo.

Chống báo trùng: UNIQUE một phần `(reporter_user_id, booking_id, category)` khi còn mở, và `(reporter_user_id, slot_id, category)` khi không có booking.

### dispute_evidence

Bằng chứng của hồ sơ; **chỉ ghi thêm** (`reject_mutation()`, vai trò app chỉ INSERT/SELECT). Mô hình thị giác chỉ nhận ảnh đã làm mờ (BR-14). Mỗi loại chỉ dùng các cột của nó (CHECK).  
RLS: **có** (policy: `zone_staff`, `system_all`, `parties_read`, `reporter_insert`)

| Cột | Kiểu | Null | Mặc định | Ý nghĩa |
|---|---|---|---|---|
| `id` | bigint | no | identity | Khóa chính. |
| `zone_id` | uuid | no |  | Khu của hồ sơ. FK ghép `(case_id, zone_id)` và `(agreement_id, zone_id)`. |
| `case_id` | uuid | no |  | Hồ sơ. → `dispute_case`. |
| `kind` | app.evidence_kind | no |  | photo · lpr_event · consent_record · agreement · ai_vision_extraction · note. |
| `source` | text | no |  | reporter · system · zone_manager; khác `system` thì bắt buộc `submitted_by`. |
| `object_key_masked` | text | yes |  | Khóa object ảnh đã làm mờ: ảnh duy nhất được hiện (photo). |
| `object_key_original` | text | yes |  | Khóa ảnh gốc (photo); **thu quyền SELECT với vai trò app** như `plate_ciphertext`. |
| `sha256` | bytea | yes |  | Hash ảnh (32 byte); UNIQUE cùng `case_id` cho photo. |
| `lpr_event_id` | bigint | yes |  | Sự kiện LPR (loại lpr_event); UNIQUE cùng `case_id`. |
| `consent_record_id` | bigint | yes |  | Bản ghi xác nhận (loại consent_record); UNIQUE cùng `case_id`. |
| `agreement_id` | uuid | yes |  | Thỏa thuận (loại agreement); UNIQUE cùng `case_id`. |
| `snapshot` | jsonb | yes |  | Bản sao sự kiện LPR (cổng, hướng, giờ, biển số ẩn, OCR) để bằng chứng sống qua hạn lưu LPR 90 ngày (D-05); kết quả thị giác; hoặc `{"text": …}`. Không bao giờ chứa bản mã. |
| `confidence` | numeric(4,3) | yes |  | Độ tin cậy OCR / thị giác, hiện là "Gợi ý". |
| `submitted_by` | uuid | yes |  | Người nộp; NULL cho dòng system. → `app_user`. |
| `created_at` | timestamptz | no | now() | Thời điểm tạo (UTC). |
