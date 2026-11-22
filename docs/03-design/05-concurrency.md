# 05 — Đồng thời và toàn vẹn theo từng luồng nhạy cảm

> File này nêu quy tắc cho từng luồng. SQL đầy đủ của v4 (trước quá giờ và tranh chấp): `git show feff7b5:docs/03-design/05-concurrency.md`.

## 0. Quy tắc chung (mọi luồng)

| Quy tắc | Chi tiết |
|---------|----------|
| Mức cô lập | **READ COMMITTED** ở mọi nơi; mỗi bất biến là một ràng buộc, khóa dòng hoặc UPDATE có điều kiện, nên không cần SERIALIZABLE. |
| Một đơn vị công việc | `platform.db.unit_of_work(ctx)` chạy `SET LOCAL app.user_id / app.role / app.zone_ids` (ADR-0005). Một khu mỗi transaction. |
| Không gọi ngoài trong transaction | LLM, S3, enqueue arq, đẩy realtime, gọi `TravelTimeProvider`: không bao giờ ở trong. Mẫu *tx đọc → gọi ngoài → tx ghi kèm khóa idempotent*. Ghi `notification` trong transaction, đẩy **sau commit**. |
| Timeout | `statement_timeout = 5s`, `lock_timeout = 2s`, `idle_in_transaction_session_timeout = 30s` cho `parksmart_app`; job có thể tăng `statement_timeout` cục bộ. |
| Idempotent | Mọi lần ghi của workflow / job mang `idempotency_key = thread_id:step` (hoặc `source:event_id`); `23505` trên khóa này → trả dòng đã có. |
| Trọng tài | Luồng tranh chấp giữa hai người dùng (OTP, hết hạn, BQL) do **UPDATE có điều kiện trên trạng thái**: đúng một lệnh thắng, lệnh kia thấy 0 dòng. |
| Thứ tự khóa | PK tăng dần trong một bảng; giữa các bảng `share_window` → `parking_request` → `booking` → `slot_holding` → `recovery_case`. |
| Thử lại | Cả transaction, tối đa 3 lần, có jitter, khi gặp `40P01`, `55P03`, `40001`. Không thử lại `23P01` / `23505` / `23514` (đó là câu trả lời nghiệp vụ). |

### 0.1 Kiểm kê idempotent (v7)

| Bảng ghi | Chống chạy lại |
|----------|----------------|
| `parking_request`, `booking`, `payment`, `notification`, `share_window`, `recovery_case`, `ai_decision_log`, `dispute_case` | UNIQUE `idempotency_key` trên chính bảng. Khóa `ai_decision_log` = `thread_id:checkpoint_id:node` |
| `agreement` | UNIQUE `booking_id` |
| `approval_request` | UNIQUE một phần `(kind, subject_id) WHERE status = 'pending'` + UPDATE quyết định có điều kiện |
| `consent_record` | UNIQUE tự nhiên `(user_id, action, subject_id, terms_version, decision)`; chạy lại → `ON CONFLICT DO NOTHING` |
| `recovery_case` | UNIQUE một phần `recovery_case_open_uq (booking_id)` khi đang mở |
| `bql_registry_import` | UNIQUE `(batch_id, line_no)`: nhập lại cùng batch không thêm dòng |
| `lpr_event` | UNIQUE `(zone_id, source_code, source_event_id)` + `ON CONFLICT DO NOTHING` |
| `slot_holding` | EXCLUDE chồng lấn |
| `dispute_evidence` | UNIQUE một phần theo `(case_id, lpr_event_id / consent_record_id / agreement_id / sha256)` |

OTP (mã, TTL, bộ đếm lần thử) nằm trong dịch vụ OTP / Redis; DB chỉ nhận thời điểm xác nhận (BR-25).

## 1. Giữ chỗ, OTP nhận chỗ, hết hạn (W1 → M5, BR-22)

**Rủi ro:** hai người giữ cùng ô; OTP đến đúng lúc giữ hết hạn; một lần chạy lại trừ tiền hai lần.
**Cách làm:**
* **Gán:** trong một transaction, chọn ô (`FOR UPDATE SKIP LOCKED` trên `parking_request` đủ điều kiện, theo `queued_at`), insert `booking` `status = 'held'`, `assigned_at = now()`, `hold_expires_at = now() + otp_confirm_ttl` (3'). `booking_no_overlap` (EXCLUDE) là trọng tài: người thứ hai nhận `23P01` → ứng viên kế trong transaction mới. Đã đo: 8 phiên → 1 booking, 7 × `23P01`.
* **OTP nhận chỗ:** `UPDATE booking SET renter_otp_confirmed_at = now(), hold_expires_at = <ETA + hold_after_eta, tối đa hold_max / th3_hold_max>` `WHERE id = $1 AND status = 'held' AND renter_otp_confirmed_at IS NULL AND hold_expires_at > now()`. 0 dòng = OTP trễ (quá 3'), không trừ tiền. Thành công → cùng transaction: `payment` `share_booking` (`recorded`), `consent_record` `renter_assignment_otp`, `parking_request` → `holding`.
* **Hết hạn:** job `UPDATE booking … WHERE status = 'held' AND renter_otp_confirmed_at IS NULL AND hold_expires_at < now()` (chưa OTP) hoặc `… AND checked_in_at IS NULL` (đã OTP, xe chưa vào, camera không thấy). Hai trường hợp cùng lúc với OTP: lệnh nào commit trước thắng, lệnh kia 0 dòng.
* **Phí không tới (đã OTP):** cùng transaction với `expired`: `no_show_fee_vnd = max(no_show_fee_rate × price, no_show_min_hours × giá 1 giờ)`, `INSERT payment cancel_refund` với số tiền `price − phí`, khóa `noshow:<booking_id>`. Chưa OTP → không có phí, không có hoàn.
* `booking_validate` tính lại cấp, phạm vi (BR-01/04/16), kích thước (BR-11) và biên khung (FR-06) trong transaction.
* **TH3:** `app.th3_free_slots()` chỉ để báo (BR-28); quyết định thật là EXCLUDE trên ô. Hai yêu cầu cùng đọc "còn 1 chỗ" → một thắng.

## 2. Đăng chỗ, tin 30 phút, chủ về sớm, hàng chờ (M4, W2, W3)

* **Đăng:** insert `share_window` `status = 'open'` chỉ khi có `owner_otp_confirmed_at` (CHECK); EXCLUDE `share_window_no_overlap` trên `(slot_id, period) WHERE status = 'open'`.
* **Xe chủ ra (N1):** `UPDATE share_window SET owner_exited_at = now() WHERE id = $1 AND status = 'open' AND owner_exited_at IS NULL AND expires_at > now()`.
* **Hết tin 30' (BR-20):** job `UPDATE share_window SET status = 'expired' WHERE status = 'open' AND owner_exited_at IS NULL AND expires_at < now()` (dùng `share_window_listing_expiry_idx`). Xe ra đúng lúc hết hạn: lệnh nào commit trước thắng; nếu hết hạn thắng, cổng ra không mở chỗ và app báo chủ đăng lại.
* **Hủy và đặt cùng lúc:** insert booking lấy `FOR SHARE` trên khung; hủy lấy `FOR UPDATE`, **rồi** (câu lệnh mới) kiểm tra booking còn sống; có → từ chối.
* **Chủ về sớm (W3, D-36), một transaction trong khu của ô:** khóa khung, rồi booking đã xác nhận (`FOR UPDATE`); mở hồ sơ (`recovery_case`, khóa `thread_id:w3.case`; hồ sơ thứ hai → `23505` → đọc hồ sơ có sẵn). Người thuê **dời**: lượt thay thế (mỗi ô một `SAVEPOINT`, `23P01` → ô kế), booking cũ `relocated`, khung `closed_early`. Người thuê **ở lại** / quá hạn: booking TH3 `provider_user_id = NULL` cho chủ (EXCLUDE chống hai chủ). Hết ô → `escalated` + `building.intake_paused_at` (khóa lạc quan trên `building`).
* **Hàng chờ (D-34, D-39):** ghép lấy yêu cầu `queued` / `eligible` đầu tiên theo `queued_at` bằng `FOR UPDATE SKIP LOCKED`; hai worker không ghép cùng người. Chốt gán kiểm lại ETA ≤ `eta_assign_max` trong chính transaction đó. `parking_request_one_live_uq` chặn người thuê vào hàng hai lần.

## 3. GPS và ETA người thuê (BR-27, job 15 phút)

* **Phạm vi job:** mỗi `gps_interval` (15') chỉ với yêu cầu `queue_status IN ('queued', 'eligible')`; ngừng khi `assigned` (TH3: tới khi `parked`). Chạy theo lô 500 dòng, mỗi khu một worker (`pg_try_advisory_xact_lock`), gọi `TravelTimeProvider` **ngoài** transaction.
* **Ghi ETA:** `UPDATE parking_request SET last_eta_minutes = $1, last_eta_at = now(), eta_source = 'gps', gps_missed_streak = 0 WHERE id = $2 AND queue_status IN ('queued', 'eligible')`. Kết quả trễ sau khi đã gán không ghi đè (0 dòng).
* **Không có GPS:** `gps_missed_streak + 1`; từ 2 lần liên tiếp → nhắc người thuê, không loại khỏi hàng. ETA cũ quá lâu → coi như xa (BR-27).
* **Không dùng GPS để:** xác nhận chỗ trống, tính tiền, hay chặn `parked` (có thể giả GPS). Các việc đó là cổng ra và OTP.

## 4. Hai bên xác nhận thỏa thuận (M6, AC-07)

**Rủi ro:** hai bên xác nhận cùng lúc và thỏa thuận không bao giờ (hoặc hai lần) có hiệu lực. **Cách làm:** mỗi bên một UPDATE có điều kiện:
đặt `<bên>_confirmed_at = now()` và tính `status` bằng `CASE` (bên kia chưa xác nhận → giữ nguyên; `requires_approval` → `pending_approval`;
còn lại `effective`) `WHERE status = 'pending_confirmation' AND <bên>_confirmed_at IS NULL AND confirm_deadline > now()`. `effective` → insert
`consent_record` (`agreement_confirm`, `evidence.body_sha256`); `pending_approval` → insert `approval_request` (CHECK bắt buộc). OTP thỏa thuận: `INCR` nguyên tử
đếm lần thử, từ chối quá 5 lần, so hash thời gian hằng (nằm ngoài DB).

## 5. BQL quyết định và hạn 10 phút (M12; W2, W3; BR-26)

* **Quyết định:** `UPDATE approval_request SET status = $d, decided_by = $me, decided_at = now(), bql_decision = $d WHERE id = $1 AND status = 'pending' RETURNING thread_id` (RLS giới hạn theo khu của BQL); 0 dòng → `409` kèm trạng thái hiện tại.
* **Hết hạn:** job `UPDATE approval_request SET status = 'expired', bql_decision = 'timed_out' WHERE status = 'pending' AND bql_deadline_at < now()`. BQL bấm đúng lúc hạn: cùng điều kiện `status = 'pending'`, một lệnh thắng. Người thuê nhận thông báo và gợi ý bãi khác.
* **Resume workflow:** job chạy **sau commit**; mọi lần ghi sau resume dùng khóa `thread_id:step`, nên resume hai lần vô hại.

## 6. Bằng chứng đồng ý và hồ sơ

* `consent_record`: trigger mức câu lệnh `reject_mutation()` chặn UPDATE / DELETE / TRUNCATE (kể cả owner); vai trò app chỉ INSERT + SELECT; khóa tự nhiên xếp hàng các insert trùng (`23505` = đã ghi). Hai xác nhận OTP v7 (`owner_listing_otp`, `renter_assignment_otp`) và `location_share` (GPS) cùng kiểu.
* `recovery_case`: `recovery_case_open_uq` cho một trong hai lần chạy W3 đồng thời mở hồ sơ; đổi trạng thái dùng khóa lạc quan.
* `dispute_evidence`: cùng trigger `reject_mutation()`; vai trò app không đọc được `object_key_original`. Hai cư dân báo cùng sự việc: UNIQUE một phần `dispute_case_open_booking_uq` / `_open_slot_uq`; lần báo thứ hai nhận `23505` → đọc hồ sơ có sẵn.

## 7. Nạp LPR (N1) và sổ khoản phí

* **LPR:** `INSERT INTO lpr_event … ON CONFLICT (zone_id, source_code, source_event_id) DO NOTHING RETURNING id`; không có dòng trả về → trùng, không tác dụng phụ (AC-10a). OCR dưới `zone_policy.ocr_review_threshold` → `pending_review`, không kích hoạt gì (BR-13).
* **Sổ khoản:** mỗi khoản là một INSERT `status = 'recorded'` với `idempotency_key`; `payment_recorded_uq` cho tối đa một khoản sống mỗi booking và loại; hủy là `UPDATE … SET status = 'cancelled' WHERE status = 'recorded'`. **Quá giờ (W4):** N2 chạy lại hay hai worker chồng nhau chỉ tạo một thông báo mỗi mốc (`overstay_pre:<booking_id>`, `overstay_due:<booking_id>` → `23505` bỏ qua). Phí ghi lúc ra với khóa `overstay_fee:<booking_id>`.

## 8. Cấu hình, job, bước LLM

* **Cấu hình (M3):** phiên bản `zone_policy` mới = `max(version) + 1`; hai người lưu cùng lúc → `23505` trên `(zone_id, version)` → tải lại. Thỏa thuận ghim id phiên bản nên giá và mẫu đang chạy không đổi. Tham số pilot (30', 15', 10', 40', 60', 3') đổi theo phiên bản mới.
* **Xác thực (ADR-0011):** access JWT 8 giờ, không refresh token. Đăng nhập sai: một `UPDATE … failed_logins + 1, locked_until = CASE …` nguyên tử.
* **Job:** chạy đơn lẻ theo khu bằng `pg_try_advisory_xact_lock`; các job của mục 1, 2, 3, 5 dùng lô 500 dòng và `FOR UPDATE SKIP LOCKED`. MVP không có relay outbox, job xóa theo hạn lưu hay job xóa dữ liệu.
* **Bước LLM:** `tx1 (đọc) → gọi LLM (ngoài transaction, chỉ nhận phút ETA và dữ liệu ẩn danh) → tx2 (ghi, khóa thread_id:step + ai_decision_log)`; chết giữa lần gọi và tx2 thì bước chạy lại và tx2 chỉ insert một lần.
* **Công thức hoãn** (hoán đổi, voucher, xoay refresh token, relay outbox) quay lại cùng bảng của chúng ([08-deferred-tables](08-deferred-tables.md)).
