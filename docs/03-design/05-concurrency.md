# 05 — Đồng thời và toàn vẹn theo từng luồng nhạy cảm

> File này nêu quy tắc cho từng luồng. SQL đầy đủ của từng công thức (v4): `git show feff7b5:docs/03-design/05-concurrency.md`.

## 0. Quy tắc chung (mọi luồng)

| Quy tắc | Chi tiết |
|---------|----------|
| Mức cô lập | **READ COMMITTED** ở mọi nơi; mỗi bất biến là một ràng buộc, khóa dòng hoặc UPDATE có điều kiện, nên không cần SERIALIZABLE. |
| Một đơn vị công việc | `platform.db.unit_of_work(ctx)` chạy `SET LOCAL app.user_id / app.role / app.zone_ids` (ADR-0005). Một khu mỗi transaction. |
| Không gọi ngoài trong transaction | LLM, S3, enqueue arq, đẩy realtime: không bao giờ ở trong. Mẫu *tx đọc → gọi ngoài → tx ghi kèm khóa idempotent*. v4 không có outbox ([ADR-0011](../07-adr/ADR-0011-mvp-simplifications.md)): ghi `notification` trong transaction, đẩy **sau commit** qua `platform.publish()`. |
| Timeout | `statement_timeout = 5s`, `lock_timeout = 2s`, `idle_in_transaction_session_timeout = 30s` cho `parksmart_app`; job có thể tăng `statement_timeout` cục bộ. |
| Idempotent | Mọi lần ghi của workflow / job mang `idempotency_key = thread_id:step` (hoặc `source:event_id`); `23505` trên khóa này → trả dòng đã có. LangGraph chạy lại node `interrupt()` khi resume; arq chạy lại job. |
| Thứ tự khóa | PK tăng dần trong một bảng; giữa các bảng `share_window` → `booking` → `slot_holding` → `recovery_case`; insert chỉ ghi thêm để cuối. |
| Thử lại | Cả transaction, tối đa 3 lần, có jitter, khi gặp `40P01`, `55P03`, `40001`. Không thử lại `23P01` / `23505` / `23514` (đó là câu trả lời nghiệp vụ). |
| Khóa lạc quan | `UPDATE … SET version = version + 1 WHERE id = $1 AND version = $2`; 0 dòng → `409`. |

### 0.1 Kiểm kê idempotent (v4)

| Bảng ghi | Chống chạy lại |
|----------|----------------|
| `parking_request`, `booking`, `payment`, `notification`, `share_window`, `recovery_case`, `ai_decision_log` | UNIQUE `idempotency_key` trên chính bảng (không có bảng `idempotency_keys` chung). Khóa của `ai_decision_log` = `thread_id:checkpoint_id:node` |
| `agreement` | UNIQUE `booking_id` |
| `approval_request` | UNIQUE một phần `(kind, subject_id) WHERE status = 'pending'` + UPDATE quyết định có điều kiện |
| `consent_record` | UNIQUE tự nhiên `(user_id, action, subject_id, terms_version, decision)`; chạy lại → `ON CONFLICT DO NOTHING` |
| `recovery_case` | UNIQUE một phần `recovery_case_open_uq (booking_id)` khi đang mở: một hồ sơ mở mỗi booking |
| `agent_thread` | PK `thread_id` + `INSERT … ON CONFLICT (thread_id) DO UPDATE` |
| `lpr_event` | UNIQUE `(zone_id, source_code, source_event_id)` + `ON CONFLICT DO NOTHING` |
| `slot_holding` | EXCLUDE chồng lấn |

OTP thỏa thuận (hash, TTL, bộ đếm lần thử) nằm trong Redis. Không bảng ghi nào trong 23 bảng thiếu cơ chế chống chạy lại.

## 1. Giữ chỗ / tạo booking (W1 → M5)

**Rủi ro:** hai người (hoặc một lần chạy lại) giữ cùng ô và giờ. **Cách làm:** trong một transaction, hết hạn các giữ chỗ cũ của ô
(`UPDATE booking SET status = 'expired' WHERE slot_id = $s AND status = 'held' AND hold_expires_at < now()`), insert giữ chỗ kèm
`idempotency_key`, insert `notification`. `booking_no_overlap` (EXCLUDE trên `(slot_id, period)`) là trọng tài: người thứ hai chờ rồi lỗi
`23P01` → thử ứng viên kế (Q2) trong transaction mới. Đã đo: 8 phiên → 1 booking, 7 × `23P01`. `booking_validate` tính lại cấp, phạm vi
(BR-01/04/16), kích thước (BR-11) và biên khung (FR-06) ngay trong transaction.

## 2. Đăng / hủy khung chia sẻ, chủ về sớm (M4, W3)

* **Đăng:** EXCLUDE `share_window_no_overlap` trên `(slot_id, period) WHERE status = 'open'`.
* **Hủy và đặt cùng lúc:** insert booking lấy `FOR SHARE` trên khung; hủy lấy `FOR UPDATE`, **rồi** (câu lệnh mới, snapshot mới) kiểm tra
  booking còn sống; có → từ chối, không → `status = 'cancelled'`. Không gộp phần kiểm tra vào `WHERE NOT EXISTS` của UPDATE.
* **Chủ về sớm (W3), một transaction trong khu của ô:** khóa khung, rồi booking đã xác nhận (`FOR UPDATE`); mở hồ sơ (`recovery_case`, khóa
  `thread_id:w3.case`; hồ sơ mở thứ hai → `23505` → đọc hồ sơ có sẵn); thử ô TH3 cùng khu, mỗi ô một `SAVEPOINT` (`23P01` → ô kế); khi người thuê
  chấp nhận (`consent_record`, `accept_relocation`): booking cũ `relocated`, khung `closed_early`; thanh toán `early_return_refund` (thời gian
  chưa dùng) và `relocation_th3` (giá TH3), mỗi khoản một khóa, chủ chỗ không trả gì (D-09); hồ sơ `resolved` kèm `relocated_booking_id`
  (khóa lạc quan). Hết TH3 → không commit gì, chuyển BQL (`approval_request` loại `early_return_escalation`).

## 3. Hai bên xác nhận thỏa thuận (M6, AC-07)

**Rủi ro:** hai bên xác nhận cùng lúc và thỏa thuận không bao giờ (hoặc hai lần) có hiệu lực. **Cách làm:** mỗi bên một UPDATE có điều kiện:
đặt `<bên>_confirmed_at = now()` và tính `status` bằng `CASE` (bên kia chưa xác nhận → giữ nguyên; `requires_approval` → `pending_approval`;
còn lại `effective`) `WHERE status = 'pending_confirmation' AND <bên>_confirmed_at IS NULL AND confirm_deadline > now()`. Khóa dòng xếp hàng
hai bên. `effective` → insert `consent_record` (`agreement_confirm`, `evidence.body_sha256`) và xác nhận booking; `pending_approval` → insert
`approval_request` và đặt `approval_request_id` (CHECK bắt buộc). **OTP trong Redis:** `INCR` nguyên tử khóa đếm lần thử (cùng TTL), từ chối
quá 5 lần, so hash thời gian hằng, xóa khi khớp.

## 4. BQL quyết định HITL (M12; W2, W3)

`UPDATE approval_request SET status = $d, decided_by = $me, decided_at = now() WHERE id = $1 AND status = 'pending' RETURNING thread_id`
(RLS giới hạn theo khu của BQL); 0 dòng → `409` kèm trạng thái hiện tại. `notification` cùng transaction. Job resume enqueue **sau commit**;
mọi lần ghi sau resume dùng khóa `thread_id:step`, nên resume hai lần vô hại.

## 5. Bằng chứng đồng ý và hồ sơ chủ về sớm

* `consent_record`: trigger mức câu lệnh `reject_mutation()` chặn UPDATE / DELETE / TRUNCATE (kể cả owner); vai trò app chỉ INSERT + SELECT;
  khóa tự nhiên xếp hàng các insert trùng (`23505` = đã ghi). Hai bên ghi `user_id` khác nhau nên không tranh nhau.
* `recovery_case`: `recovery_case_open_uq` cho một trong hai lần chạy W3 đồng thời mở hồ sơ; đổi trạng thái dùng khóa lạc quan.
* Sổ cái chuỗi hash (v1–v3, khóa dòng head của khu sau cùng) đã hoãn; làm lại nếu nó quay về ([08-deferred-tables](08-deferred-tables.md)).

## 6. Nạp LPR (N1, Ưu tiên 1)

`INSERT INTO lpr_event … ON CONFLICT (zone_id, source_code, source_event_id) DO NOTHING RETURNING id`; không có dòng trả về → trùng, không
tác dụng phụ (AC-10a). OCR dưới `zone_policy.ocr_review_threshold` → `pending_review`, không kích hoạt gì (BR-13). Một worker mỗi nguồn:
`pg_try_advisory_xact_lock(hashtextextended('n1:' || zone_id || ':' || source_code, 0))`.

## 7. Thanh toán (VietQR mock, Ưu tiên 2)

`UPDATE payment SET status = 'paid_simulated', paid_at = now() WHERE id = $1 AND status = 'pending'`; `payment_paid_uq` chặn hai lần thanh
toán thành công cùng loại cho một booking; `idempotency_key` hấp thụ việc bấm "Thanh toán" hai lần.

## 8. Xác thực, cấu hình, job, bước LLM

* **Xác thực (ADR-0011):** access JWT 8 giờ, không refresh token, không thu hồi. Đăng nhập sai: một `UPDATE … failed_logins + 1, locked_until = CASE …` nguyên tử.
* **Cấu hình (M3):** phiên bản `zone_policy` mới = `max(version) + 1`; hai người lưu cùng lúc → `23505` trên `(zone_id, version)` → tải lại.
  Thỏa thuận ghim id phiên bản nên thỏa thuận đang chạy giữ nguyên giá và mẫu.
* **Job:** chạy đơn lẻ theo khu bằng `pg_try_advisory_xact_lock`; dọn giữ chỗ hết hạn theo lô 500 dòng (`FOR UPDATE SKIP LOCKED`).
  MVP không có relay outbox, job xóa theo hạn lưu hay job xóa dữ liệu.
* **Bước LLM:** `tx1 (đọc) → gọi LLM (ngoài transaction, đã ẩn danh) → tx2 (ghi, khóa thread_id:step + ai_decision_log)`; chết giữa lần gọi
  và tx2 thì bước chạy lại và tx2 chỉ insert một lần.
* **Công thức hoãn** (chân hoán đổi, quá giờ, dùng voucher, bằng chứng tranh chấp, xoay refresh token, relay outbox với
  `FOR UPDATE SKIP LOCKED`) quay lại cùng bảng của chúng ([08-deferred-tables](08-deferred-tables.md)).
