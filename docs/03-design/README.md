# 03-design — Thiết kế chi tiết

> **Thư mục này trả lời:** dữ liệu được tổ chức thế nào và các đối tượng chính đi qua những trạng thái nào.

## Tổng quan

Thiết kế chi tiết ở mức dưới kiến trúc ([02-architecture](../02-architecture/README.md)) và trên code: lược đồ dữ liệu, máy trạng thái, sơ đồ trình tự. Thiết kế giao diện (UI) không nằm ở đây mà ở [01-product/ux/](../01-product/README.md).

Hiện có **thiết kế cơ sở dữ liệu PostgreSQL (đề xuất v7, MVP 26 bảng, [ADR-0011](../07-adr/ADR-0011-mvp-simplifications.md))**. v6 (2026-11-22, D-34…D-37) theo [pilot một tòa](../01-product/07-pilot-mot-toa.md): hàng chờ, chỗ trống khi xe chủ đã ra, chủ về sớm ưu tiên người thuê, sổ khoản phí không QR; chưa chạy lại kiểm thử. v7 (2026-11-22, plan 024, D-38…D-41) theo bản cuối của pilot: OTP hai bên, GPS/ETA, duyệt 2 lớp, đối chiếu BQL, ưu tiên TH3. Đây là đề xuất, chưa được BQL/nghiệp vụ duyệt; chưa có migration trong `server/migrations/`. Bản v3 (27 bảng) nằm trong lịch sử git của thư mục này; bản v2 (57 bảng) nằm trong git: `git show 333b85b:docs/database/02-schema.sql`. v4 bỏ 8 bảng của v3 (`staff_zone`, `refresh_token`, `otp_challenge`, `ledger_head`, `ledger_entry`, `outbox`, `idempotency_keys`, `audit_log`) và thêm 4 bảng (`agent_thread`, `recovery_case`, `consent_record`, `ai_decision_log`); kiểm chứng trên PostgreSQL 17 với 180 phép kiểm. v5 (2026-11-19) thêm quá giờ (W4, không bảng: 4 cột `zone_policy.overstay_*` và loại thanh toán `overstay_fee`) và tranh chấp (W5, 2 bảng `dispute_case`, `dispute_evidence`, [D-33](07-db-decision-log.md#d-33)); kiểm chứng với 257 phép kiểm.

## Tài liệu

| File | Nội dung |
|---|---|
| [01-data-model.md](01-data-model.md) | Điểm vào: tóm tắt, yêu cầu, giả định, quyết định chính, trạng thái kiểm chứng, truy vết yêu cầu → schema |
| [02-erd.md](02-erd.md) · [erd/](erd/01-facility-people.md) | Ghi chú quan hệ, chính sách ON DELETE; 4 sơ đồ Mermaid trong `erd/` |
| [03-data-dictionary.md](03-data-dictionary.md) · [dictionary/](dictionary/01-facility.md) | Mục lục từ điển; bảng và cột theo nhóm module trong `dictionary/` (ràng buộc: `sql/schema.sql`) |
| [04-queries-indexes.md](04-queries-indexes.md) | Truy vấn chính và index phục vụ chúng |
| [05-concurrency.md](05-concurrency.md) | Đồng thời và toàn vẹn cho từng luồng nhạy cảm |
| [06-risks-edge-cases.md](06-risks-edge-cases.md) | Tình huống biên và rủi ro |
| [07-db-decision-log.md](07-db-decision-log.md) | Nhật ký quyết định D-01…D-41, chờ nhóm duyệt |
| [08-deferred-tables.md](08-deferred-tables.md) | 34 bảng đã hoãn (26 của v3 + 8 của v4; tranh chấp đã vào v5) và cách thêm lại; thiết kế nên tái dùng từ bản DBML thay thế |
| [09-adr-0005-amendment-proposal.md](09-adr-0005-amendment-proposal.md) | Đề xuất sửa ADR-0005: mã hóa biển số ở ứng dụng (Proposed) |
| [10-assumptions-traceability.md](10-assumptions-traceability.md) | Giả định AS-01…AS-21, yêu cầu phi chức năng, truy vết yêu cầu → schema |
| [11-deferred-designs-functions.md](11-deferred-designs-functions.md) | Thiết kế DBML nên dùng lại khi làm Ưu tiên 3 (tranh chấp đã nhận ở v5); hàm và enum đã bỏ |
| [sql/schema.sql](sql/schema.sql) · [sql/seed-and-tests.sql](sql/seed-and-tests.sql) | DDL và dữ liệu mẫu + kiểm thử |
| [diagrams/schema-diagram.html](diagrams/schema-diagram.html) | Sơ đồ schema mức cột, sinh tự động từ `sql/schema.sql` bằng `python scripts/gen_schema_diagram.py` (mở bằng trình duyệt; bấm bảng để xem quan hệ) |
| [diagrams/tables.html](diagrams/tables.html) | Từ điển 26 bảng (371 cột) sinh từ `sql/schema.sql` bằng `python scripts/gen_tables_html.py`: tìm kiếm, lọc theo nhóm, đánh dấu cột mới (plan 024) |

Liên quan, nằm ở thư mục khác: [vận hành CSDL](../06-operations/01-database-operations.md) ([bảo mật](../06-operations/02-database-security.md), [giám sát](../06-operations/03-database-monitoring-scaling.md)) · [checklist CSDL trước production](../05-deployment/01-db-preprod-checklist.md).

## Nên có thêm

| File gợi ý | Nội dung |
|---|---|
| `NN-state-machines.md` | Trạng thái của lượt đặt chỗ, thỏa thuận (chờ OTP, hiệu lực, từ chối, hết hạn), giao dịch chờ duyệt HITL |
| `NN-rls-policies.md` | Chính sách RLS theo khu và hộ; ai thấy dữ liệu gì (hiện rải trong `sql/schema.sql` và 01-data-model) |
| `NN-sequence-*.md` | Sơ đồ trình tự cho W1 → W2, W3, HITL resume |

## Nguồn để viết

- Thực thể và quy tắc: [PRD §2–5](../01-product/02-prd.md).
- Module và thư mục BE: [05 Backlog](../01-product/05-backlog.md#2-tính-năng), [ADR-0010](../07-adr/ADR-0010-backend-modules-agent-workflows-jobs.md).
- CSDL và RLS: [ADR-0005](../07-adr/ADR-0005-rds-postgres-asyncpg-rls-alembic-sql.md); migration thật nằm ở `server/migrations/` (skill `new-migration`).
- Idempotency khi resume HITL: rủi ro R7 trong [Tech stack](../02-architecture/02-tech-stack.md).

## Quy ước

- File đánh số `NN-` theo thứ tự đọc; sơ đồ ưu tiên Mermaid trong Markdown để diff được. SQL đặt trong `sql/`, sơ đồ HTML trong `diagrams/`. **Đổi `schema.sql` thì chạy lại `python scripts/gen_schema_diagram.py` và `python scripts/gen_tables_html.py`**, không sửa tay file HTML.
- Mỗi file `.md` dưới 100 dòng; nội dung tra cứu dài tách vào thư mục con (`erd/`, `dictionary/`). Bản đầy đủ trước khi tách: commit `feff7b5`.
- Schema thật là code trong `server/migrations/`. Tài liệu ở đây chỉ giải thích; khi lệch, migration đúng hơn.
- Thêm file thì cập nhật bảng trên và [docs/README.md](../README.md).
