# 06 — Tình huống biên và rủi ro

Cột "Xử lý / chặn bởi" ghi đối tượng làm chính database từ chối trạng thái sai; phép kiểm tương ứng trong
[sql/seed-and-tests.sql](sql/seed-and-tests.sql) được ghi là **T:** nếu có.

## 1. Tình huống biên riêng của ParkSmart

| # | Tình huống | Hậu quả nếu bỏ qua | Xử lý / chặn bởi |
|---|------------|--------------------|------------------|
| E-01 | **Hạn hiệu lực NULL** của tư cách (chủ sở hữu không hết hạn) | `upper(valid_during) < now()` ra NULL → chủ sở hữu bị loại hoặc nhận nhầm | Khoảng không có cận trên = không hết hạn; kiểm tra bằng `valid_during @> now()` (an toàn với NULL). Index hết hạn loại `upper_inf`. T: "L4 guest has no expiry" |
| E-02 | Khoảng thời gian rỗng / ngược / vô hạn | Booking dài 0, `[x, -∞)`, giữ chỗ không bao giờ hết | CHECK `app.is_finite_range()` trên mọi khoảng của booking / khung / yêu cầu. T: "empty / inverted booking period" |
| E-03 | Chuỗi trắng (`'   '`) cho tên, mã, lý do | Bản ghi vô dụng, "lý do" giả cho quyết định | CHECK `btrim(x) <> ''` (cả `agreement_template_md`, `level_code`). T: "blank name" |
| E-04 | Email tùy chọn | Hai email NULL va nhau hoặc lưu chuỗi rỗng | Unique một phần `WHERE email IS NOT NULL`; app lưu NULL, không lưu `''` |
| E-05 | Trùng số điện thoại khi đăng ký lại sau khi xóa | User đã xóa chặn số mãi mãi | Unique một phần `WHERE deleted_at IS NULL`. T: "duplicate live phone number" |
| E-06 | Một biển số trên hai tài khoản gia đình | Unique chặn gia đình hoặc cho mạo danh | Unique theo `(user_id, plate_hash)`; LPR khớp nhiều xe → coi là mơ hồ → hàng chờ kiểm tra (D-13) |
| E-07 | Định dạng biển số: `30A-123.45`, `30a12345`, dấu cách, gạch Unicode | Cùng xe ra hash khác → LPR không khớp | App chuẩn hóa trước HMAC: NFKC, chữ hoa, chỉ giữ `[A-Z0-9]`. Một hàm có unit test, dùng chung cho đăng ký và N1 |
| E-08 | Tên tiếng Việt, sắp xếp và tìm kiếm (`Đ`, dấu) | Sai thứ tự, tìm `do` không ra `Đỗ` | Lưu nguyên (UTF8). Sắp xếp bằng `COLLATE "vi-VN-x-icu"`; tìm mờ sau này bằng `unaccent` + `pg_trgm` |
| E-09 | Múi giờ: DB UTC, người dùng UTC+7, "hết hạn ngày D", đối soát ngày | Lệch 7 giờ; chia ngày sai | Mọi cột `timestamptz`; `zone.timezone` quyết định ngày địa phương; "hết ngày D" = `(D + 1) 00:00` theo múi giờ khu. Việt Nam không có giờ mùa hè |
| E-10 | Khoảng nửa mở: đặt 08:00–12:00 rồi 12:00–14:00 | Từ chối hai lượt liền nhau, hoặc nhận chồng thật | `tstzrange` mặc định `[)`; `&&` coi hai khoảng kề nhau là không chồng |
| E-11 | Làm tròn tiền: giá giờ × 1 giờ 20 phút | Lẻ đồng; tổng không khớp | Mọi số tiền là `bigint` VND. Rule engine làm tròn một lần mỗi dòng và lưu kết quả; DB không tính tiền từ số thực. Giá trong `zone_policy.prices` là số nguyên |
| E-12 | Tràn số nguyên | `ref_no`, bộ đếm tràn | id / sequence `bigint`; `smallint` chỉ cho bộ đếm có CHECK (lần thử ≤ 10, giờ 0–23) |
| E-13 | Danh sách rỗng: khu hết TH3, user không có tư cách | Gom ra NULL, crash | `eligibility_level_at` luôn trả một dòng (mặc định L4); ghép ra 0 dòng → lưu kết quả `no_match` (đếm trong `kpi_daily_v`) |
| E-14 | Xe lớn hơn mọi ô của khu | Không bao giờ ghép được | Rule engine trả `no_match`, W1 gợi ý khu khác (FR-27); DB vẫn từ chối booking sai kích thước (BR-11). T: "BR-11 XL pickup" |
| E-15 | Tư cách hết hạn giữa lượt đỗ | Người thuê bị đuổi giữa chừng, hoặc vẫn đặt mới được | Kiểm tra cấp lúc đặt. Lượt đang chạy kéo dài tối đa `zone_policy.eligibility_grace_max` (mặc định 7 ngày, D-04), không quá giờ kết thúc. T: "BR-16 expired tenant claims L1" |
| E-16 | Chủ về sớm mà TH3 đã đầy | Người thuê không có chỗ | Transaction không commit gì; W3 chuyển BQL (`early_return_escalation`) |
| E-17 | Giữ chỗ hết hạn nhưng job dọn chưa chạy | Ô trông như đã đặt; người tìm bị từ chối | Transaction đặt chỗ hết hạn giữ chỗ cũ của ô trước (05 §1); job dọn mỗi phút |
| E-18 | Quá hạn xác nhận khi mới có một bên | Booking chặn ô mãi | UPDATE xác nhận yêu cầu `confirm_deadline > now()`; job dọn cho thỏa thuận + booking hết hạn (`agreement_deadline_idx`) |
| E-19 | Xóa dây chuyền ngoài ý muốn | Xóa khu / user làm mất booking, bằng chứng | `ON DELETE RESTRICT` trên mọi FK nghiệp vụ; CASCADE chỉ cho dữ liệu phụ (02-erd §4). T: "deleting a user with history", "deleting a zone" |
| E-20 | Mồ côi: `consent_record.subject_id`, `approval_request.subject_id` đa hình | Tham chiếu treo | Ghi cùng transaction với đối tượng; CHECK `consent_record.subject_type` chỉ cho `app_user`, `agreement`, `recovery_case`, `share_window`, `booking`, `parking_request`. FK ngược ở chỗ cần (`agreement.approval_request_id`) |
| E-21 | Gửi lại: bấm hai lần, LangGraph chạy lại sau `interrupt()`, arq retry, nhà cung cấp gửi lại | Hai giữ chỗ, hai xác nhận, hai thanh toán, LPR trùng, ghi quyết định hai lần | UNIQUE `idempotency_key` trên booking, request, payment, notification, share_window, recovery_case, ai_decision_log; khóa tự nhiên trên `consent_record`; UNIQUE + ON CONFLICT cho LPR. T: "replayed booking idempotency key", "LPR duplicate" |
| E-22 | Dữ liệu nhập từ ngoài (danh sách cư dân của từng BQL, A-09) | Nhập sai vượt qua quy tắc app | Nạp vào `bql_registry_import` (mặc định `needs_bql`); chỉ khớp tự động khi duy nhất (FR-38); `asset` / `eligibility` ở `pending`; BQL xác minh. Không dùng `session_replication_role = replica` |
| E-23 | Tham chiếu chéo khu (ô khu A trong booking khu C) | Lộ dữ liệu cho BQL sai khu | FK ghép `(x_id, zone_id)`. T: "booking a zone-A slot under zone C" |
| E-24 | Lệch giờ LPR / sự kiện sai thứ tự / thời điểm tương lai | Thứ tự sự kiện sai | Giữ cả `occurred_at` và `received_at`; ghép cặp vào / ra hoãn cùng `parking_session` |
| E-25 | OCR ở giá trị biên (đúng ngưỡng, > 1, NULL) | Định tuyến sai sang kiểm tra | `ocr_confidence NOT NULL CHECK 0..1`; quy tắc `< ngưỡng → kiểm tra` (bằng ngưỡng thì qua). T: "OCR confidence above 1" |
| E-27 | User đặt chính ô mình chia sẻ | Tự giao dịch, thổi phồng KPI | CHECK `provider_user_id <> renter_user_id` |
| E-28 | Thứ tự khóa / khoảng trắng trong `consent_record.evidence` | Hash tính từ evidence lệch khi kiểm lại | `body_sha256` tính từ nội dung thỏa thuận, không từ jsonb; evidence lưu giá trị dạng chuỗi |
| E-31 | Dòng nắm giữ nhập nhầm (sai chủ) | EXCLUDE chặn ô của chủ thật | `slot_holding.voided_at` + `void_reason` bắt buộc; EXCLUDE bỏ qua dòng void. T: "(a) voided holding frees the slot" |
| E-33 | Chủ về sớm, người thuê ở lại mà hết ô dự phòng | Chủ không có chỗ đỗ | v6 (D-36): `escalated` → BQL; `building.intake_paused_at` chặn lượt thuê mới tới khi có lại ô. Số ô dự phòng tối thiểu: BQL xác nhận (A-12). T: section 11 |
| E-38 | Hai lần chạy W3 mở hồ sơ cho một booking | Hai booking thay thế cho một người thuê | UNIQUE một phần `recovery_case_open_uq`; bên thua đọc hồ sơ có sẵn. T: một hồ sơ mở mỗi booking |
| E-39 | Hồ sơ `resolved` / `escalated` mà thiếu kết quả | Báo xong nhưng người thuê không có chỗ / BQL không có yêu cầu | CHECK `recovery_case_resolved_has_booking`, `recovery_case_escalated_has_approval` |
| E-40 | Nhân viên không có khu, hoặc cư dân có khu nhân viên | BQL không thấy gì, hoặc cư dân có quyền khu qua claim JWT | CHECK `app_user_staff_zone_role`; claim `zone_ids` chỉ dựng từ cột đó. `zone_manager` thiếu khu thì không thấy gì (mặc định an toàn) |
| E-41 | Đặt ô đang bảo trì hoặc bị khóa | Người thuê đến ô không dùng được | `booking_validate` từ chối `slot.operational_status <> 'active'` |
| E-42 | `checked_out_at` trước `checked_in_at`, hoặc ra mà chưa vào | Sai số liệu chiếm chỗ | CHECK `booking_check_times`; N1 đặt cả hai từ `lpr_event` khớp |
| E-43 | Node chạy lại sau `interrupt()` ghi quyết định AI lần nữa | Dòng kiểm toán trùng | UNIQUE `ai_decision_log.idempotency_key` = `thread_id:checkpoint_id:node` |
| E-44 | Ghi prompt, đầu ra hay user id gốc vào nhật ký AI "để debug" | Lộ dữ liệu cá nhân vào bảng không xóa được | Bảng chỉ có cột hash (CHECK độ dài 32), không có cột văn bản; debug đi qua OTel có lọc PII (ADR-0008) |
| E-45 | User đọc `agent_thread` của người khác | Lộ thẻ đã ẩn danh và trạng thái workflow | RLS policy `owner`; BQL chỉ đọc dòng `awaiting_manager` của khu mình |
| E-46 | Hai lần báo cùng sự việc (cùng người báo, booking hoặc ô, loại) khi hồ sơ còn mở | Hai hồ sơ cho BQL xử lý | UNIQUE một phần `dispute_case_open_booking_uq` / `dispute_case_open_slot_uq`; lần hai đọc hồ sơ có sẵn. T: "duplicate open report" |
| E-47 | N2 chạy lại hoặc hai worker chồng nhau | Người thuê nhận nhắc quá giờ nhiều lần | UNIQUE `notification.idempotency_key` = `overstay_pre:<booking_id>` / `overstay_due:<booking_id>`; chỉ hai thông báo mỗi booking, không nhắc thêm. T: "duplicate reminder key" |
| E-48 | Ghi phí quá giờ khi xe chưa ra (`checked_out_at` NULL), hoặc ghi hai lần | Tính phí sai, tính trùng | Trigger `payment_overstay_guard` từ chối; `payment_recorded_uq (booking_id, kind)`; khóa `overstay_fee:<booking_id>`. T: "second recorded overstay_fee" |
| E-49 | Phí quá giờ cho booking TH3 (không có người cho thuê) | Không rõ ai nhận | Quy tắc (D-33): người nhận = `booking.provider_user_id`, hoặc khu khi NULL; không cột người nhận, sổ khoản không thanh toán trong app (A-05) |
| E-50 | Sửa hoặc xóa bằng chứng tranh chấp sau khi nộp | Hồ sơ mất giá trị | `dispute_evidence` chỉ ghi thêm (`reject_mutation()` + vai trò app chỉ INSERT/SELECT). T: "evidence UPDATE" |
| E-51 | Đọc ảnh gốc (có thể chứa biển số) qua API hoặc SQL của vai trò app | Vượt BR-09 / BR-14, lộ biển số | Thu SELECT cột `object_key_original`; chỉ `object_key_masked` được hiện và gửi cho mô hình thị giác; `description` lưu sau khi ẩn biển số. T: "original key not selectable" |
| E-52 | Bằng chứng khác khu hoặc của hồ sơ khác; người bị báo của hồ sơ khác đọc được | Lộ dữ liệu giữa các khu (BR-18) | FK ghép `(case_id, zone_id)`, `(agreement_id, zone_id)`; `lpr_event` / `consent_record` FK thường nên khớp khu là quy tắc ứng dụng + RLS; `parties_read` chỉ hồ sơ của mình. T: "cross-zone FK" |
| E-53 | Cư dân khi báo tự đặt bên bị báo, trường AI hay quyết định, hoặc gắn booking / thread của người khác | Giả mạo hồ sơ | RLS `reporter_insert` (chỉ `open`, không các trường đó; booking mà mình là một bên, thread của mình); W5 / system suy ra bên bị báo. CHECK `dispute_case_resolution_consistent`, `_ready_before_decision` |
| E-54 | OTP nhận chỗ đến đúng lúc giữ hết hạn | Trừ tiền cho chỗ đã bị nhả, hoặc giữ hai lần | UPDATE có điều kiện `renter_otp_confirmed_at IS NULL AND hold_expires_at > now()` và job hết hạn cùng điều kiện; lệnh nào commit trước thắng (05 §1). T: OTP sau 3 phút bị từ chối |
| E-55 | Xe chủ ra đúng lúc tin đăng hết 30 phút | Chỗ được coi là trống dù đã hết hạn | `owner_exited_at` chỉ ghi khi `expires_at > now()`; job đặt `expired` cùng điều kiện (05 §2) |
| E-56 | GPS giả, GPS trễ sau khi đã gán, hoặc người thuê tắt GPS | Gán sai ưu tiên, sai tiền | ETA không dùng để xác nhận chỗ hay tính tiền; ghi ETA chỉ khi còn `queued` / `eligible`; tắt GPS = coi như xa, nhắc sau 2 lần (BR-27) |
| E-57 | BQL không trả lời ca chờ | Ca treo, người thuê chờ mãi | `bql_deadline_at` = `escalated_at + bql_review_ttl` (10'); job đặt `timed_out` (từ chối) và gợi ý bãi khác (05 §5) |
| E-58 | Đăng ký khớp nhiều dòng của BQL (cùng SĐT hoặc cùng biển số, hai ô) | Tự kích hoạt nhầm | Khớp không duy nhất → `needs_bql`, không `auto_matched` (FR-38, `bql_registry_import`) |
| E-59 | Bãi khách còn ≤ 2 chỗ mà khách vãng lai đến | Chiếm chỗ đã giữ cho người ưu tiên | Số chỗ trừ lượt đang giữ (`app.th3_free_slots`); ≤ `th3_guest_alert_slots` → báo BQL và bảo vệ; khách không dùng app bị bảo vệ chặn (BR-28) |
| E-60 | OTP xong nhưng xe không vào | Người thuê đã trả, ô trống | Hết `hold_expires_at` mà `checked_in_at` trống → nhả chỗ, phí 30%, hoàn 70% (BR-22); lệch ETA (`last_eta_at` và giờ camera) vào KPI |

**Hoãn cùng bảng** (xem [08](08-deferred-tables.md)): E-26 voucher · E-29 xóa khi còn booking · E-30 partition LPR · E-32 hoán đổi trước đồng ý · E-34 job xóa theo hạn · E-35 chuỗi hash · E-36 outbox · E-37 refresh token.

## 2. Rủi ro

| # | Rủi ro | Tác động | Giảm thiểu |
|---|--------|----------|------------|
| R-01 | App kết nối mà không đặt ngữ cảnh RLS | Kết quả rỗng (an toàn) hoặc lộ dữ liệu nếu vai trò vượt RLS | Thiếu thiết lập = "không có quyền"; vai trò app `NOBYPASSRLS`, không phải owner; một helper `unit_of_work`; test tích hợp mỗi policy |
| R-02 | Ngữ cảnh `system` rộng (job) | Job của khu A đọc khu B | `system` vẫn bị giới hạn bởi `app.zone_ids`; job chạy theo khu |
| R-03 | Lạm dụng hàm `SECURITY DEFINER` | Leo thang quyền, IDOR | `search_path = pg_catalog, app` cố định; kiểm vai trò / khu bên trong; thu `EXECUTE` từ PUBLIC |
| R-04 | Lộ khóa biển số | Giải mã được biển số | **D-07:** mã hóa ở app (AES-256-GCM, khóa bọc KMS) + khóa HMAC riêng; DB không thấy khóa. Xoay vòng qua `plate_key_version` |
| R-05 | Checkpoint LangGraph (schema `agent`) chứa dữ liệu cá nhân ngoài RLS | Lộ chéo khu qua bảng checkpoint | **D-12:** cô lập schema hai chiều, quy tắc nội dung (chỉ id / mã giả). Job xóa checkpoint 30 ngày hoãn; serializer mã hóa chưa kiểm chứng |
| R-06, R-28 | Không có chuỗi hash: DBA / superuser sửa bằng chứng không bị phát hiện | Mất khẳng định toàn vẹn | `reject_mutation()` (chặn cả owner), quyền chỉ INSERT / SELECT, không dùng superuser trực tiếp ở production, backup. Đưa chuỗi hash lại khi có yêu cầu (D-32) |
| R-07 | `lpr_event` không partition phình mãi | Quét chậm, không xóa rẻ | Ổn cho demo. Trước khi có LPR thật: partition theo tháng + hạn lưu |
| R-09 | Trigger lệch rule engine | Từ chối booking hợp lệ hoặc vượt rule engine | Trigger chỉ giữ bất biến cứng có mã BR; test tham số L1–L4 × phạm vi × loại chạy cả trên DB |
| R-10 | Hai driver Postgres, ba process | Hết kết nối trên `db.t4g.small` | Ngân sách pool mỗi process + PgBouncer transaction mode ([vận hành §4](../06-operations/03-database-monitoring-scaling.md)); `SET LOCAL` hợp với transaction pooling |
| R-11 | Thay đổi enum | `ADD VALUE` không dùng được trong cùng transaction; bỏ giá trị rất khó | Thêm giá trị trong migration riêng; không bao giờ xóa giá trị |
| R-12 | Migration dài khóa bảng nóng | Gián đoạn khi deploy | Expand → migrate → contract, `CONCURRENTLY`, `NOT VALID` + `VALIDATE`, `lock_timeout` ([vận hành §1](../06-operations/01-database-operations.md)) |
| R-13 | RDS một AZ (ADR-0005) | Ngừng vài giờ khi AZ lỗi | Chấp nhận cho demo; Multi-AZ trước khi có dữ liệu thật |
| R-14 | BR-05 (khách cư dân miễn phí) không có dữ liệu riêng | Thỏa thuận khách có thu tiền ngoài nền tảng | Ngoài phạm vi demo ngoài TH3; rule engine chặn giao dịch "khách" có phí |
| R-16 | Giá trị nghiệp vụ là mặc định (ngưỡng, dự phòng, phí) | Hành vi sai khi chạy thật | Mặc định có nghiên cứu, ghi "cần BQL xác nhận" trong [07](07-db-decision-log.md) §1; đổi chỉ là đổi dữ liệu |
| R-17 | Chưa chạy trên PG16 + pgvector | Lỗi không tương thích ở lần deploy đầu | DDL tránh tính năng chỉ có ở PG17; chạy cả hai script trên `pgvector/pgvector:pg16` trong CI trước migration đầu (D-30) |
| R-18, R-19 | Khung pháp lý mới (PDPL 91/2025, Nghị định 356/2025); chuyển dữ liệu ra nước ngoài (Bedrock) | Dẫn sai luật; bị xử phạt | Thiết kế theo D-22; prompt chỉ chứa mã giả; nộp hồ sơ đánh giá tác động trong 60 ngày và DPIA trước dữ liệu thật (D-23) |
| R-20 | Chưa kiểm index ở quy mô thật | Ghép / hàng chờ chậm | Chạy lại truy vấn của [04](04-queries-indexes.md) trên staging trước go-live |
| R-21 | **MVP không thực thi hạn lưu và xóa dữ liệu** | Giữ dữ liệu quá hạn luật; không xử lý được yêu cầu xóa | Demo chỉ dữ liệu giả. Bắt buộc có trước dữ liệu thật ([bảo mật §3](../06-operations/02-database-security.md)) |
| R-22 | **Chỉ hiển thị biển số ẩn** | Màn hình hiện biển số gốc sẽ vượt AC-12 | Phải có `plate_access_log` + hàm xem có ghi log trước |
| R-23 | **`zone_policy.prices` là JSONB, DB không ràng buộc** | Giá sai hoặc âm làm hỏng tính phí | Rule engine (Pydantic) kiểm trước INSERT; `payment.amount_vnd >= 0` là chốt cuối |
| R-26 | **Không refresh token; JWT demo sống 8 giờ, không thu hồi** | Token lộ dùng được đến khi hết hạn | Chỉ chấp nhận cho demo; trước người dùng thật đưa `refresh_token` trở lại |
| R-27 | **Không outbox**: đẩy realtime sau commit | Mất tin realtime nếu process chết giữa chừng | Người dùng vẫn thấy dòng `notification`; client tải lại khi kết nối lại; giữ port `platform.publish()` |
| R-29 | **`ai_decision_log` không có job xóa** | Phình mãi; `user_hash` là dữ liệu cá nhân theo PDPL | Chỉ hash và id; quyết định hạn lưu (mục tiêu 5 năm, D-06) và cách xóa trước dữ liệu thật |
| R-30 | **Ân hạn, giá, bước tính và nhắc quá giờ là số mặc định** (20 / 10 phút, 50 000 đ/giờ, bước 15 phút) | Phí sai so với nội quy thật | Nằm trong `zone_policy.overstay_*` nên đổi bằng dòng nội quy mới; cần BQL xác nhận (D-03). Miễn phí chỉ qua tranh chấp (`fee_waived`, quy tắc ứng dụng) |
| R-31 | **Ảnh làm mờ chuẩn bị tay, chưa có pipeline làm mờ, S3, hạn lưu ảnh** | Ảnh gốc có thể chứa biển số và tồn tại mãi | MVP chỉ lưu khóa object; hạn lưu ảnh và pipeline làm mờ là việc phải quyết định trước dữ liệu thật; mô hình thị giác chỉ nhận ảnh đã làm mờ |
| R-32 | **Chưa có `overstay_case` và `plate_access_log`** | Không báo cáo được quá giờ lặp lại; không xem biển số gốc có ghi log | Chấp nhận (hoãn, [08](08-deferred-tables.md)); AC-12 vẫn đúng vì chỉ hiện biển số ẩn |
| R-33 | GPS và ETA mock sai so với kẹt xe thật | Ngưỡng 30' sai; gán sớm hoặc muộn | Port `TravelTimeProvider`, adapter thật sau cờ; đo độ lệch ETA trong KPI pilot; xem lại sau 2 tuần |
| R-34 | Import đăng ký BQL sai (cột, số điện thoại, biển số) | Người đúng bị BQL duyệt; người sai được kích hoạt | Nhập qua bảng tạm, kiểm trùng và thiếu, BQL ký nhận từng batch; `batch_id` để hoàn tác (D-41) |
| R-35 | OTP SMS không đến kịp 3 phút | Người thuê mất chỗ oan | OTP hết hạn → chưa trừ tiền, người thuê về hàng chờ (BR-22); có nút gửi lại OTP; dịch vụ OTP có giám sát tỷ lệ gửi |
