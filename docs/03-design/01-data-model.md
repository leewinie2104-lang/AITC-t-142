# 01 — Mô hình dữ liệu: tổng quan thiết kế CSDL

## Tóm tắt

**Thiết kế này là gì:** schema PostgreSQL 16 cho ParkSmart AI (**v7 đề xuất: 26 bảng**, schema `app`; v6 có 25, v4 có 23, v3 có 27, v2 có 57),
RLS theo khu/hộ, bằng chứng xác nhận chỉ ghi thêm (`consent_record`), tranh chấp, nhật ký quyết định AI, mã hóa biển số.
Phạm vi = use case **pilot một tòa bản cuối** ([01-product/07](../01-product/07-pilot-mot-toa.md), 2026-11-22). Lịch sử thay đổi: mục 1.

**Danh sách bảng chi tiết:** [sơ đồ schema](diagrams/schema-diagram.html) (mở trình duyệt; bấm bảng để xem từ điển cột, index, RLS; cột v7 có chip) · [03-data-dictionary](03-data-dictionary.md).

**Hoãn trong MVP:** hoán đổi (M11), hồ sơ quá giờ riêng, voucher, dự báo, đối soát, quên mật khẩu, xem biển số gốc, xóa theo yêu cầu,
job xóa theo hạn lưu, partition `lpr_event`, refresh token, sổ cái hash-chain, outbox, idempotency chung, audit log cấu hình → [08-deferred-tables](08-deferred-tables.md).

**10 quyết định quan trọng nhất** (chi tiết: [07-db-decision-log](07-db-decision-log.md))
1. RLS trên mọi bảng theo khu/hộ; khu khác chỉ nhận *cấp tư cách + hạn* (BR-17).
2. EXCLUDE chống đặt trùng ô/giờ; dòng đã hủy / đổi chỗ / void không còn chặn (D-26).
3. Bằng chứng xác nhận là `consent_record` chỉ ghi thêm; không hash-chain (D-32).
4. Biển số mã hóa **ở ứng dụng** AES-256-GCM + KMS, tra cứu bằng HMAC; MVP chỉ hiện biển số ẩn (D-07).
5. **Hai OTP, mỗi bên với hệ thống** (BR-25): chủ lúc đăng, người thuê lúc được gán. DB chỉ lưu *thời điểm* xác nhận, không lưu mã (D-38).
6. **Giữ chỗ theo ETA** (BR-22): OTP 3 phút; giữ ETA + 10, tối đa 40 (TH3: 60); không tới → phí 30%, hoàn 70% (D-39).
7. **GPS/ETA không lưu tọa độ** (BR-27): chỉ phút ETA, thời điểm, nguồn, và `consent_record` đồng ý vị trí (D-39).
8. **Duyệt 2 lớp** (BR-26): cột kết quả trên `approval_request`; BQL chỉ xem ca xấu; AI chỉ siết (D-40).
9. **Đăng ký tự đối chiếu dữ liệu BQL** (FR-38): một bảng nhập một lần, không bảng đếm chỗ TH3 (D-41).
10. Tham số pilot nằm trong `zone_policy` (phiên bản, có hiệu lực theo thời điểm); mặc định là **giá trị nghiên cứu, cần BQL xác nhận** (D-02, D-08, D-16).

**5 rủi ro lớn nhất:** (1) chưa chạy trên PG16 + pgvector và btree_gist; (2) giá / ngưỡng / thời gian là số mặc định; (3) chưa EXPLAIN với dữ liệu lớn;
(4) GPS có thể bị giả, ETA là ước lượng; (5) chưa có xóa dữ liệu / hạn lưu. Chi tiết: [06](06-risks-edge-cases.md).

## 1. Thay đổi theo phiên bản

**v7 (+1 bảng, plan 024, D-38…D-41):**

| Bảng | Thay đổi |
|------|----------|
| `share_window` | `owner_otp_confirmed_at` (BR-25), `expires_at` (đăng + 30', BR-20); `status = 'open'` cần OTP chủ; CHECK chỉ-ra-sau-OTP |
| `parking_request` | `queue_status`: `queued` → `eligible` → `assigned` → `otp_pending` → `holding` → `parked`; `expired` / `rejected` / `escalated` / `left`. ETA: `last_eta_minutes`, `last_eta_at`, `eta_source` (gps / manual / none), `gps_consent_id`, `gps_missed_streak`; `is_urban_related` (BR-28) |
| `booking` | `assigned_at`, `renter_otp_confirmed_at`, `no_show_fee_vnd`; `hold_expires_at` = hạn OTP trước khi nhập, = ETA + 10 sau đó |
| `approval_request` | `rule_result` (pass / reject / gray), `ai_risk` (normal / suspicious), `reasons` (jsonb), `escalated_at`, `bql_deadline_at` (đổi tên `due_at`), `bql_decision`; loại mới `booking_review`, `registration_review` |
| `zone_policy` | bỏ `hold_ttl`; thêm 11 tham số pilot (`hold_after_eta`, `hold_max`, `th3_hold_max`, `otp_confirm_ttl`, `listing_expiry`, `eta_assign_max`, `gps_interval`, `bql_review_ttl`, `no_show_fee_rate`, `no_show_min_hours`, `th3_guest_alert_slots`) |
| `consent_record` | thêm `owner_listing_otp`, `renter_assignment_otp`; `subject_type` thêm `share_window`, `booking`, `parking_request` |
| **mới** `bql_registry_import` | dữ liệu BQL nhập một lần (cư dân, shophouse, ô + kích thước, biển số dạng hash) để đối chiếu đăng ký (FR-38) |
| hàm `app.th3_free_slots()` | số chỗ TH3 còn lại = ô đang hoạt động trừ lượt đang giữ/đã đặt; không có bảng đếm (BR-28) |

Không đổi: `payment` (không thêm loại; phí không tới là `booking.no_show_fee_vnd` và khoản hoàn `cancel_refund` = giá − phí).
`recovery_case.eta_source`: giá trị `location` đổi thành `gps`. Chưa chạy: xem mục 6.

**v6 (25 bảng, plan 023, D-34…D-37):** hàng chờ trên `parking_request`; `share_window.owner_exited_at`; `recovery_case` (ETA chủ, quyết định, ô dự phòng);
`building.intake_paused_at`; `payment` thành sổ khoản phí không QR (`cancel_refund`).

**v5 (+2 bảng, D-33):** `dispute_case`, `dispute_evidence`; quá giờ không bảng (`zone_policy.overstay_*`, `payment.kind = 'overstay_fee'`, trigger `payment_overstay_guard`);
`kpi_daily_v` có cột phí và tranh chấp.

**v4 (23 bảng, ADR-0011, D-32):** bỏ 8 bảng (`staff_zone` → `app_user.staff_zone_id`, `refresh_token`, `otp_challenge` → Redis, `ledger_*`, `outbox`, `idempotency_keys`, `audit_log`);
thêm `agent_thread`, `recovery_case`, `consent_record`, `ai_decision_log`. Lịch sử v2–v3: git log và [08-deferred-tables](08-deferred-tables.md).

## 2. Miền nghiệp vụ trong một đoạn

Một đơn vị vận hành một chuỗi N ≥ 2 khu. Mỗi khu có tòa, shophouse thấp tầng và bãi công cộng; hầm có
TH1 (đã mua, chủ cho thuê, phạm vi tòa → khu), TH2 (thuê từ chủ đầu tư, phạm vi khu → chuỗi) và TH3 (công cộng, BQL khai thác).
Một người có một tài khoản, nhiều tư cách; cấp tại một tòa là L1 > L2 > L3 > L4 (BR-15). Luồng chính pilot:
chủ đăng (OTP) → người thuê vào hàng chờ (GPS/ETA) → đủ điều kiện, được gán → OTP nhận chỗ, bắt đầu giữ → xe vào (`parked`) → thỏa thuận và duyệt 2 lớp khi cần.
Ngoại lệ: chủ về sớm (`recovery_case`), quá giờ, tranh chấp (`dispute_case`), đối chiếu đăng ký (`bql_registry_import`), KPI.

## 3. Giả định, yêu cầu phi chức năng, truy vết

AS-01…AS-17 (cộng AS-18…AS-21 của v7), yêu cầu phi chức năng và truy vết: [10-assumptions-traceability](10-assumptions-traceability.md).

## 4. Quyết định chính

| # | Quyết định | Lý do / phương án đã loại |
|---|------------|---------------------------|
| 4.1 | Một schema `app`, bảng nhóm theo module (ADR-0010); schema `agent` cho checkpointer LangGraph | Cần FK chéo module; schema riêng thêm việc cấp quyền mà không cô lập thật |
| 4.2 | UUIDv7 cho thực thể; `bigint` identity cho log (`lpr_event`, `consent_record`, `ai_decision_log`, `dispute_evidence`, `bql_registry_import`); `agent_thread` khóa bằng `thread_id` | Id trong URL không đoán được; app tạo id trước khi insert |
| 4.3 | `zone_id` trên mọi dòng thuộc khu, giữ đúng bằng FK ghép `(parent_id, zone_id)` | RLS cần nó; ràng buộc bảo vệ nên không lệch |
| 4.4 | DB giữ bất biến cứng (EXCLUDE, trigger, CHECK OTP/ETA/duyệt); **rule engine quyết định** (BR-14) | Từ chối dòng sai do lỗi app; không thay `policy/domain` |
| 4.5 | `app.eligibility_level_at()` là `SECURITY DEFINER`, chỉ trả `(level, valid_until)` | BR-17: BQL khu khác biết cấp, không thấy dòng tài sản |
| 4.6 | Biển số: `plate_ciphertext` (thu quyền theo cột), `plate_hash` (HMAC), `plate_masked`; registry chỉ giữ hash + ẩn | AC-12; xem gốc cần `plate_access_log` (hoãn) |
| 4.7 | Bằng chứng = `consent_record` chỉ ghi thêm (`reject_mutation()`, quyền INSERT/SELECT) | Chuỗi hash quay lại khi có yêu cầu pháp lý |
| 4.8 | Tọa độ GPS không bao giờ vào DB; chỉ `last_eta_minutes`, `last_eta_at`, `eta_source` | BR-27, NĐ 13/2023 (tối thiểu hóa); LLM chỉ nhận phút |
| 4.9 | OTP không lưu trong bảng; chỉ `owner_otp_confirmed_at`, `renter_otp_confirmed_at` | BR-25; mã OTP ở dịch vụ OTP (Redis, TTL) như v4 |
| 4.10 | TH3 đếm chỗ bằng hàm, không bảng đếm; ưu tiên bằng cờ `is_urban_related` | Số không lệch khỏi booking; BR-28 |
| 4.11 | Enum cho tập đóng; `jsonb` chỉ cho bằng chứng, `pending_card`, `reasons`, `recovery_case.options`, `zone_policy.prices` | Không EAV, không cột nhiều giá trị |
| 4.12 | PostgreSQL 16 trên RDS + `btree_gist`, `pgvector`; `pgcrypto` chỉ cho seed/test; migration SQL thuần | ADR-0005; mã hóa ở ứng dụng (D-07) |

## 5. Câu hỏi → quyết định

Câu hỏi v1 (Q1–Q13) và các câu hỏi pilot đã có quyết định trong [07-db-decision-log](07-db-decision-log.md); giá trị là mặc định, cần BQL xác nhận.

## 6. Trạng thái kiểm chứng

| Hạng mục | Trạng thái |
|----------|------------|
| `sql/schema.sql` + `sql/seed-and-tests.sql` (v7) | **Chưa chạy.** Chỉ kiểm cú pháp bằng `pglast`: câu lệnh schema và seed đều đọc được. Phép kiểm `expect_fail` và ràng buộc mới chưa được chạy |
| v6 | Chưa chạy lại trên PG; bản v5 đã chạy trên PG17 (257 phép kiểm, `app` = 25 bảng) |
| Chạy trên **PostgreSQL 16** + pgvector | **Chưa chạy**: máy làm tài liệu thiếu `btree_gist`, `pgcrypto`, và không có Docker |
| Đồng thời (v2, PG17, cùng mã EXCLUDE) | 8 phiên tranh một ô → 1 booking, 7 × `23P01` |
| EXPLAIN với dữ liệu thật | **Chưa làm**; [04](04-queries-indexes.md) giữ plan của v1 |

**Để lấp khoảng trống** trên máy có Docker: `docker compose up -d postgres`, rồi `psql -v ON_ERROR_STOP=1 -f sql/schema.sql` và
`-f sql/seed-and-tests.sql`; dòng cuối mong đợi `== done: all assertions passed`. Sinh lại HTML: `python scripts/gen_schema_diagram.py`.
