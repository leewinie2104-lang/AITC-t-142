# 02 — Sơ đồ thực thể – quan hệ (ERD)

Bốn sơ đồ, mỗi vùng một sơ đồ, mỗi sơ đồ một file trong `erd/` cho dễ đọc. Chúng phủ **25 bảng** của schema MVP v5 ([ADR-0011](../07-adr/ADR-0011-mvp-simplifications.md)).
Chỉ vẽ khóa và cột giải thích quan hệ; danh sách cột đầy đủ ở [03-data-dictionary](03-data-dictionary.md), bản vẽ mức cột của mọi bảng ở
[diagrams/schema-diagram.html](diagrams/schema-diagram.html). `zone_id` có mặt ở gần như mọi bảng: đó là khóa RLS, và FK ghép
`(x_id, zone_id)` giữ nó khớp với cha (xem [01-data-model §4.3](01-data-model.md#4-quyết-định-chính)).

30 bảng của v2 và 8 bảng của v3 không có trong MVP (chain, subzone, basement, gate, voucher, hoán đổi, bảng báo cáo; bốn bảng tranh chấp của v2 được thay bằng 2 bảng ở v5; ở v4:
`staff_zone`, `refresh_token`, `otp_challenge`, sổ cái, `outbox`, `idempotency_keys`, `audit_log`) được liệt kê cùng phần thay thế trong
[08-deferred-tables](08-deferred-tables.md); chúng không xuất hiện bên dưới.

## 1. Cơ sở vật chất, người dùng, tư cách

Sơ đồ: [erd/01-facility-people.md](erd/01-facility-people.md).

* **Zone → Building → Slot** là cây cơ sở vật chất của PRD §2. Phân khu và tầng hầm là cột thường (`building.subzone_code`,
  `slot.level_code`), hạng kích thước là enum có thứ tự, nên BR-11 là `vehicle.size_class <= slot.size_class`. Mọi liên kết là
  `ON DELETE RESTRICT`: cơ sở vật chất ngừng dùng bằng `is_active = false` (ô dùng `slot.operational_status`), không bao giờ xóa,
  vì booking và bằng chứng xác nhận trỏ tới chúng.
* **Slot pool** mang phạm vi mở. Loại của ô phải bằng loại của pool (FK ghép `(pool_id, slot_type, zone_id)`); CHECK của pool áp bảng
  PRD §4 (TH1 ≤ khu, TH2 ≤ chuỗi khi chủ đầu tư đồng ý, TH3 = công cộng).
* **Eligibility** là quan hệ M:N giữa `app_user` và `asset`, mang vai trò và hạn. EXCLUDE cấm hai tư cách còn hiệu lực cho cùng
  (user, asset, role) chồng thời gian.
* **Slot holding** là quan hệ M:N theo thời gian giữa `app_user` và `slot` (ai được chia sẻ ô TH1/TH2). Ô TH3 không có người giữ
  (CHECK theo `slot_type`). Dòng cũ đóng (`voided_at`) rồi mở dòng mới, nên lịch sử còn nguyên.
* **Staff zone** là FK cho phép NULL `app_user.staff_zone_id`: một khu cho mỗi thành viên BQL hoặc bảo vệ (CHECK: chỉ `guard` /
  `zone_manager`), nguồn của claim JWT `zone_ids` = `{staff_zone_id}`. Thay bảng nối `staff_zone` của v3 (ADR-0011).
* Con duy nhất bị xóa theo khi xóa user là `notification`. Thực tế user chỉ xóa mềm, nên cascade chỉ ảnh hưởng dữ liệu test.

## 2. Chia sẻ, đặt chỗ, thỏa thuận, bằng chứng, chủ về sớm, tiền

Sơ đồ: [erd/02-sharing-money.md](erd/02-sharing-money.md).

* **share_window → booking:** booking TH1/TH2 tham chiếu khung qua `(share_window_id, slot_id, provider_user_id)`, nên ô và người
  cho thuê chắc chắn là của khung đó. Booking TH3 không có khung và người cho thuê (CHECK + trigger).
* **booking → booking** (`relocated_from_booking_id`): booking TH3 thay thế khi chủ về sớm trỏ về booking nó thay.
* **booking 1–0..1 agreement** (UNIQUE `booking_id`): chỉ booking TH1/TH2 chia sẻ có thỏa thuận; lượt TH3 là biên lai của khu (PRD §7).
* **agreement → zone_policy:** ghim đúng phiên bản nội quy đã dùng. Bảng giá (`zone_policy.prices`) và nội dung mẫu
  (`zone_policy.agreement_template_md`) nằm trong dòng nội quy, nên nội quy đổi sau không làm đổi thỏa thuận đã ký.
* **consent_record** cố ý *không* có FK tới đối tượng (`subject_type`, `subject_id`): đây là nhật ký bằng chứng bất biến, phải sống lâu
  hơn và mô tả được mọi dòng; tham chiếu đa hình là đánh đổi thường gặp. Xác nhận thỏa thuận mang `evidence.body_sha256` (hash nội dung
  thỏa thuận). OTP nằm trong Redis nên không có bảng OTP. Chỉ ghi thêm nhờ trigger `reject_mutation()`; khóa tự nhiên
  `UNIQUE (user_id, action, subject_id, terms_version, decision)`.
* **recovery_case → booking:** FK ghép `(booking_id, zone_id)`, `(relocated_booking_id, zone_id)`, `(chosen_slot_id, zone_id)`,
  `(approval_request_id, zone_id)` giữ mọi dòng liên kết cùng khu. Index UNIQUE một phần `(booking_id) WHERE status NOT IN
  ('resolved','cancelled')` cho phép một hồ sơ mở mỗi booking; CHECK bắt buộc `relocated_booking_id` khi `resolved` và
  `approval_request_id` khi `escalated`.

## 3. Vận hành: LPR, duyệt, thread Agent, kiểm toán AI, báo cáo

Sơ đồ: [erd/03-operations.md](erd/03-operations.md). `kpi_daily_v` là view trên `parking_request`, `payment`, `dispute_case` và `zone` (không phải bảng): thay bảng
`kpi_daily` của v2 và tự lọc dòng theo vai trò và khu.

* **lpr_event** là bảng thường (MVP không partition). Khóa chống trùng `(zone_id, source_code, source_event_id)` (BR-13 / AC-10a). Cổng
  và nguồn là mã chữ; ngưỡng OCR đọc từ `zone_policy.ocr_review_threshold`. Biển số lưu dạng bản mã, hash và bản ẩn; MVP chỉ hiện bản ẩn.
* **approval_request.subject_id** đa hình theo `kind` (thỏa thuận vượt ngưỡng, chuyển lên BQL khi chủ về sớm). FK ngược
  `agreement.approval_request_id` giữ toàn vẹn ở chỗ cần. `approval_request.thread_id` là FK tới `agent_thread(thread_id)`.
* **agent_thread:** một dòng mỗi thread LangGraph; `pending_card` đã ẩn danh, không lưu tin nhắn gốc (BR-14, D-12); state graph nằm
  trong checkpointer (schema `agent`).
* **ai_decision_log** chỉ ghi thêm, chỉ chứa hash và id. FK (`thread_id`, `zone_id`, `approval_request_id`) cho phép NULL và `RESTRICT`;
  `idempotency_key` = `thread_id:checkpoint_id:node`.
* **knowledge_chunk** tự mang thông tin tài liệu (`doc_title`, `source_uri`, `doc_version`); bảng `knowledge_doc` của v2 đã bỏ.
  `zone_id` và `building_id` là FK thật.
* Bỏ cùng bảng của chúng: phiên đỗ và hồ sơ quá giờ (`overstay_case`), log xem biển số, hoán đổi, dự báo, công suất, đối soát, yêu cầu quyền riêng tư,
  quy tắc lưu trữ, workflow run (vai trò của `workflow_run` nay là `agent_thread`). Xem [08-deferred-tables](08-deferred-tables.md).

## 4. Tranh chấp (v5, W5)

Sơ đồ: [erd/04-disputes.md](erd/04-disputes.md).

* **dispute_case** nằm trong khu của ô bị báo (BR-18): FK ghép `(slot_id, zone_id)`, `(booking_id, zone_id)`, `(approval_request_id, zone_id)`
  giữ mọi liên kết cùng khu. Người báo và bên bị báo là FK `app_user`; quyết định của BQL đi qua `approval_request` loại `dispute_decision`.
  UNIQUE một phần chặn báo trùng khi hồ sơ còn mở. Policy `reporter_insert`: cư dân chỉ tạo hồ sơ `open` cho mình, không đặt bên bị báo, trường AI hay quyết định; chỉ gắn booking mà họ là một bên và thread của chính họ.
* **dispute_evidence** chỉ ghi thêm (`reject_mutation()`), FK ghép `(case_id, zone_id)` và `(agreement_id, zone_id)`; `lpr_event` và
  `consent_record` chưa có UNIQUE `(id, zone_id)` nên FK thường, việc khớp khu là quy tắc ứng dụng và RLS che khu khác. Khóa ảnh gốc
  `object_key_original` không SELECT được với vai trò app; chỉ ảnh đã làm mờ được hiện và gửi cho mô hình thị giác (BR-14).
* **Quá giờ không có bảng:** cột `zone_policy.overstay_*`, loại `payment.kind = 'overstay_fee'` và hồ sơ tranh chấp loại `overstay` để miễn phí.

## 5. Chính sách ON DELETE (tóm tắt)

| Chính sách | Ở đâu | Vì sao |
|------------|-------|--------|
| `RESTRICT` (mặc định cho FK nghiệp vụ) | cây cơ sở vật chất, user có lịch sử, booking, thỏa thuận, bằng chứng, duyệt, thread Agent, nhật ký AI, hồ sơ và bằng chứng tranh chấp | Lịch sử nghiệp vụ không được mất qua cascade. Ngừng dùng bằng `is_active` / xóa mềm |
| `CASCADE` | dữ liệu phụ riêng của user (`notification`) | Con không có nghĩa khi không còn cha |
| `SET NULL` | `lpr_event.matched_vehicle_id/matched_booking_id`, `zone_policy.created_by` | Liên kết ngữ cảnh tùy chọn trên log; mất liên kết không được chặn việc xóa dữ liệu test |

`lpr_event.reviewed_by` giữ `RESTRICT` vì một CHECK bắt buộc nó trên dòng đã kiểm tra (D-27).
