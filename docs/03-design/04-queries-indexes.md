# 04 — Truy vấn chính và index phục vụ chúng

> **Trạng thái v5:** chưa EXPLAIN với dữ liệu thật. Plan ở §2 bị ép bằng `enable_seqscan=off` trên bảng nhỏ, chỉ chứng minh có index dùng được;
> `lpr_event` (300 nghìn dòng) và `notification` (110 nghìn) đo ở v1/v2. Index của các bảng đã bỏ (outbox, sổ cái, refresh token, `staff_zone`,
> `audit_log`, voucher, hoán đổi, `overstay_case`, log xem biển số) hoãn cùng bảng ([08-deferred-tables](08-deferred-tables.md),
> [D-32](07-db-decision-log.md#d-32)). Q18–Q20 phục vụ các bảng mới ở v4; Q7, Q12, Q21 là của v5 (quá giờ, tranh chấp). SQL và plan đầy đủ: `git show feff7b5:docs/03-design/04-queries-indexes.md`.

**Nguyên tắc**
* Mỗi index phục vụ một truy vấn có tên; không có index "phòng hờ". FK chỉ có index khi bảng con được truy vấn hoặc xóa qua nó
  (kiểm tra RESTRICT quét bảng con khi xóa cha).
* Index một phần cho truy cập kiểu hàng chờ (`WHERE status = 'pending'`, `status NOT IN ('resolved','cancelled')`, `status = 'held'`): nhỏ vì dòng rời hàng chờ.
* Phân trang keyset ở mọi danh sách có thể dài (`ORDER BY created_at DESC, id DESC` + `(created_at, id) < ($1, $2)`); không `OFFSET` sau trang đầu.
* RLS thêm điều kiện `zone_id` / `user_id` vào mọi truy vấn; các truy vấn dưới đây bắt đầu bằng cột đó nên điều kiện policy dùng chung index.

## 1. Bản đồ truy vấn ↔ index

| # | Truy vấn (module / workflow) | Index | Loại và lý do | Chi phí ghi |
|---|------------------------------|-------|---------------|-------------|
| Q1 | Cấp của user tại một tòa (W1, mọi lần đặt) | `eligibility_user_idx` gist `(user_id, valid_during) WHERE status='verified'`; PK `asset` | GiST vì `valid_during @> now()` là điều kiện khoảng; một phần chỉ giữ dòng còn hiệu lực | Thấp: tư cách ít đổi |
| Q2 | Ghép: khung mở ở khu K phủ [s,e) + kích thước ô + chưa bị đặt (W1/W2, FR-07) | `share_window_match_idx` gist `(zone_id, bookable_period) WHERE status='open'`; `booking_no_overlap` gist (cũng là EXCLUDE) | Phép chứa khoảng cần GiST; anti-join dùng lại index EXCLUDE | Vừa: một GiST mỗi khung |
| Q3 | Lịch sử người thuê / người cho thuê, mới nhất trước (M5, M4) | `booking_renter_idx (renter_user_id, lower(period) DESC)`, `booking_provider_idx` một phần | Ghép: so bằng trước, cột sắp xếp sau → quét keyset theo index | Thấp |
| Q4 | Hàng chờ duyệt của BQL một khu (M12) | `approval_request_queue_idx (zone_id, requested_at) WHERE status='pending'`; `approval_request_pending_uq (kind, subject_id) WHERE status='pending'` | Một phần: chỉ dòng đang chờ | Không đáng kể |
| Q5 | Hàng chờ kiểm tra OCR (M8, BR-13) | `lpr_event_review_idx (zone_id, occurred_at) WHERE status='pending_review'` | Một phần: chỉ dòng OCR thấp (~2 %) | Thấp |
| Q6 | LPR → khớp xe, sự kiện gần đây của một biển số (N1) | `vehicle_plate_hash_idx` một phần; `lpr_event_plate_idx (plate_hash, occurred_at DESC)` | So bằng trên HMAC, rồi thời gian | Một B-tree mỗi sự kiện LPR |
| Q7 | N2 quá giờ: booking đã check-in, chưa check-out, sắp / đã hết giờ (W4, FR-11) | `booking_active_end_idx (zone_id, upper(period)) WHERE status='confirmed'`; lọc tiếp `checked_in_at IS NOT NULL AND checked_out_at IS NULL`; chống nhắc trùng bằng UNIQUE `notification.idempotency_key` (`overstay_pre:<id>`, `overstay_due:<id>`) | Một phần: chỉ booking đã xác nhận; quét ~5 phút một lần | Không thêm index |
| Q9 | Hộp thông báo, số chưa đọc (M13) | `notification_inbox_idx (user_id, created_at DESC, id DESC)`, `notification_unread_idx` một phần | Keyset; một phần cho đếm chưa đọc | Một B-tree mỗi insert (+1 khi chưa đọc) |
| Q10 | N6 tư cách sắp hết hạn | `eligibility_expiry_idx (upper(valid_during)) WHERE status='verified' AND NOT upper_inf(valid_during)` | Biểu thức + một phần: chủ sở hữu (không hết hạn) bị loại | Thấp |
| Q11 | Dọn giữ chỗ quá hạn | `booking_hold_expiry_idx (hold_expires_at) WHERE status='held'` | Một phần; OTP 3 phút, giữ chỗ tối đa 40 phút (TH3 60) | Thấp |
| Q12 | Hàng chờ tranh chấp của BQL một khu; tranh chấp lặp theo ô (M10, W5) | `dispute_case_queue_idx (zone_id, status, created_at DESC)`; `dispute_case_slot_idx (slot_id, created_at DESC)`; chống báo trùng `dispute_case_open_booking_uq`, `dispute_case_open_slot_uq` (một phần, khi còn mở) | So bằng khu rồi trạng thái; keyset theo thời gian | Thấp (tranh chấp hiếm) |
| Q13 | Bằng chứng xác nhận của một thỏa thuận / của một khu theo thời gian (M6) | `consent_record_subject_idx (subject_type, subject_id)`, `consent_record_zone_idx (zone_id, created_at DESC) WHERE zone_id IS NOT NULL`; khóa tự nhiên `consent_record_natural_uq` | So bằng theo đối tượng; keyset theo thời gian cho màn hình BQL | Hai B-tree + UNIQUE mỗi insert (bảng chỉ ghi thêm, tần suất thấp) |
| Q14 | Dashboard KPI (M12) | view `app.kpi_daily_v` trên `parking_request` (khu + ngày địa phương); `parking_request_kpi_idx (zone_id, created_at, outcome)` | Gom khi đọc; chỉ materialise nếu > 500 ms ([vận hành §5](../06-operations/03-database-monitoring-scaling.md)) | Không |
| Q15 | Đăng nhập bằng số điện thoại (ADR-0006); nhân viên của một khu | `app_user_phone_uq` unique một phần; `app_user_staff_zone_idx (staff_zone_id) WHERE staff_zone_id IS NOT NULL` | So bằng | Thấp |
| Q17 | Truy xuất RAG cho W7 | `knowledge_chunk_scope_idx (zone_id, building_id)` + quét vector chính xác; lọc `is_active` | Vài chục tài liệu → quét chính xác nhanh hơn ANN; thêm HNSW khi > ~50 nghìn đoạn | Không đáng kể |
| Q18 | Hội thoại của user, mới nhất trước (M14); thread chờ BQL quyết định | `agent_thread_user_idx (user_id, updated_at DESC)`; `agent_thread_zone_idx (zone_id) WHERE status='awaiting_manager'`; `approval_request_thread_idx (thread_id)` | Ghép cho danh sách user; một phần cho hàng chờ BQL | Thấp (một update mỗi lượt) |
| Q19 | Hồ sơ chủ về sớm đang mở của khu theo hạn (W3) | `recovery_case_zone_idx (zone_id, deadline_at) WHERE status NOT IN ('resolved','cancelled')`; `recovery_case_open_uq (booking_id)` UNIQUE một phần; `recovery_case_relocated_idx`, `recovery_case_slot_idx`, `recovery_case_approval_idx` | Một phần: hồ sơ đã đóng rời index | Thấp |
| Q20 | Quyết định AI theo khu, thread, lượt duyệt (màn hình kiểm toán BQL) | `ai_decision_log_zone_idx (zone_id, created_at DESC)`, `ai_decision_log_thread_idx (thread_id)`, `ai_decision_log_approval_idx` một phần; UNIQUE `idempotency_key` | Keyset theo thời gian; so bằng theo thread | Một bộ B-tree mỗi bước AI |
| Q21 | Bằng chứng của một hồ sơ theo thời gian; chống thu thập trùng (W5) | `dispute_evidence_case_idx (case_id, created_at)`; UNIQUE một phần `(case_id, lpr_event_id)`, `(case_id, consent_record_id)`, `(case_id, agreement_id)`, `(case_id, sha256) WHERE kind='photo'` | Keyset; UNIQUE làm W5 chạy lại không thêm trùng | Nhiều B-tree nhỏ mỗi insert (bảng chỉ ghi thêm) |

Q8 (relay outbox), Q16 (log xem biển số): hoãn cùng bảng. Q22 (v6, đổi v7): hàng chờ của tòa theo thứ tự `parking_request_queue_idx (building_id, queued_at) WHERE queue_status IN ('queued','eligible')`; khung thật sự trống `share_window_available_idx`. v7: quét tin hết hạn `share_window_listing_expiry_idx (expires_at)`; chỗ TH3 còn trống `app.th3_free_slots()` (ô TH3 hoạt động trừ `booking` đang giữ, dùng `booking_no_overlap` và `slot_zone_type_idx`); job OTP/giữ chỗ dùng `booking_hold_expiry_idx`. Q14: view `kpi_daily_v` gom `payment` (`overstay_fee` đã ghi nhận, `payment_recorded_uq`) và `dispute_case` (`dispute_case_queue_idx`).
Index FK chỉ thêm cho join / kiểm tra RESTRICT có thật (`slot_pool_id_idx`, `booking_share_window_idx`, `booking_request_idx`, `booking_vehicle_idx`,
`agreement_*_idx`, `slot_holding_user_idx`…); đích FK ghép dùng lại UNIQUE `(id, zone_id)`. Cố ý không index: `ai_decision_log.user_hash`,
`lpr_event.reviewed_by` (hiếm khi lọc; điều tra quét theo khoảng thời gian là đủ).

## 2. Truy vấn mẫu và ghi chú EXPLAIN

Đo trên PostgreSQL 17.10 với seed của `sql/seed-and-tests.sql`. Bảng khác chỉ vài dòng nên plan Q1–Q4, Q10 bị ép; trên dữ liệu thật planner
nên tự chọn vì điều kiện chọn lọc. Chạy lại bằng `EXPLAIN (ANALYZE, BUFFERS)` trên bản staging trước khi go-live.

- **Q1** (trong `app.eligibility_level_at`): `Nested Loop → Index Scan eligibility_user_idx → Index Scan asset_id_zone_id_key`; O(1) mỗi lần đặt.
- **Q2** (ghép cung): `Nested Loop Anti Join`, bên trong `Index Only Scan booking_no_overlap`. Trên bảng nhỏ planner dùng index EXCLUDE của
  khung; dữ liệu thật dự kiến dùng `share_window_match_idx`. **Cần kiểm trên staging.** Anti-join chỉ là gợi ý: EXCLUDE mới là thứ chặn đặt trùng.
- **Q3** `Index Scan booking_renter_idx`, không có bước sort · **Q5** index một phần `lpr_event_review_idx`, đọc 50 dòng ·
  **Q6** bitmap scan `lpr_event_plate_idx` · **Q9** `Index Scan notification_inbox_idx`, đọc 20 dòng bất kể trang sâu · **Q10** `eligibility_expiry_idx`.

## 3. Điểm nghẽn dự kiến

| Rủi ro | Ở đâu | Cách thiết kế này xử lý | Khi nào làm thêm |
|--------|-------|-------------------------|------------------|
| Phân trang sâu | hộp thông báo, lịch sử, bằng chứng, nhật ký AI, dòng thời gian LPR | Con trỏ keyset + index ghép tương ứng | — |
| `LIKE '%x%'` | tài liệu không yêu cầu | Chưa làm. Tìm kiếm mờ đầu tiên (BQL tìm user theo tên) → GIN `pg_trgm` trên `lower(unaccent(full_name))` | Khi có tính năng |
| Bảng phình | `lpr_event` | Bảng thường, đủ cho demo; MVP không có job xóa | Trước khi có LPR thật: partition theo tháng + hạn lưu ([08-deferred-tables](08-deferred-tables.md)) |
| | `notification`, `ai_decision_log`, `consent_record` | `notification` xóa theo TTL bằng job (không có trong MVP); hai bảng còn lại chỉ ghi thêm, không xóa trong MVP; partition khi > ~50 triệu dòng | [Vận hành §5](../06-operations/03-database-monitoring-scaling.md) |
| Dòng nóng | `share_window` / `booking` của ô đông khách | EXCLUDE chỉ khóa mức dòng của index; không có dòng đếm | — |
| Truy vấn N+1 | ghép, hộp thông báo | Ghép là một truy vấn tập hợp (Q2) | Quy tắc review code |
| Báo cáo nặng | KPI | View `app.kpi_daily_v` (chỉ số tổng hợp) tính khi đọc | Materialise hằng đêm, rồi read replica khi báo cáo > ~10 % CPU primary |
| Chi phí RLS | mọi truy vấn | Hàm ngữ cảnh bọc trong `(SELECT …)` → tính một lần mỗi truy vấn (InitPlan); policy bắt đầu bằng cột có index | Đo bằng `pg_stat_statements` |
| Chi phí trigger khi đặt | `booking_validate` (3 tra cứu + hàm tính cấp) | Đều là tra PK / index; ~5 lần đọc index mỗi insert | Booking tần suất thấp (AS-01: ~15/phút) |
