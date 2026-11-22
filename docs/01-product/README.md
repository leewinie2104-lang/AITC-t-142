# 01-product — Đặc tả sản phẩm

> **Thư mục này trả lời:** ParkSmart AI giải bài toán gì, cho ai, theo quy tắc nào, làm gì trước, và màn hình trông ra sao.

## Tổng quan

Toàn bộ yêu cầu sản phẩm nằm ở đây, đi từ đề bài gốc tới backlog và wireframe. Mọi file suy ra từ [00 Bài toán](00-xac-dinh-bai-toan.md). Khi tài liệu lệch code trong `server/src/app/`, code đúng hơn.

## File và thư mục

| File / thư mục | Trả lời câu hỏi |
|---|---|
| [00-xac-dinh-bai-toan.md](00-xac-dinh-bai-toan.md) | Đề bài gốc: bối cảnh, vấn đề, đối tượng, Agent làm gì, KPI |
| [01-project-brief.md](01-project-brief.md) | Vì sao làm: vấn đề P1–P8, ai cần thuê chỗ, giải pháp, giá trị, KPI |
| [02-prd.md](02-prd.md) | Làm theo quy tắc nào: tư cách L1–L4, TH1–TH3, phạm vi mở, BR, FR, giá |
| [03-scope.md](03-scope.md) | Bản demo gồm gì, không gồm gì; dữ liệu và quyền riêng tư; giả định A-01…A-12 |
| [04-user-stories.md](04-user-stories.md) | Ai cần gì (US) và làm sao biết đã đúng (AC Given/When/Then) |
| [06-traceability.md](06-traceability.md) | US → AC → module → workflow → use case → màn hình |
| [05-backlog.md](05-backlog.md) | Việc cần làm trong 4 tuần: ưu tiên use case pilot, cách đọc, tóm tắt theo tuần |
| [backlog.html](backlog.html) | Bảng backlog đầy đủ: mỗi tính năng chia DB / BE / Worker nền / Worker Agent / FE; lọc theo mức, tuần, người làm, tìm kiếm; mở trong trình duyệt |
| [07-pilot-mot-toa.md](07-pilot-mot-toa.md) | **Use case ưu tiên**: pilot một tòa, hàng chờ, ghép, giữ chỗ, về sớm theo ETA, AI dùng vào đâu |
| [ux/01-user-flow.md](ux/01-user-flow.md) | Các luồng nghiệp vụ của bản demo |
| [ux/wireframes/](ux/wireframes/README.md) | 19 màn hình HTML low-fidelity; mở `index.html` trong trình duyệt |
| `ux/ui-design/` | Chưa có (thiết kế giao diện chi tiết) |

## Đọc theo vai trò

| Vai trò | Đọc |
|---|---|
| Mentor, người mới | [07 Pilot một tòa](07-pilot-mot-toa.md) → [01 Brief](01-project-brief.md) → [05 Backlog](05-backlog.md) §0–1 |
| AI Agent | [02 PRD](02-prd.md) §3–5 → [backlog.html](backlog.html) (lọc cột Worker Agent) → [04 US & AC](04-user-stories.md) |
| Server core | [02 PRD](02-prd.md) → [backlog.html](backlog.html) (lọc cột BE) → [06 Traceability](06-traceability.md) |
| Client | [04 US & AC](04-user-stories.md) → [ux/01-user-flow](ux/01-user-flow.md) → [wireframes](ux/wireframes/README.md) |
| Hạ tầng, worker | [03 Scope](03-scope.md) → [backlog.html](backlog.html) (lọc cột Worker nền) |

## Bảng mã định danh

| Mã | Nghĩa | Định nghĩa ở |
|---|---|---|
| P1–P8 | Vấn đề | Brief §2 |
| L1–L4 · TH1–TH3 | Cấp tư cách · loại chỗ đỗ | PRD §3.2, §4 |
| BR-xx · FR-xx | Quy tắc nghiệp vụ · yêu cầu chức năng | PRD §5, §6 |
| A-xx | Giả định cần xác nhận | Scope §4 |
| US-xx · AC-xx | User story · tiêu chí nghiệm thu | 04-user-stories |
| M1–M14 · W0–W7 · N1–N9 | Module · workflow Agent · job nền | 05 Backlog, ADR-0010 |
