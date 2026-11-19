# 01 — Mô hình dữ liệu: tổng quan thiết kế CSDL

## Tóm tắt

**Thiết kế này là gì:** schema PostgreSQL 16 cho ParkSmart AI (**v4 MVP: 23 bảng**, schema `app`; v3 có 27 bảng, v2 có 57 bảng), RLS theo khu/hộ,
bằng chứng xác nhận chỉ ghi thêm (`consent_record`), nhật ký quyết định AI (`ai_decision_log`), mã hóa biển số. Phạm vi = Ưu tiên 1 + 2 của
[backlog 4 tuần](../01-product/backlog/README.md). v4 theo [ADR-0011](../07-adr/ADR-0011-mvp-simplifications.md) và [D-32](07-db-decision-log.md#d-32).

**Hoãn trong MVP:** tranh chấp (M10), hoán đổi (M11), quá giờ (W4), voucher, dự báo, đối soát, quên mật khẩu, xem biển số gốc, xóa dữ liệu theo yêu cầu,
job xóa theo hạn lưu, partition `lpr_event`, refresh token, sổ cái hash-chain, outbox, bảng idempotency chung, audit log cấu hình → [08-deferred-tables](08-deferred-tables.md).

**10 quyết định quan trọng nhất** (chi tiết: [07-db-decision-log](07-db-decision-log.md))
1. RLS trên mọi bảng theo khu/hộ; khu khác chỉ nhận *cấp tư cách + hạn* (BR-17).
2. EXCLUDE constraint chống đặt trùng ô/giờ; dòng đã hủy / đổi chỗ / void không còn chặn (D-26).
3. Bằng chứng xác nhận hai bên (FR-09) là dòng `consent_record` chỉ ghi thêm (trigger `reject_mutation()` + vai trò app chỉ INSERT/SELECT); không hash-chain (D-32).
4. Biển số mã hóa **ở ứng dụng** AES-256-GCM + KMS, tra cứu bằng HMAC (D-07, [đề xuất sửa ADR-0005](09-adr-0005-amendment-proposal.md)); MVP chỉ hiện biển số ẩn.
5. Log LPR thô: mục tiêu giữ 90 ngày (D-05) nhưng MVP không partition, không job xóa.
6. Mục tiêu lưu: nhật ký 5 năm; bằng chứng, thỏa thuận, thanh toán 10 năm (D-06): **chỉ ghi trong tài liệu, chưa thực thi**.
7. Xóa dữ liệu cá nhân trong 20 ngày (Nghị định 356/2025, D-14, D-15): hoãn, **bắt buộc làm trước khi có dữ liệu thật**.
8. Chủ về sớm: chủ không chịu thêm phí; người thuê trả giá TH3 cho phần bị chuyển, được hoàn phần chưa dùng (D-09).
9. Hoán đổi và đồng ý hai bên (D-10) hoãn cùng M11.
10. Ngưỡng duyệt 1 000 000 đ / thỏa thuận; dự phòng 15/30 phút (D-02, D-08, *mặc định, cần BQL xác nhận*); giá trong `zone_policy.prices` (D-01).

**5 rủi ro lớn nhất:** (1) chưa chạy trên PG16 + pgvector; (2) giá / ngưỡng / thời gian là số mặc định; (3) chưa EXPLAIN với dữ liệu lớn;
(4) checkpoint LangGraph (schema `agent`) có thể chứa dữ liệu cá nhân nếu code agent không ẩn danh (D-12); (5) chưa có xóa dữ liệu / hạn lưu. Chi tiết: [06](06-risks-edge-cases.md).

## 1. Thay đổi ở v4 (23 bảng)

| Mục | Thay đổi |
|-----|----------|
| Bỏ (8) | `staff_zone` → `app_user.staff_zone_id`; `refresh_token` (access JWT 8 giờ); `otp_challenge` (OTP trong Redis); `ledger_entry`, `ledger_head` (FR-09 = `consent_record`); `outbox` (notification ghi cùng transaction, đẩy sau commit); `idempotency_keys` (UNIQUE `idempotency_key` trên từng bảng đích); `audit_log` |
| Thêm (4) | `agent_thread` (thread LangGraph + `pending_card`), `recovery_case` (W3), `consent_record` (bằng chứng chỉ ghi thêm), `ai_decision_log` (kiểm toán AI chỉ ghi thêm, chỉ hash) |
| Cột | `slot.operational_status` thay `is_active`; `booking.checked_in_at/checked_out_at`; `approval_request.thread_id` → `agent_thread` |
| Kiểm thử | 180 phép kiểm (106 âm, 74 dương) trên PG17 |

Lịch sử v3 (57 → 27 bảng, D-31) và v2: git log của thư mục này; DDL v2: `git show 333b85b:docs/database/02-schema.sql`.

## 2. Miền nghiệp vụ trong một đoạn

Một đơn vị vận hành một chuỗi N ≥ 2 khu. Mỗi khu có tòa (khối đế shophouse, văn phòng…), shophouse thấp tầng và bãi công cộng; hầm có
TH1 (đã mua, chủ cho thuê, phạm vi tòa → khu), TH2 (thuê từ chủ đầu tư, đồng ý theo pool, phạm vi khu → chuỗi) và TH3 (công cộng, chỉ BQL).
Một người có một tài khoản, nhiều tư cách; cấp tại một tòa là L1 > L2 > L3 > L4 (BR-15). Luồng chính: yêu cầu → cấp → định tuyến (ghép TH1/TH2
hoặc TH3 / công cộng) → giữ chỗ → thỏa thuận (hai bên xác nhận OTP, mỗi xác nhận = một `consent_record`) → BQL duyệt nếu vượt ngưỡng →
thanh toán mô phỏng (Ưu tiên 2). Ngoại lệ trong MVP: chủ về sớm (`recovery_case`), nạp log LPR, KPI.

## 3. Giả định, yêu cầu phi chức năng, truy vết

AS-01…AS-17, yêu cầu phi chức năng và truy vết yêu cầu → schema: [10-assumptions-traceability](10-assumptions-traceability.md).

## 4. Quyết định chính

| # | Quyết định | Lý do / phương án đã loại |
|---|------------|---------------------------|
| 4.1 | Một schema `app`, bảng nhóm theo module (ADR-0010); schema `agent` cho checkpointer LangGraph | Cần FK chéo module; schema riêng từng module thêm việc cấp quyền, search_path mà không cô lập thật |
| 4.2 | Khóa UUIDv7 cho thực thể; `bigint` identity cho `lpr_event`, `consent_record`, `ai_decision_log`; `agent_thread` khóa bằng `thread_id` của LangGraph | Id trong URL và state workflow không được đoán được; app tạo id trước khi insert; v7 giữ B-tree chèn theo thứ tự |
| 4.3 | `zone_id` trên mọi dòng thuộc khu, giữ đúng bằng FK ghép `(parent_id, zone_id)` | RLS cần nó; có ràng buộc bảo vệ nên không lệch 3NF. Cùng cách đó buộc người cho thuê của booking = chủ khung chia sẻ |
| 4.4 | DB giữ bất biến cứng (EXCLUDE, `booking_validate`, `share_window_validate`, thỏa thuận chỉ hiệu lực khi đủ hai xác nhận); **rule engine quyết định** (BR-14) | Từ chối dòng sai do lỗi app; không thay `policy/domain` |
| 4.5 | `app.eligibility_level_at(user, building, at)` là `SECURITY DEFINER`, chỉ trả `(level, valid_until)` | BR-17: BQL khu khác biết cấp, không thấy dòng tài sản |
| 4.6 | Biển số: `plate_ciphertext` (thu quyền theo cột), `plate_hash` (HMAC blind index), `plate_masked`; MVP không có đường xem bản gốc | Nếu màn hình nào cần biển số gốc thì phải có `plate_access_log` + hàm xem trước (AC-12) |
| 4.7 | Bằng chứng xác nhận = `consent_record` chỉ ghi thêm (`reject_mutation()`, quyền INSERT/SELECT, khóa UNIQUE tự nhiên); không chuỗi hash | Mất khả năng phát hiện dòng bị superuser xóa. Chuỗi hash quay lại khi có yêu cầu pháp lý |
| 4.7a | `agent_thread` không lưu văn bản gốc (D-12); `recovery_case` một hồ sơ mở mỗi booking; khóa idempotent `ai_decision_log` = `thread_id:checkpoint_id:node`; notification ghi cùng transaction, đẩy qua `platform.publish()` | ADR-0011; port cho phép thêm outbox sau |
| 4.8 | MVP không partition; `lpr_event` là bảng thường, chống trùng `UNIQUE (zone_id, source_code, source_event_id)` | Dữ liệu demo rất nhỏ; partition trước khi lên hàng chục triệu dòng ([vận hành §5](../06-operations/03-database-monitoring-scaling.md)) |
| 4.9 | Enum cho tập đóng (loại ô, phạm vi, cấp, trạng thái, `size_class` có thứ tự); `jsonb` chỉ cho bằng chứng, `pending_card`, `recovery_case.options`, `zone_policy.prices`, deep link | Không EAV, không cột nhiều giá trị |
| 4.10 | PostgreSQL 16 trên RDS + `btree_gist`, `pgvector`; `pgcrypto` chỉ cho seed / test; Alembic SQL thuần; chưa cần `pg_trgm` | ADR-0005; mã hóa ở ứng dụng (D-07) |

## 5. Câu hỏi → quyết định

Mọi câu hỏi v1 (Q1–Q13) đã có quyết định trong [07-db-decision-log](07-db-decision-log.md); giá trị là mặc định, cần BQL xác nhận.

## 6. Trạng thái kiểm chứng

| Hạng mục | Trạng thái |
|----------|------------|
| `sql/schema.sql` + `sql/seed-and-tests.sql` (v4) | **Đã chạy trên PostgreSQL 17: 180 phép kiểm đạt**; `pg_tables` trong `app` = 23 |
| Chạy trên **PostgreSQL 16** + pgvector | **Chưa chạy** (Docker / WSL2 local bị crash; không build được pgvector) |
| `knowledge_chunk.embedding vector(1024)` | Chưa chạy (tắt bằng `parksmart.allow_missing_pgvector=on`) |
| Đồng thời (v2, PG17, cùng mã EXCLUDE) | 8 phiên tranh một ô → 1 booking, 7 × `23P01` |
| Migration không khóa | Đã kiểm trên PG17 (v2): index `CONCURRENTLY`, FK `NOT VALID` + `VALIDATE` |
| EXPLAIN với dữ liệu thật | **Chưa làm**; [04](04-queries-indexes.md) giữ plan của v1 |

**Để lấp khoảng trống** trên máy có Docker: `docker compose up -d postgres`, rồi `psql -v ON_ERROR_STOP=1 -f sql/schema.sql` và
`-f sql/seed-and-tests.sql`; dòng cuối mong đợi `== done: all assertions passed`.
