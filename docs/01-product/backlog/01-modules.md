# Backlog — Module (FE / BE)

> **File này trả lời:** mỗi module (M1–M14) làm gì, và tính năng nào thuộc ưu tiên nào trong 4 tuần.
> Liên quan: [README](README.md) · [Workflow AI Agent](02-agent-workflows.md) · [Workflow nền](03-background-workflows.md) · [PRD §3 tư cách](../02-prd.md#3-đối-tượng-người-dùng-và-tư-cách) · [Tech stack](../../02-architecture/02-tech-stack.md)
> Ảnh: [ParkSmartAI-modules.png](../../images/ParkSmartAI-modules.png) (14 module, vẽ lại 2026-11-18; chưa cập nhật theo phân bổ ưu tiên mới).

![ParkSmart AI — 14 module](../../images/ParkSmartAI-modules.png)

Mỗi module gồm cả **FE** (React + Vite SPA) và **BE** (FastAPI + LangGraph, rule engine, PostgreSQL trên RDS). Định nghĩa mức ưu tiên: [README §1](README.md#1-ba-mức-ưu-tiên).

## 1. Tóm tắt theo mức ưu tiên

| Module | Tính năng | Ưu tiên 1 | Ưu tiên 2 | Ưu tiên 3 |
|---|---|:---:|:---:|:---:|
| **M1 Tài khoản & tư cách** | Đăng nhập, đăng xuất (JWT tự cấp, [ADR-0006](../../10-adr/ADR-0006-self-issued-jwt-auth.md)) | ● |  |  |
|  | Seed tài khoản, 5 vai trò, bảng tư cách *(tài sản, vai trò, hạn)* cho các khu | ● |  |  |
|  | Tính cấp L1–L4 tại một ô, kiểm tra hạn khi xử lý yêu cầu | ● |  |  |
|  | RLS theo khu và hộ | ● |  |  |
|  | Đăng ký + đồng ý xử lý dữ liệu |  | ● |  |
|  | Hồ sơ, xem tư cách của mình |  | ● |  |
|  | API xác nhận liên khu chỉ trả cấp và hạn |  | ● |  |
|  | Quên mật khẩu; rút lại đồng ý |  |  | ● |
|  | BQL xem, duyệt, thu hồi tư cách |  |  | ● |
|  | N6 quét tư cách hết hạn và thông báo |  |  | ● |
|  | Ủy quyền dùng tư cách; đồng bộ cư dân thật; eKYC |  |  | ● |
| **M2 Khu, tòa, xe, chỗ đỗ** | Seed Chuỗi → Khu → Phân khu → Tòa → Hầm → Ô | ● |  |  |
|  | Ô TH1/TH2/TH3, kích thước ô, chủ ô | ● |  |  |
|  | Xe của người dùng, mã hóa biển số khi lưu | ● |  |  |
|  | Thêm / sửa / xóa xe |  | ● |  |
|  | Danh sách ô và trạng thái |  | ● |  |
|  | Sơ đồ bãi realtime từ sự kiện LPR |  |  | ● |
|  | Sơ đồ bản vẽ, chỉ đường tới ô; ô sạc xe điện |  |  | ● |
| **M3 Nội quy & cấu hình** | Cấu hình bằng seed: khung giá theo cấp, khoảng dự phòng, ngưỡng BQL duyệt, **phạm vi mở của từng pool** | ● |  |  |
|  | Rule engine: cấp × phạm vi mở, chặn sai tư cách / sai phạm vi, tính phí | ● |  |  |
|  | Mẫu thỏa thuận | ● |  |  |
|  | Hỏi đáp nội quy W7 (RAG lọc theo khu / tòa) |  | ● |  |
|  | BQL chỉnh nội quy khu mình, lịch sử thay đổi |  |  | ● |
|  | Mở TH1 ra cả khu (sau khi A-08 được xác nhận pháp lý) |  |  | ● |
|  | Khung giá giờ cao điểm |  |  | ● |
| **M4 Chia sẻ chỗ** | Tạo / hủy lịch chia sẻ kèm khoảng dự phòng | ● |  |  |
|  | Chặn chia sẻ TH3 | ● |  |  |
|  | Ghép cung–cầu theo giờ, kích thước, phạm vi mở | ● |  |  |
|  | Nút "Tôi về sớm" |  | ● |  |
|  | Sửa lịch chia sẻ |  | ● |  |
|  | Chủ chỗ **thu hẹp phạm vi chia sẻ** (không vượt nội quy) |  | ● |  |
|  | Dự báo giờ trống, đề xuất khung giờ (N4) |  |  | ● |
|  | Thu nhập, lịch sử chia sẻ |  |  | ● |
|  | Lặp lịch hằng tuần; nháp lịch từ dự báo |  |  | ● |
| **M5 Đặt chỗ** | Gửi yêu cầu qua chat (W1) | ● |  |  |
|  | Định tuyến theo cấp, giữ chỗ tạm | ● |  |  |
|  | Kết quả ghép / chuyển TH3 / bãi công cộng / chặn kèm lý do | ● |  |  |
|  | Form đặt chỗ |  | ● |  |
|  | Lượt đỗ hiện tại; lịch sử, hủy đặt chỗ |  | ● |  |
|  | Gợi ý ô ở khu khác đủ điều kiện (FR-27), giá L3 |  | ● |  |
|  | Đặt chỗ định kỳ, giữ chỗ liên khu |  |  | ● |
| **M6 Thỏa thuận & sổ cái** | Sinh thỏa thuận theo mẫu của khu có ô | ● |  |  |
|  | Hai bên xác nhận OTP có thời hạn | ● |  |  |
|  | Sổ cái append-only, chuỗi hash | ● |  |  |
|  | Xem sổ cái, kiểm tra toàn vẹn |  | ● |  |
|  | Thỏa thuận bị từ chối / hết hạn chờ |  | ● |  |
|  | Xuất dữ liệu; chữ ký số |  |  | ● |
| **M7 Thanh toán & voucher** | Tính phí chia sẻ theo cấp tư cách | ● |  |  |
|  | VietQR mock, trạng thái thanh toán | ● |  |  |
|  | Voucher shophouse (chỉ lượt TH3) |  |  | ● |
|  | Phí quá giờ; lịch sử giao dịch |  |  | ● |
|  | Thanh toán thật (VietQR thật, MoMo, ZaloPay); đối soát tiền; chia doanh thu |  |  | ● |
| **M8 LPR & ra vào** | N1 cơ bản: nạp CSV mô phỏng, chuẩn hóa, bỏ log trùng mã, gắn khu nguồn |  | ● |  |
|  | Bộ log mô phỏng (ngày thường, cuối tuần, Tết) cho các khu |  | ● |  |
|  | Webhook / MQTT; so khớp mờ biển số |  |  | ● |
|  | Hàng chờ OCR thấp; dòng thời gian ra vào |  |  | ● |
|  | Kích hoạt W3 / W4 / W5 |  |  | ● |
|  | Tích hợp LPR thật |  |  | ● |
| **M9 Ngoại lệ** | W3 từ app: cấp ô TH3 thay thế cùng khu |  | ● |  |
|  | Phát hiện về sớm từ LPR |  |  | ● |
|  | W4 quá giờ: nhắc nhiều lần, tính phí, thông báo phí |  |  | ● |
|  | TH3 hết chỗ → gợi ý khu lân cận |  |  | ● |
|  | Bù chi phí khi chủ về sớm (TBD) |  |  | ● |
| **M10 Tranh chấp** | Báo tranh chấp kèm ảnh (W5) |  |  | ● |
|  | Ticket chuyển BQL khu có ô, biển số đã ẩn |  |  | ● |
|  | Danh sách, chi tiết; BQL xác minh, đóng ticket |  |  | ● |
|  | Xem biển số gốc: nhập lý do, ghi log |  |  | ● |
|  | Khiếu nại lại; thống kê theo khu |  |  | ● |
| **M11 Hoán đổi** | Đăng ký nhu cầu đổi chỗ |  |  | ● |
|  | W6 hoán đổi **2 bên** cùng khu; N5 phát hiện tranh chấp lặp |  |  | ● |
|  | BQL duyệt / từ chối; cư dân xem trạng thái |  |  | ● |
|  | Hoán đổi **theo chuỗi**; LLM giải thích lý do |  |  | ● |
| **M12 Dashboard** | Hàng chờ HITL theo khu: BQL duyệt / từ chối giao dịch vượt ngưỡng; resume graph | ● |  |  |
|  | KPI cơ bản theo khu (yêu cầu, ghép, bị chặn sai tư cách / phạm vi) |  | ● |  |
|  | Đối soát cuối ngày (N3); tình trạng nguồn LPR |  |  | ● |
|  | Hàng chờ ticket và hoán đổi |  |  | ● |
|  | Dashboard toàn chuỗi; so sánh cung–cầu (N7, N8) |  |  | ● |
| **M13 Thông báo** | Thông báo trong app: kết quả ghép, chờ xác nhận thỏa thuận, việc chờ duyệt | ● |  |  |
|  | Realtime qua WebSocket `/ws` ([ADR-0003](../../10-adr/ADR-0003-rest-openapi-sse-websocket-single-domain.md)); đánh dấu đã đọc |  | ● |  |
|  | Thông báo chỗ thay thế |  | ● |  |
|  | Nhắc quá giờ; tư cách sắp / đã hết hạn |  |  | ● |
|  | Push, Zalo, SMS |  |  | ● |
| **M14 AI Agent Chat** | Chat trả lời stream (SSE) | ● |  |  |
|  | W0 Supervisor: guardrail, mã giả tên / biển số, phân loại ý định | ● |  |  |
|  | Checkpointer dừng chờ BQL duyệt rồi chạy tiếp | ● |  |  |
|  | Eval ≥45 case + trace (bắt buộc cho Demo Day) |  | ● |  |
|  | Trích dẫn nguồn |  | ● |  |
|  | Bộ nhớ hội thoại |  |  | ● |
|  | Nhập bằng giọng nói; đa ngôn ngữ |  |  | ● |

● = tính năng thuộc mức này. Ưu tiên 1 = bắt buộc (tuần 1–2) · Ưu tiên 2 = xong trước demo (tuần 3–4) · Ưu tiên 3 = chưa cần cho demo.

## 2. Nội dung từng module

Thư mục BE theo [ADR-0010](../../10-adr/ADR-0010-backend-modules-agent-workflows-jobs.md), dưới `server/src/app/`.

| Module | Nhóm | Nội dung | Thư mục BE |
|--------|------|----------|------------|
| **M1** Tài khoản & tư cách | Nền móng | Quản lý tài khoản, vai trò và **tư cách** của người dùng (tài sản nào, ở khu nào, vai trò gì, hạn đến khi nào). Từ đó tính cấp L1–L4 tại một ô; là nguồn duy nhất trả lời "người này có quyền gì ở đây". | `identity/`, `eligibility/` |
| **M2** Khu, tòa, xe, chỗ đỗ | Nền móng | Dữ liệu vật lý: cây Chuỗi → Khu → Phân khu → Tòa → Hầm → Ô, loại ô, kích thước, chủ ô, và xe của người dùng. | `facility/` |
| **M3** Nội quy & cấu hình | Nền móng | Nội quy từng khu / tòa dưới dạng cấu hình, và **rule engine** tất định quyết định quyền thuê và phí. Thêm RAG để hỏi đáp nội quy. | `policy/`, `knowledge/` |
| **M4** Chia sẻ chỗ | Luồng chính | Phía cung: chủ chỗ đăng khung giờ chỗ đang trống, có khoảng dự phòng để không mất chỗ khi về. | `sharing/` |
| **M5** Đặt chỗ | Luồng chính | Phía cầu: người cần chỗ gửi yêu cầu; hệ thống định tuyến theo cấp tư cách sang TH1/TH2, TH3 hoặc bãi công cộng, rồi giữ chỗ. | `booking/` |
| **M6** Thỏa thuận & sổ cái | Luồng chính | Biến một lượt ghép thành thỏa thuận điện tử hai bên xác nhận, rồi ghi vào sổ cái chỉ-ghi-thêm có chuỗi hash làm bằng chứng. | `ledger/` |
| **M7** Thanh toán & voucher | Luồng chính | Tính phí theo cấp và nội quy, thanh toán VietQR mô phỏng; voucher shophouse cho khách lượt TH3. | `payment/` |
| **M8** LPR & ra vào | Vận hành | Nhận và làm sạch log camera biển số (LPR) của từng khu; nguồn sự kiện ra / vào cho các workflow khác. | `access/` |
| **M9** Ngoại lệ | Vận hành | Xử lý khi lượt đỗ không diễn ra như thỏa thuận: chủ về sớm (W3), người thuê quá giờ (W4). | TBD (W3, W4 nằm trong `agent/`) |
| **M10** Tranh chấp | Vận hành | Nhận báo cáo tranh chấp, gom bằng chứng (ảnh, sổ cái, log cổng), lập ticket ẩn biển số cho BQL khu có ô. | `dispute/` |
| **M11** Hoán đổi | Vận hành | Đề xuất đổi chỗ giữa các chủ chỗ cùng khu khi chỗ không hợp nhu cầu hoặc tranh chấp lặp lại; BQL duyệt trước khi áp dụng. | `swap/` |
| **M12** Dashboard | Quản trị | Màn hình của BQL: hàng chờ duyệt (HITL), KPI, đối soát, tình trạng nguồn LPR. | `approval/`, `reporting/` |
| **M13** Thông báo | Quản trị | Thông báo trong app cho mọi sự kiện người dùng cần biết hoặc xác nhận. | `notification/` |
| **M14** AI Agent Chat | Nền móng | Cửa vào bằng chat: Agent hiểu yêu cầu, gọi đúng workflow, ẩn danh dữ liệu trước khi gửi LLM. LLM chỉ gợi ý; quyết định do rule engine. | `agent/` |
