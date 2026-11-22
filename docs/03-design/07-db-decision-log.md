# 07 — Nhật ký quyết định (để nhóm duyệt)

> **Trạng thái:** đề xuất v6 (MVP, 25 bảng), 2026-11-22 (v5: 2026-11-19) (v4: 2026-11-18). **Chưa có gì được nghiệp vụ duyệt**: mỗi giá trị là mặc định an toàn, dễ đổi.
> Duyệt từ trên xuống (độ tin cậy thấp và khó đảo ngược trước); đa số dòng chỉ cần đổi dữ liệu (`zone_policy`, `prices`), dòng ghi "migration"
> cần một revision Alembic. Nguồn ghi **[read]** là đã mở trang, **[summary]** chỉ có tóm tắt tìm kiếm; chưa thử với người dùng hay BQL thật.

**Độ tin cậy:** cao = repo hoặc văn bản luật gốc · vừa = nguồn thứ cấp đáng tin · thấp = phán đoán, cần thay bằng số thật.
**Đảo ngược:** chỉ dữ liệu · migration · không đảo ngược được trên thực tế.

## 0. Quyết định phạm vi MVP (D-31)

| ID | Câu hỏi | Quyết định | Lý do | Tin cậy | Nếu đổi | Đảo ngược |
|----|---------|------------|-------|---------|---------|-----------|
| D-31 | Schema MVP = 27 bảng (phương án C) | Giữ lõi demo 20 bảng + 7 bảng bảo mật / bền vững. Bỏ 30 bảng: 19 bảng chỉ phục vụ Ưu tiên 3, và các bảng chất lượng dữ liệu / cấu hình / tuân thủ đã gộp vào cột (`subzone`, `basement`, `size_class`, `gate`, `lpr_source`, `consent`, `price_rule`, `agreement_template`, `knowledge_doc`, `chain`, `kpi_daily` thành view) hoặc chỉ ghi mục tiêu (hạn lưu, xóa dữ liệu). | Năng lực 4 người × 4 tuần; 19 bảng chỉ phục vụ Ưu tiên 3. | vừa | Thêm bảng lại theo [08-deferred-tables](08-deferred-tables.md). **D-32 thay phần giữ `refresh_token`, `staff_zone`, `otp_challenge`, `ledger_head`, `audit_log`, `idempotency_keys`.** | migration |

## D-32

**Schema MVP v4: 23 bảng, bỏ 8, nhận 3 ý từ bản DBML thay thế, thêm nhật ký quyết định AI** ([ADR-0011](../07-adr/ADR-0011-mvp-simplifications.md)). Chốt 2026-11-18 với owner.

| ID | Câu hỏi | Quyết định | Lý do | Tin cậy | Nếu đổi | Đảo ngược |
|----|---------|------------|-------|---------|---------|-----------|
| D-32 | Demo 4 tuần thật sự cần bảng nào trong 27 bảng v3, cần thêm gì? | **Bỏ (8):** `staff_zone` → `app_user.staff_zone_id`; `refresh_token` → không (access JWT **8 giờ**, không thu hồi); `otp_challenge` → OTP trong Redis, DB giữ `agreement.*_confirmed_at` + một `consent_record`; `ledger_entry` + `ledger_head` → không (**FR-09 viết lại thành bằng chứng xác nhận**); `outbox` → `notification` cùng transaction, đẩy sau commit qua `platform.publish()`; `idempotency_keys` → cột UNIQUE `idempotency_key` trên từng bảng đích; `audit_log` → không (`zone_policy` có phiên bản). **Nhận (3 bảng, viết lại theo quy ước repo):** `agent_thread`, `recovery_case`, `consent_record`. **Thêm cho yêu cầu kiểm toán AI của ban tổ chức:** `ai_decision_log`. **Cột:** `slot.operational_status`, `booking.checked_in_at/checked_out_at`. | Ra demo sớm hơn; đề bài là cách hiểu của đội (owner xác nhận) nên sửa spec theo schema. 3 bảng thay thế lấp khoảng trống thật (trạng thái W3, bằng chứng đồng ý, thread M14); phần còn lại không nhận ([11](11-deferred-designs-functions.md#thiết-kế-nên-dùng-lại-từ-bản-dbml-thay-thế)). | vừa | Thêm bảng lại theo [08](08-deferred-tables.md). Trước người dùng thật: `refresh_token`, job xóa `ai_decision_log`, outbox khi có workflow do job kích hoạt. | migration |

## D-33

**Schema MVP v5: 25 bảng, thêm quá giờ (W4, không bảng) và tranh chấp (W5, 2 bảng)** (plan 003, file local trong `.claude/plans/`). Chốt 2026-11-19 với owner.

| ID | Câu hỏi | Quyết định | Lý do | Tin cậy | Nếu đổi | Đảo ngược |
|----|---------|------------|-------|---------|---------|-----------|
| D-33 | Đưa quá giờ (FR-11, FR-12) và tranh chấp (FR-13…16) từ Ưu tiên 3 vào MVP thế nào? | **Quá giờ không bảng:** 4 cột `zone_policy.overstay_*` + `payment_kind = 'overstay_fee'`. N2 gửi người thuê **hai** thông báo (khóa `overstay_pre:<booking_id>` trước giờ kết thúc, `overstay_due:<booking_id>` đúng giờ kết thúc), không nhắc thêm. Phí tính **lúc ra** (`checked_out_at`), từ giờ kết thúc khi đã quá ân hạn, theo mỗi bước đã bắt đầu; trigger `payment_overstay_guard` từ chối khi chưa check-out. **Người nhận phí** = người cho thuê (`booking.provider_user_id`), hoặc khu với booking TH3; không cột người nhận (VietQR mô phỏng, A-05). **Miễn phí chỉ qua tranh chấp** (`resolution_code = 'fee_waived'` → payment đang chờ thành `cancelled`). **Tranh chấp 2 bảng** lấy từ bản DBML thay thế: `dispute_case` (gộp `dispute_ticket` + `dispute_party` của v2) và `dispute_evidence` chỉ ghi thêm; enum `dispute_category` (5 loại), `dispute_status`, `evidence_kind`; `approval_kind` thêm `dispute_decision`. Mô hình thị giác chỉ nhận ảnh đã làm mờ (BR-14), xe nhận diện qua `lpr_event` + hash biển số; `object_key_original` bị thu quyền SELECT với vai trò app. `kpi_daily_v` thêm `overstay_fees`, `disputes_opened`, `dispute_prep_minutes_avg`. `overstay_case` vẫn hoãn. | Hai lần nhắc và phí lúc ra đủ cho FR-11/12 mà không cần hồ sơ riêng; tranh chấp cần bằng chứng bất biến và định tuyến theo khu của ô (BR-18) nên đáng 2 bảng. Quy tắc người nhận chọn phương án B, đơn giản nhất. | thấp (số liệu mặc định) / vừa (cấu trúc) | Thêm `overstay_case` khi cần nhắc lặp hoặc báo cáo quá giờ ([08](08-deferred-tables.md)); cột người nhận khi có thanh toán thật. | migration |

## D-34…D-37

**Schema v6: pilot một tòa, không thêm bảng** ([07 Pilot](../01-product/07-pilot-mot-toa.md), [ADR-0014](../07-adr/ADR-0014-eta-location-and-renter-priority-on-early-return.md)). Đề xuất 2026-11-22, chờ owner duyệt.

| ID | Câu hỏi | Quyết định | Lý do | Tin cậy | Nếu đổi | Đảo ngược |
|----|---------|------------|-------|---------|---------|-----------|
| D-34 | Hàng chờ người thuê (BR-21) lưu ở đâu? | Trên `parking_request`: `outcome = 'queued'`, `queue_status` (`waiting` / `matched` / `left` / `expired`), `queued_at`; thứ tự theo `queued_at`, không theo ETA; một yêu cầu `waiting` mỗi người mỗi tòa. | Yêu cầu đã là bản ghi KPI; không cần bảng hàng chờ riêng. | vừa | Bảng `queue_entry` nếu cần ưu tiên nhiều tiêu chí | migration |
| D-35 | Khi nào chỗ chia sẻ được coi là trống (BR-20)? | `share_window.owner_exited_at`, N1 đặt từ log `out` của xe thuộc chủ sau lúc đăng; ghép chỉ lấy khung `open` có cột này. | Phản hồi mentor: xe ra cổng chưa chắc ô trống; thêm bước chủ tự đăng. | vừa | Cảm biến ô thay log cổng | migration |
| D-36 | Chủ về sớm thì ai được ưu tiên (thay D-09)? | **Người thuê.** `recovery_case.new_return_at` = ETA, `eta_source`, `renter_decision`; `move` → lượt thay thế cùng giá, không thu thêm, không hoàn; `stay` / quá hạn → `owner_buffer_slot_id` (ô TH3 của tòa, miễn phí cho chủ); hết ô → `escalated` + `building.intake_paused_at`. `early_return_cost_rule = 'renter_priority_owner_buffer'`. | Người thuê không có lỗi; chủ vẫn luôn có chỗ đỗ. | thấp (cần BQL, A-12) | Quay lại D-09 bằng giá trị mới của CHECK | dữ liệu + migration |
| D-37 | Thanh toán trong app? | **Không.** `payment` là sổ khoản: bỏ `provider`, `paid_at`; trạng thái `recorded` / `cancelled`; loại `share_booking`, `th3_visit`, `cancel_refund`, `overstay_fee`; `payment_recorded_uq`; KPI theo `created_at`. | Bỏ QR khỏi demo (plan 022); phí vẫn cần cho BR-08, BR-23, KPI, tranh chấp. | vừa | Thêm lại cột nhà cung cấp, trạng thái thanh toán | migration |

## 1. Độ tin cậy thấp hoặc khó đảo ngược (duyệt trước)

| ID | Câu hỏi | Quyết định | Lý do (nguồn) | Tin cậy | Nếu đổi | Đảo ngược |
|----|---------|------------|---------------|---------|---------|-----------|
| D-05 | Giữ log LPR thô bao lâu? | **90 ngày.** **v3:** chỉ là mục tiêu, chưa thực thi; `lpr_event` không partition, `occupancy_hourly` hoãn. Phải có trước dữ liệu thật. | Vị trí chính xác là dữ liệu nhạy cảm (NĐ 356) [summary]; PDPL yêu cầu hạn lưu rõ; ANPR cảnh sát Anh giữ 12 tháng [summary], bãi tư nhân mục đích yếu hơn nên ngắn hơn. | vừa | `retention_rule('lpr_event')` | dữ liệu, nhưng **xóa là mất** |
| D-07 | Mã hóa biển số: ở app (KMS) hay pgcrypto (ADR-0005)? | **AES-256-GCM ở app, khóa bọc KMS;** khóa **HMAC-SHA256 blind index** riêng cho `plate_hash`. pgcrypto chỉ dùng cho test / seed. [09](09-adr-0005-amendment-proposal.md) | Với pgcrypto khóa đi qua SQL, có thể lộ trong log, `pg_stat_activity`. Blind index là cách chuẩn để tìm trên trường mã hóa [summary]. | vừa | Giữ pgcrypto thì quy tắc khóa ở [bảo mật §3](../06-operations/02-database-security.md) thành bắt buộc | **cấp migration**: đổi sau phải mã hóa lại mọi biển số |
| D-01 | Giá theo loại ô × cấp (BR-19) | `TH1/TH2` L1–L2: **50 000 đ/ngày, 10 000 đ/giờ**; L3: **70 000 đ/ngày, 15 000 đ/giờ**; `TH3` thành viên: **20 000 đ/giờ**, khách L4: **30 000 đ/giờ**; tổng theo giờ không quá giá ngày. Giá nằm trong `zone_policy.prices`. | PRD §8; Hà Nội 2026 giá đỗ đường phố **45 000 đ/60 phút** trong vành đai 1 [read: VOV]. TH3 khách thấp hơn giá đường để còn hấp dẫn. | thấp | Sửa `zone_policy.prices` | dữ liệu |
| D-02 | Dự phòng quanh khung chia sẻ (FR-06) | **15 phút trước, 30 phút sau** khung vắng của chủ. | Chưa có chuẩn VN; nền tảng P2P cho ~10 phút mỗi bên [read: JustPark]. Dự phòng *sau* bảo vệ quyền quay về (BR-07). | thấp | `zone_policy.buffer_before/after` | dữ liệu |
| D-03 | Quá giờ: thời gian cho phép, phí, nhịp nhắc | **Ân hạn 10 phút; 50 000 đ/giờ** tính theo mỗi bước 15 phút đã bắt đầu, **từ giờ kết thúc** khi đã quá ân hạn; nhắc người thuê **hai lần**: 20 phút trước giờ kết thúc và đúng giờ kết thúc (không nhắc mỗi 15 phút). Người nhận phí = người cho thuê, hoặc khu với booking TH3. **v3 / v4:** hoãn cùng W4. **v5 ([D-33](#d-33)):** vào MVP. | Chuẩn 10 phút ở bãi tư nhân Anh [read]. Phí cao hơn TH3 khách để quá giờ không bao giờ rẻ hơn trả tiền. | thấp | `zone_policy.overstay_*` (4 cột, v5) | dữ liệu |
| D-08 | Thế nào là "vượt ngưỡng" (BR-12)? | **Thỏa thuận ≥ 1 000 000 đ.** Chưa mô hình theo thời lượng / số lượt. | Chủ chỗ thu ~1 triệu/tháng, nên thuê cả tháng cần BQL duyệt, chia sẻ theo ngày tự động. | thấp | `zone_policy.approval_threshold_vnd` | dữ liệu / migration (tiêu chí mới) |
| D-04 | BR-16: lượt đang chạy giữ bao lâu sau khi tư cách hết hạn? | **Tối đa 7 ngày**, không quá giờ kết thúc. | Lượt đặt tối đa 31 ngày; 7 ngày đủ hết một tuần, chặn lạm dụng cả tháng. | thấp | `zone_policy.eligibility_grace_max` | dữ liệu |
| D-16 | Thời hạn giữ chỗ, xác nhận thỏa thuận | Giữ chỗ **10 phút**; xác nhận trong **30 phút**. | Thông lệ giữ hàng khi thanh toán; nhả ô nhanh khi một bên không trả lời. | thấp | `zone_policy.hold_ttl/agreement_confirm_ttl` | dữ liệu |
| D-21 | Ngưỡng OCR cần kiểm tra (BR-13) | **0.80**, nay là `zone_policy.ocr_review_threshold` (theo khu). | Phụ thuộc nhà cung cấp; chỉnh theo tuần dữ liệu thật đầu tiên. | thấp | Đổi giá trị | dữ liệu |
| D-11 | Văn phòng / phòng khám là tổ chức? | **Không có thực thể tổ chức.** Người đại diện giữ tư cách và chỗ; nhân viên có tư cách `employee`. | Đơn giản nhất; tài liệu không yêu cầu thanh toán cấp tổ chức. | thấp | Thêm bảng `organisation` | migration |
| D-12 | Dữ liệu cá nhân trong checkpointer LangGraph (schema `agent`) | **Được phép:** id, mã giả, văn bản đã ẩn danh, enum. **Không được:** tên, số điện thoại, biển số, tin nhắn gốc, bảng mã giả dạng rõ. Cô lập schema hai chiều (đã test). **v3:** job xóa 30 ngày hoãn. **v4:** `agent_thread` chỉ có `pending_card` ẩn danh. | RLS không nhìn được trong blob; LangGraph chạy lại node từ checkpoint nên gì trong state cũng tồn tại. | vừa | Quy tắc review code agent. **Chưa kiểm:** bảng thật của `langgraph-checkpoint-postgres`, serializer mã hóa | dữ liệu / code |
| D-13 | Một biển số trên nhiều tài khoản | **Cho phép;** unique theo `(user_id, plate_hash)`. LPR khớp nhiều xe → hàng chờ kiểm tra. | Gia đình dùng chung xe; quyền gắn với người. | vừa | Unique toàn cục trên `plate_hash` | migration |
| D-14 | Xóa dữ liệu với bằng chứng bất biến | `app.erase_user`: xóa tên, số điện thoại, email, biển số…; **giữ id**; từ chối khi còn booking đang chạy. **v3:** hoãn, phải có trước dữ liệu thật (20 ngày). **v4:** `consent_record` cần quy tắc xóa riêng vì chỉ ghi thêm. | PDPL có quyền xóa; NĐ 356 Đ.5: **20 ngày** [summary]. Chứng từ kế toán phải giữ nên giữ id / số tiền. | vừa | Hàm `app.erase_user` | migration |
| D-09 | Ai trả khi chủ về sớm (AC-09)? **Thay bởi D-36 (v6).** | **Chủ không trả thêm. Người thuê trả giá TH3 cho phần bị chuyển; hoàn tiền phần chưa dùng.** Loại thanh toán `relocation_th3`, `early_return_refund`; cờ `zone_policy.early_return_cost_rule`. **v4:** phần chia thể hiện qua hai khoản và `recovery_case.options`; người thuê đồng ý = `consent_record` (`accept_relocation`). | Giữ quyền quay về của chủ không bị phạt, đúng nỗi lo P3. | vừa | Thêm giá trị cho CHECK `early_return_cost_rule` | migration |

## 2. Độ tin cậy vừa

| ID | Câu hỏi | Quyết định | Lý do (nguồn) | Nếu đổi | Đảo ngược |
|----|---------|------------|---------------|---------|-----------|
| D-06 | Hạn lưu log, kiểm toán, tiền | Nhật ký **5 năm**; thỏa thuận, thanh toán, `consent_record` **10 năm**, không job xóa; thông báo 180 ngày. **v3 / v4:** chỉ là mục tiêu; `ai_decision_log` (mục tiêu 5 năm) cần chốt trước dữ liệu thật. | NĐ 356 yêu cầu giữ hồ sơ xử lý ≥ 5 năm [summary]; chứng từ kế toán ≥ 10 năm (NĐ 174/2016) [summary]. | Dòng `retention_rule` | dữ liệu (rút ngắn = mất) |
| D-10 | Hoán đổi có cần các bên đồng ý trước khi BQL duyệt? | **Có, mặc định;** cờ theo khu. **v3:** hoãn cùng M11. | Hoán đổi đổi quyền dùng ô người ta đã mua; làm mà không đồng ý sẽ sinh tranh chấp. | Cờ trong `zone_policy` | dữ liệu |
| D-15 | Theo dõi yêu cầu của chủ thể dữ liệu | `app.privacy_request` có `due_at`: xác nhận ≤ 2 ngày làm việc; truy cập / sửa ≤ 10; rút đồng ý ≤ 15; xóa ≤ 20 ngày. **v3:** hoãn. | NĐ 356 Đ.5 [summary]; **cần đối chiếu văn bản chính thức**. | Cấu hình app | dữ liệu |
| D-17 | Quy mô | **Giữ AS-01:** ~20 khu, ~300 nghìn user, ~150 nghìn ô, ~200 nghìn sự kiện LPR/ngày, ~5 triệu booking/năm. | Tài liệu không có số; không có gì mâu thuẫn. | Ngưỡng ở [vận hành §5](../06-operations/03-database-monitoring-scaling.md) | dữ liệu |
| D-18 | Giữ ô TH1/TH2 có làm người đó thành L1? | **Không.** Cấp đến từ tư cách căn hộ / shophouse / văn phòng; `slot_holding` chỉ cho quyền chia sẻ. | PRD §3.2 định nghĩa L1 bằng tài sản trong tòa. | Thêm nhánh trong `eligibility_level_at` | migration |
| D-20 | Model embedding cho W7 | **1024 chiều**, model đa ngôn ngữ trên Bedrock. | ADR-0007 chưa chọn model embedding. **Chưa kiểm model có ở region đã chọn.** | Đổi `vector(N)` + embed lại | migration (rẻ) |
| D-23 | Chuyển dữ liệu ra nước ngoài (Bedrock) | Prompt chỉ chứa dữ liệu đã ẩn danh. Chuẩn bị **hồ sơ đánh giá tác động trong 60 ngày** kể từ lần chuyển đầu, và DPIA, trước dữ liệu thật. | PDPL + NĐ 356 [summary]. Doanh nghiệp nhỏ có thể hoãn DPIA 5 năm — câu hỏi pháp lý. | Không ảnh hưởng schema | — |
| D-24 | OTP xác nhận thỏa thuận | 6 chữ số, **5 phút**, **5 lần thử**; v4 lưu trong Redis. | ADR-0006 yêu cầu hạn và giới hạn lần thử. | Cấu hình app | dữ liệu |
| D-25 | Sự kiện LPR có là dữ liệu nhạy cảm? | **Coi là nhạy cảm:** biển số mã hóa, MVP chỉ hiện bản ẩn, chỉ BQL truy cập. | NĐ 356 liệt kê vị trí chính xác là nhạy cảm [summary]. | — | — |

## 3. Độ tin cậy cao (có repo hoặc test)

| ID | Câu hỏi | Quyết định | Lý do |
|----|---------|------------|-------|
| D-22 | Luật riêng tư nào áp dụng? | **PDPL 91/2025/QH15 + NĐ 356/2025/NĐ-CP, hiệu lực từ 2026-01-01.** NĐ 13/2023 **hết hiệu lực**. | [read: luatvietnam; summary: vietnam-briefing, DFDL, EY, PwC] |
| D-19 | TH1 có mở cho cả khu (A-08)? | Cấu hình theo tòa; **mặc định `building`** (chỉ L1). | Scope A-08 |
| D-26 | EXCLUDE có nhả dòng đã hủy / chuyển / đóng? | **Có** với `booking`, `share_window`. **Sửa** `slot_holding`: thêm `voided_at` + `void_reason`. | Đã test đặt lại sau hủy, sau hết giữ chỗ, sau chuyển chỗ |
| D-27 | `ON DELETE SET NULL` bị CHECK chặn? | **Sửa một lỗi:** `lpr_event.reviewed_by` → **RESTRICT**. | Đã test |
| D-28 | Bảng ghi thiếu khóa idempotent | **Đã sửa;** v4 mỗi bảng đích có cột UNIQUE `idempotency_key`, `consent_record` dùng khóa tự nhiên. | Đã test |
| D-29 | Migration không khóa | Đã kiểm trên `booking`, `notification`, `lpr_event`. PostgreSQL **từ chối FK `NOT VALID` trên bảng partition**. | Chạy trên PG 17.10 |
| D-30 | Kiểm trên PG16 + pgvector | **Còn mở.** Docker không chạy được (WSL2 crash); mọi thứ chạy trên PG 17.10 không có pgvector. | Chạy hai script trong CI trên `pgvector/pgvector:pg16` |

## 4. Nguồn

Bản đầy đủ từng dòng (tiếng Anh, kèm mọi URL nguồn) ở commit `feff7b5`: `git show feff7b5:docs/03-design/07-db-decision-log.md`.
**Pháp lý VN:** PDPL 91/2025/QH15 và NĐ 356/2025/NĐ-CP (luatvietnam.vn) · Vietnam Briefing, DFDL, EY, Allen & Gledhill, CookieYes · NĐ 174/2016/NĐ-CP (caselaw.vn).
**Giá đỗ xe:** VOV 2026-10-18 · QĐ 44/2017/QĐ-UBND Hà Nội (lsvn.vn) · JustPark. **Hạn lưu LPR:** UK National ANPR Service. **Mã hóa trường:** CipherStash.
**Repo:** PRD §3–§9, Scope §3–§4, User Stories (AC-05, AC-09, AC-15, AC-22), wireframes, ADR-0005, 0006, 0007, 0010.
