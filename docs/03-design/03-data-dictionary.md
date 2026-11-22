# 03 — Từ điển dữ liệu

> Theo [sql/schema.sql](sql/schema.sql) v7 (đề xuất, chưa dựng trên PostgreSQL; cột pgvector `knowledge_chunk.embedding` không tính): **26 bảng, 371 cột**
> và view `kpi_daily_v`. Bản HTML có tìm kiếm, lọc theo nhóm và đánh dấu cột mới: [diagrams/tables.html](diagrams/tables.html).
> Kiểu, null, mặc định khớp DDL; phần ý nghĩa viết tay. Khi schema đổi, sinh lại thay vì sửa tay cột kiểu.

**Quy ước.** Mọi bảng nằm trong schema `app`. `RLS` = bật row-level security. Thời gian là `timestamptz` (UTC); khoảng thời gian là
nửa mở `[bắt đầu, kết thúc)`. Tiền là `bigint` VND. Ràng buộc, index và giá trị enum **chỉ** có trong [sql/schema.sql](sql/schema.sql)
(các khối "Constraints and indexes" theo bảng đã bỏ khỏi từ điển cho file ngắn; DDL là nguồn).

## Mục lục

| File | Bảng |
|------|------|
| [01 Cơ sở vật chất, pool](dictionary/01-facility.md) (M2, M3) | `zone` · `building` · `slot_pool` · `slot` |
| [02 Tài khoản, nội quy](dictionary/02-identity-policy.md) (M1, M3) | `app_user` · `vehicle` · `zone_policy` |
| [03 Tư cách](dictionary/03-eligibility.md) (M1) | `asset` · `eligibility` · `slot_holding` · `bql_registry_import` (v7) |
| [04 Chia sẻ, yêu cầu](dictionary/04-sharing-requests.md) (M4, M5) | `share_window` · `parking_request` |
| [05 Đặt chỗ, chủ về sớm](dictionary/05-booking-recovery.md) (M5, M9) | `booking` · `recovery_case` |
| [06 Thỏa thuận, thanh toán](dictionary/06-agreement-payment.md) (M6, M7) | `agreement` · `consent_record` · `payment` |
| [07 Vận hành](dictionary/07-operations.md) (M8, M12, M13) | `lpr_event` · `approval_request` · `notification` |
| [08 Agent, tri thức](dictionary/08-agent-knowledge.md) (M14, W7) | `agent_thread` · `ai_decision_log` · `knowledge_chunk` · view `kpi_daily_v` |
| [09 Tranh chấp](dictionary/09-disputes.md) (M10, W5) | `dispute_case` · `dispute_evidence` |

## Bảng theo mức ưu tiên của backlog

Cả 26 bảng phục vụ Ưu tiên 1 hoặc 2 của [backlog 4 tuần](../01-product/05-backlog.md) và pilot một tòa (v7):

- **Ưu tiên 1:** `zone`, `building`, `slot_pool`, `slot`, `app_user`, `vehicle`, `asset`, `eligibility`, `slot_holding`, `zone_policy`,
  `share_window`, `parking_request`, `booking`, `agreement`, `consent_record`, `lpr_event` (N1), `approval_request`, `notification`,
  `agent_thread`, `ai_decision_log`.
- **Ưu tiên 1 (v6):** `payment` là sổ khoản phí, không QR (D-37). **v7:** `bql_registry_import` (FR-38); OTP, ETA và duyệt 2 lớp là cột trên bảng sẵn có.
- **Ưu tiên 2:** `recovery_case` (W3), `knowledge_chunk` (W7), view `kpi_daily_v` (KPI),
  `dispute_case`, `dispute_evidence` (W5, v5). Quá giờ (W4) không có bảng riêng: cột `zone_policy.overstay_*` + `payment.kind = 'overstay_fee'`.

## Bảng đã bỏ

- **v4 (8 bảng):** `staff_zone`, `refresh_token`, `otp_challenge`, `ledger_head`, `ledger_entry`, `outbox`, `idempotency_keys`,
  `audit_log`; xem [ADR-0011](../07-adr/ADR-0011-mvp-simplifications.md), [D-32](07-db-decision-log.md#d-32).
- **v3 (30 bảng):** `chain`, `subzone`, `basement`, `voucher`, `dispute_*` (v2: 4 bảng, thay bằng 2 bảng ở v5), `swap_*`, `kpi_daily` …
- Cách thêm lại từng bảng: [08-deferred-tables.md](08-deferred-tables.md).
