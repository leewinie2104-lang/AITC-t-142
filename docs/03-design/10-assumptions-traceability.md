# 10 — Giả định và truy vết yêu cầu → schema

> Tách từ [01-data-model](01-data-model.md) cho file ngắn. Lý do của các giá trị mặc định: [07-db-decision-log](07-db-decision-log.md).
> Dòng ghi **hoãn** trỏ tới đối tượng chỉ có trong thiết kế v2; xem [08-deferred-tables](08-deferred-tables.md).

## 1. Giả định

| ID | Giả định | Nguồn / lý do |
|----|----------|---------------|
| AS-01 | **Quy mô (tài liệu không nêu): vừa.** ~20 khu, ~300 nghìn user, ~150 nghìn ô; ~200 nghìn sự kiện LPR/ngày, giữ 90 ngày (≈ 18 triệu dòng, D-05; chỉ là mục tiêu); ~5 triệu booking/năm. Demo có 3 khu. Chốt ở D-17 | PRD §9 "mục tiêu hiệu năng: TBD" |
| AS-02 | Nhắm **PostgreSQL 16** (compose `pgvector:pg16`, RDS 16). DDL tránh tính năng chỉ có ở PG17 | `docker-compose.yml`, ADR-0005 |
| AS-03 | Tiền là VND số nguyên (`bigint`). Rule engine tính giá; DB lưu kết quả | PRD §8 |
| AS-04 | Mỗi khu một múi giờ (mặc định `Asia/Ho_Chi_Minh`) quyết định ngày làm việc (đối soát, "hết hạn ngày D") | Một thành phố (Brief §1) |
| AS-05 | Hết hạn tư cách được kiểm lúc dùng (`valid_during @> now()`), không phụ thuộc job N6 | Ghi chú N6 trong backlog |
| AS-06 | Shophouse thấp tầng không thuộc tòa (`asset.building_id IS NULL`) → chủ là L2 của khu; shophouse khối đế thuộc tòa → L1 ở tòa đó | Scope A-10 |
| AS-07 | Giữ một ô đỗ **không** tự tạo cấp tư cách; cấp đến từ căn hộ / shophouse / văn phòng. Quyền dùng ô nằm trong `slot_holding`. Chốt ở D-18 | PRD §3.1 |
| AS-08 | Dự phòng cấu hình theo khu (trước và sau khung); khung của chủ trừ dự phòng là thời gian đặt được | FR-06, AC-05 |
| AS-09 | Pool: TH1 theo tòa; TH2 và TH3 theo khu | PRD §4, AC-20 |
| AS-10 | *(hoãn cùng M11)* Hoán đổi chuyển **quyền sử dụng** (`slot_holding` loại `swap_usage`), không chuyển sở hữu | Scope §2 |
| AS-11 | Phí quá giờ là một `payment` loại `overstay_fee` (v5, D-33): người trả = người thuê, người nhận = người cho thuê hoặc khu với booking TH3; tính bằng `zone_policy.overstay_*` (phiên bản hiệu lực lúc hết giờ) | BR-08, FR-12 |
| AS-12 | App không xóa cứng user; xóa dữ liệu (hoãn, D-14) = xóa mềm + xóa dữ liệu cá nhân. Vì thế FK tới user là `ON DELETE RESTRICT` | Bằng chứng và lịch sử phải còn (PRD §9) |
| AS-13 | Mã hóa biển số: **AES-256-GCM ở app, khóa bọc KMS + HMAC blind index** (D-07); đề xuất sửa ADR-0005 ở [09](09-adr-0005-amendment-proposal.md) | 01-data-model §4.6 |
| AS-14 | File ảnh lưu ở S3, không trong DB; DB giữ object key (bản làm mờ và bản gốc) và SHA-256; ảnh làm mờ chuẩn bị tay cho demo | FR-13 |
| AS-15 | Embedding 1024 chiều | ADR-0007 chưa chọn model embedding |
| AS-16 | Yêu cầu tối đa 31 ngày; vé tháng ngoài phạm vi | Scope §2 |
| AS-17 | Chỗ ghi `Supabase Auth/Realtime` trong backlog cũ đã lỗi thời: ADR-0004/0005/0006 (RDS, JWT tự cấp, Redis pub/sub) mới hơn và đúng | Mâu thuẫn giữa backlog cũ và ADR |
| AS-18 | *(v7)* OTP do dịch vụ OTP quản lý (Redis, TTL); DB chỉ nhận thời điểm xác nhận. Nếu pháp lý cần mã đã băm, phải có ADR | BR-25, D-38 |
| AS-19 | *(v7)* ETA lấy từ port `TravelTimeProvider`: mock ở dev/CI/demo, adapter thật (Goong / VietMap / Google) sau cờ; đã tính kẹt xe | BR-27, D-39 |
| AS-20 | *(v7)* Đăng ký BQL nhập một lần lúc triển khai bằng file; biển số gửi vào DB dạng HMAC, cùng khóa với `vehicle.plate_hash` | BR-26, FR-38, D-41 |
| AS-21 | *(v7)* Thời gian GPS 15 phút chỉ khi có yêu cầu đang chờ; tọa độ không ghi ở đâu, kể cả log và trace | BR-27; tọa độ không vào log hay trace |

## 2. Yêu cầu phi chức năng

| Yêu cầu | Nguồn | Nằm ở đâu |
|---------|-------|-----------|
| Tách theo khu và hộ; BQL chỉ thấy khu mình; vận hành chuỗi chỉ thấy số tổng hợp | PRD §9, ADR-0005 | RLS trên các bảng; `app.kpi_daily_v` chỉ cho vận hành chuỗi và nhân viên khu đó |
| Biển số mã hóa khi lưu; chỉ BQL khu thấy bản gốc; mọi lượt xem ghi log | PRD §9, Scope §3, AC-12 | `plate_ciphertext` thu quyền theo cột; MVP chỉ hiện bản ẩn (chưa có `reveal_*`, `plate_access_log`) |
| Bằng chứng hai bên xác nhận, chỉ ghi thêm (FR-09 viết lại ở v4; v5 thêm bằng chứng tranh chấp) | PRD §9, ADR-0011 | `consent_record`, `dispute_evidence` + trigger `reject_mutation()` + quyền chỉ INSERT / SELECT |
| Quyết định AI kiểm toán được | ADR-0011 | `ai_decision_log` (chỉ hash, chỉ ghi thêm) + trace OTel |
| Không chồng khung / booking trên một ô | ADR-0005 | `EXCLUDE USING gist` |
| Bước workflow và job idempotent | ADR-0005, 0010, 0011 | UNIQUE `idempotency_key` trên mọi bảng đích |
| Thêm khu / tòa / pool chỉ bằng dữ liệu | PRD §2, §9 | Mọi cấp và quy tắc là dòng dữ liệu |
| Hạn lưu, mục tiêu hiệu năng, độ sẵn sàng | PRD §9 ghi **TBD** | Giả định ở §1 |

## 3. Truy vết (yêu cầu → schema)

| Yêu cầu | Bảng / cột / đối tượng |
|---------|------------------------|
| FR-23 một tài khoản, nhiều tư cách | `app_user`, `eligibility (user_id, asset_id, role, valid_during, status, verified_by)`, `asset` |
| FR-24 / BR-15 cấp tại vị trí ô | `app.eligibility_level_at()`, `asset.building_id/zone_id`, `booking.eligibility_level` |
| FR-25 / BR-16 hết hạn chặn giao dịch mới | `eligibility.valid_during` kiểm lúc dùng; `booking_validate`; `parking_request(outcome='blocked', block_reason='BR-16')` |
| FR-26 phạm vi mở từng pool | `slot_pool.max_open_scope` + CHECK theo loại, `share_window.open_scope` + `share_window_validate` |
| FR-27 gợi ý khu khác | `share_window_match_idx`; cung mở đọc được toàn chuỗi (RLS `open_read`) |
| FR-01…04 định tuyến, chặn | `parking_request`, `booking_validate` (BR-01/04/11), `share_window_validate` (BR-03), `slot.slot_type` |
| BR-05 khách miễn phí chỉ ở tòa mình | Rule engine; DB không mô hình "khách của cư dân" (06 R-14) |
| FR-06 dự phòng | `zone_policy.buffer_before/after`, `share_window.bookable_period` |
| FR-07 / BR-11 ghép theo giờ, kích thước, phạm vi | enum `app.size_class`, `slot.size_class`, `vehicle.size_class`, EXCLUDE trên `booking` |
| FR-08 / AC-07 hai bên xác nhận | `agreement` (ghim `zone_policy_id`), `agreement.*_confirmed_at`, CHECK trạng thái `effective`; OTP chỉ là thời điểm (v7) |
| FR-09 bằng chứng xác nhận | `consent_record` (`action = 'agreement_confirm'`, `evidence.body_sha256`), `reject_mutation()` |
| FR-09a / BR-12 / AC-15 duyệt vượt ngưỡng | `zone_policy.approval_threshold_vnd`, `agreement.requires_approval/approval_request_id`, `approval_request` |
| FR-10 / FR-31 / BR-07 / BR-24 chủ về sớm (v6) | `recovery_case` (`new_return_at` = ETA, `eta_source`, `renter_decision`, `owner_buffer_slot_id`), `relocated_from_booking_id`, `consent_record` (`accept_relocation`, `location_share`), `building.intake_paused_at` (D-36) |
| FR-28 / BR-21 hàng chờ | `parking_request.queue_status`, `queued_at`, `last_eta_minutes/at`, `eta_source`; `zone_policy.eta_assign_max` (D-34, D-39) |
| FR-29 / BR-20 chỗ trống, tin 30 phút | `share_window.owner_otp_confirmed_at`, `owner_exited_at`, `expires_at`, `status = 'expired'`; `share_window_listing_expiry_idx`; `zone_policy.listing_expiry` |
| FR-30 Agent đề xuất ghép, rule chốt | `ai_decision_log`, `parking_request.queue_status = 'eligible'`; quyết định gán do rule engine (BR-14) |
| FR-31 ETA người thuê (GPS 15') · ETA chủ 1 lần | `parking_request.gps_consent_id` (`location_share`), `gps_missed_streak`, `zone_policy.gps_interval`; `recovery_case.eta_source` |
| FR-32 quá giờ báo bảo vệ | `booking.checked_in_at` trống sau `hold_expires_at`; `notification` (kênh bảo vệ) |
| FR-33 duyệt 2 lớp (BR-26) | `approval_request.rule_result`, `ai_risk`, `reasons`, `escalated_at`, `bql_deadline_at`, `bql_decision`; `zone_policy.bql_review_ttl` |
| FR-34 dòng thời gian tranh chấp có nguồn | `dispute_evidence` (`source`, `snapshot`, `created_at`), `dispute_case` |
| FR-35 OTP nhận chỗ, giữ theo ETA (BR-22, BR-25) | `booking.assigned_at`, `renter_otp_confirmed_at`, `hold_expires_at`, `no_show_fee_vnd`; `zone_policy.otp_confirm_ttl`, `hold_after_eta`, `hold_max`, `no_show_fee_rate`, `no_show_min_hours`; `consent_record` (`renter_assignment_otp`) |
| FR-36 ưu tiên TH3, báo BQL/bảo vệ (BR-28) | `parking_request.is_urban_related`, `app.th3_free_slots()`, `zone_policy.th3_hold_max`, `th3_guest_alert_slots` |
| FR-37 báo số chỗ còn lại (BR-29) | tính khi cần từ hàng chờ và `app.th3_free_slots()`; không lưu số đếm |
| FR-38 đăng ký tự đối chiếu BQL (BR-26) | `bql_registry_import` (`match_status`, `matched_user_id`, `plate_hash`), RLS zone staff |
| FR-16a / BR-13 / AC-10a chống trùng LPR, kiểm OCR | `lpr_event UNIQUE (zone_id, source_code, source_event_id)`, `zone_policy.ocr_review_threshold`, `status='pending_review'` |
| FR-19 adapter LPR | `lpr_event.source_code` (bảng `lpr_source` hoãn) |
| FR-21 phí · BR-23 hủy và hoàn | `zone_policy.prices` (jsonb), `payment` sổ khoản (`recorded` / `cancelled`, `cancel_refund`, D-37) |
| FR-11 nhắc quá giờ (N2) | `zone_policy.overstay_pre_reminder`, `booking_active_end_idx`, `notification.idempotency_key` (`overstay_pre:` / `overstay_due:<booking_id>`) |
| FR-12 / BR-08 phí quá giờ | `zone_policy.overstay_grace/overstay_fee_per_hour_vnd/overstay_billing_step`, `payment.kind = 'overstay_fee'`, trigger `payment_overstay_guard`, `payment_recorded_uq`; miễn phí qua `dispute_case.resolution_code = 'fee_waived'` |
| FR-13…16 / BR-18 / AC-12 tranh chấp, bằng chứng | `dispute_case` (khu của ô, FK ghép, RLS theo khu), `dispute_evidence` (chỉ ghi thêm, `object_key_masked`, `snapshot`), `approval_request.kind = 'dispute_decision'`, `ai_decision_log` |
| BR-14 LLM không quyết định | Quyết định trong `approval_request` do nhân viên; không cột quyết định nào ghi từ đầu ra LLM; `dispute_case.ai_summary` và bằng chứng `ai_vision_extraction` chỉ là gợi ý, ảnh gửi mô hình là ảnh đã làm mờ |
| BR-17 dữ liệu liên khu tối thiểu | RLS trên `asset` / `eligibility`; `eligibility_level_at` chỉ trả cấp + hạn |
| BR-19 giá theo cấp | `zone_policy.prices` `{slot_type: {level: {hour, day}}}` |
| A-03 đồng ý | `consent_record` (`registration_terms`, `plate_processing`; `withdrawn` giữ lịch sử) |
| Lượt đỗ hiện tại (N1, M5) | `booking.checked_in_at/checked_out_at` từ `lpr_event` khớp |
| Ô không đặt được | `slot.operational_status`, `booking_validate` từ chối |
| M14 hội thoại, HITL resume | `agent_thread`, `approval_request.thread_id`, `pending_card` |
| Kiểm toán AI | `ai_decision_log` (chỉ hash, chỉ ghi thêm, RLS theo khu) |
| KPI (Scope §6) | view `app.kpi_daily_v` (kể cả `overstay_fees`, `disputes_opened`, `dispute_prep_minutes_avg`) |
| ADR-0006 xác thực (một phần thay bởi 0011) | `app_user.password_hash` (argon2id), `app_user.staff_zone_id`; access JWT 8 giờ; OTP trong Redis |
| W7 RAG | `knowledge_chunk` + `embedding` |
| **Hoãn** | Voucher (FR-22, AC-16), dự báo (FR-05, FR-20), `overstay_case`, hoán đổi (FR-17/18, D-10), xem biển số gốc có log (AC-12), quyền chủ thể dữ liệu (D-14, D-15), hạn lưu (D-05, D-06, D-12) → [08](08-deferred-tables.md) |
