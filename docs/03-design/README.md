# 03-design — Thiết kế chi tiết

> **Thư mục này trả lời:** dữ liệu được tổ chức thế nào và các đối tượng chính đi qua những trạng thái nào.

## Tổng quan

Thiết kế chi tiết ở mức dưới kiến trúc ([02-architecture](../02-architecture/README.md)) và trên code: lược đồ dữ liệu, máy trạng thái, sơ đồ trình tự. Thiết kế giao diện (UI) không nằm ở đây mà ở [01-product/ux/](../01-product/README.md).

Hiện có **thiết kế cơ sở dữ liệu PostgreSQL (đề xuất v3, MVP 27 bảng)**. Đây là đề xuất, chưa được BQL/nghiệp vụ duyệt; chưa có migration trong `server/migrations/`. Bản v2 (57 bảng) nằm trong git: `git show 333b85b:docs/database/02-schema.sql`.

## Tài liệu

| File | Nội dung |
|---|---|
| [01-data-model.md](01-data-model.md) | Điểm vào: tóm tắt, yêu cầu, giả định, quyết định chính, trạng thái kiểm chứng, truy vết yêu cầu → schema |
| [02-erd.md](02-erd.md) | ERD (Mermaid) và chính sách ON DELETE |
| [03-data-dictionary.md](03-data-dictionary.md) | Từ điển bảng và cột, sinh từ catalog |
| [04-queries-indexes.md](04-queries-indexes.md) | Truy vấn chính và index phục vụ chúng |
| [05-concurrency.md](05-concurrency.md) | Đồng thời và toàn vẹn cho từng luồng nhạy cảm |
| [06-risks-edge-cases.md](06-risks-edge-cases.md) | Tình huống biên và rủi ro |
| [07-db-decision-log.md](07-db-decision-log.md) | Nhật ký quyết định D-01…D-31, chờ nhóm duyệt |
| [08-deferred-tables.md](08-deferred-tables.md) | 30 bảng đã hoãn và cách thêm lại |
| [09-adr-0005-amendment-proposal.md](09-adr-0005-amendment-proposal.md) | Đề xuất sửa ADR-0005: mã hóa biển số ở ứng dụng (Proposed) |
| [sql/schema.sql](sql/schema.sql) · [sql/seed-and-tests.sql](sql/seed-and-tests.sql) | DDL và dữ liệu mẫu + kiểm thử |
| [diagrams/schema-diagram.html](diagrams/schema-diagram.html) · [diagrams/schema-overview.html](diagrams/schema-overview.html) | Sơ đồ schema mức cột (mở bằng trình duyệt) |

Liên quan, nằm ở thư mục khác: [vận hành CSDL](../08-operations/01-database-operations.md) · [checklist CSDL trước production](../07-deployment/01-db-preprod-checklist.md).

## Nên có thêm

| File gợi ý | Nội dung |
|---|---|
| `NN-state-machines.md` | Trạng thái của lượt đặt chỗ, thỏa thuận (chờ OTP, hiệu lực, từ chối, hết hạn), giao dịch chờ duyệt HITL |
| `NN-rls-policies.md` | Chính sách RLS theo khu và hộ; ai thấy dữ liệu gì (hiện rải trong `sql/schema.sql` và 01-data-model) |
| `NN-sequence-*.md` | Sơ đồ trình tự cho W1 → W2, W3, HITL resume |

## Nguồn để viết

- Thực thể và quy tắc: [PRD §2–5](../01-product/02-prd.md).
- Module và thư mục BE: [backlog/01-modules](../01-product/backlog/01-modules.md), [ADR-0010](../10-adr/ADR-0010-backend-modules-agent-workflows-jobs.md).
- CSDL và RLS: [ADR-0005](../10-adr/ADR-0005-rds-postgres-asyncpg-rls-alembic-sql.md); migration thật nằm ở `server/migrations/` (skill `new-migration`).
- Idempotency khi resume HITL: rủi ro R7 trong [Tech stack](../02-architecture/02-tech-stack.md).

## Quy ước

- File đánh số `NN-` theo thứ tự đọc; sơ đồ ưu tiên Mermaid trong Markdown để diff được. SQL đặt trong `sql/`, sơ đồ HTML trong `diagrams/`.
- Schema thật là code trong `server/migrations/`. Tài liệu ở đây chỉ giải thích; khi lệch, migration đúng hơn.
- Thêm file thì cập nhật bảng trên và [docs/README.md](../README.md).
