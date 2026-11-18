# 03-design — Thiết kế chi tiết

> **Thư mục này trả lời:** dữ liệu được tổ chức thế nào và các đối tượng chính đi qua những trạng thái nào.

## Tổng quan

**Chưa có tài liệu.** Thư mục này dành cho thiết kế chi tiết ở mức dưới kiến trúc ([02-architecture](../02-architecture/README.md)) và trên code: lược đồ dữ liệu, máy trạng thái, sơ đồ trình tự. Thiết kế giao diện (UI) không nằm ở đây mà ở [01-product/ux/](../01-product/README.md).

## Nên có

| File gợi ý | Nội dung |
|---|---|
| `01-data-model.md` | ERD: chuỗi, khu, phân khu, tòa, hầm, ô; tài khoản, tư cách; lịch chia sẻ, đặt chỗ, thỏa thuận, sổ cái |
| `02-state-machines.md` | Trạng thái của lượt đặt chỗ, thỏa thuận (chờ OTP, hiệu lực, từ chối, hết hạn), giao dịch chờ duyệt HITL |
| `03-rls-policies.md` | Chính sách RLS theo khu và hộ; ai thấy dữ liệu gì |
| `04-sequence-*.md` | Sơ đồ trình tự cho W1 → W2, W3, HITL resume |

## Nguồn để viết

- Thực thể và quy tắc: [PRD §2–5](../01-product/02-prd.md).
- Module và thư mục BE: [backlog/01-modules](../01-product/backlog/01-modules.md), [ADR-0010](../10-adr/ADR-0010-backend-modules-agent-workflows-jobs.md).
- CSDL và RLS: [ADR-0005](../10-adr/ADR-0005-rds-postgres-asyncpg-rls-alembic-sql.md); migration thật nằm ở `server/migrations/` (skill `new-migration`).
- Idempotency khi resume HITL: rủi ro R7 trong [Tech stack](../02-architecture/02-tech-stack.md).

## Quy ước

- File đánh số `NN-` theo thứ tự đọc; sơ đồ ưu tiên Mermaid trong Markdown để diff được.
- Schema thật là code trong `server/migrations/`. Tài liệu ở đây chỉ giải thích; khi lệch, migration đúng hơn.
- Thêm file thì cập nhật bảng trên và [docs/README.md](../README.md).
