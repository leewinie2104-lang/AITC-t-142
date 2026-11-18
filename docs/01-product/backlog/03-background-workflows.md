# Backlog — Workflow nền

> **File này trả lời:** mỗi workflow nền (N1–N8) làm gì, chạy khi nào, tạo ra gì, và phần nào thuộc ưu tiên nào trong 4 tuần.
> Liên quan: [README](README.md) · [Module](01-modules.md) · [Workflow AI Agent](02-agent-workflows.md)
> Ảnh: [ParkSmartAI-background-workflows.png](../../images/ParkSmartAI-background-workflows.png) (N1–N8; vẽ lại 2026-11-18; chưa cập nhật theo phân bổ ưu tiên mới).

![ParkSmart AI — Workflow nền](../../images/ParkSmartAI-background-workflows.png)

**Nguyên tắc:**
- Chạy bằng worker arq + Redis; không đi qua Agent, không gọi LLM.
- Chỉ phát hiện và chuẩn bị dữ liệu. Job được gửi thẳng **thông báo thuần thông tin** qua M13 (ví dụ N3, N6). Mọi hành động đổi quyền hoặc tiền của người dùng (nhắc quá giờ, tính phí, ticket, hoán đổi) đi qua workflow Agent tương ứng.
- Mọi job chạy **riêng cho từng khu** và gắn khu nguồn. Riêng N7 và N8 đọc số liệu đã tổng hợp của nhiều khu.

## 1. Tóm tắt theo mức ưu tiên

| Workflow | Phần việc | Ưu tiên 1 | Ưu tiên 2 | Ưu tiên 3 |
|---|---|:---:|:---:|:---:|
| **N1 Xử lý log LPR** | Bản cơ bản: nạp CSV / log mô phỏng theo khu, chuẩn hóa, gắn khu nguồn |  | ● |  |
|  | Bỏ log trùng mã; đối chiếu lịch chia sẻ; cập nhật lượt đỗ |  | ● |  |
|  | Webhook / MQTT; so khớp mờ biển số |  |  | ● |
|  | OCR thấp → hàng chờ kiểm tra |  |  | ● |
|  | Kích hoạt W3 / W4 / W5 |  |  | ● |
|  | Nhận log từ LPR thật |  |  | ● |
| **N2 Kiểm tra quá giờ** | Quét lượt đỗ hết giờ, trừ khoảng trễ (TBD), kích hoạt W4 |  |  | ● |
| **N3 Đối soát cuối ngày** | So lịch, log ra vào và sổ cái; báo cáo theo khu cho BQL |  |  | ● |
| **N4 Dự báo khung giờ trống** | Dự báo theo giờ, thứ, ngày lễ của từng khu, dùng cho W2 |  |  | ● |
|  | Mô hình tốt hơn (thời tiết, sự kiện, lịch trường học) |  |  | ● |
| **N5 Phát hiện tranh chấp lặp** | Đếm tranh chấp theo ô / cặp người dùng, vượt ngưỡng (TBD) → W6 |  |  | ● |
| **N6 Quét tư cách hết hạn *(mới)*** | Quét tư cách đã / sắp hết hạn, đánh dấu, thông báo (chặn giao dịch mới đã có trong W1) |  |  | ● |
| **N7 Tổng hợp KPI toàn chuỗi *(mới)*** | Gom KPI đã tổng hợp của các khu cho dashboard chuỗi |  |  | ● |
| **N8 Cân bằng cung–cầu liên khu *(mới)*** | Gợi ý cho BQL / đơn vị vận hành khi khu này thiếu, khu lân cận dư |  |  | ● |

● = tính năng thuộc mức này. Ưu tiên 1 = bắt buộc (tuần 1–2) · Ưu tiên 2 = xong trước demo (tuần 3–4) · Ưu tiên 3 = chưa cần cho demo.

## 2. Nội dung từng workflow

Mỗi workflow: mục đích, khi nào chạy, đầu ra, module sở hữu job (theo [ADR-0010](../../10-adr/ADR-0010-backend-modules-agent-workflows-jobs.md)) và chuỗi bước.

### N1 — Xử lý log LPR
Biến log thô của camera biển số thành sự kiện ra / vào sạch, gắn đúng khu, để cập nhật lượt đỗ và kích hoạt các workflow Agent.
- **Kích hoạt:** sự kiện LPR · **Đầu ra:** trạng thái lượt đỗ; kích hoạt W3 / W4 / W5 · **Module:** M8 (`access/`)

`Nhận log từ CSV / bộ log mô phỏng (ngày thường, cuối tuần, Tết) theo khu → Chuẩn hóa sự kiện, gắn khu nguồn → Bỏ log trùng mã sự kiện → Đối chiếu với lịch chia sẻ → Cập nhật trạng thái lượt đỗ`

### N2 — Kiểm tra quá giờ
Phát hiện lượt đỗ đã quá khung giờ thỏa thuận để W4 nhắc và tính phí.
- **Kích hoạt:** định kỳ (chu kỳ TBD) · **Đầu ra:** kích hoạt W4 · **Module:** M8 (`access/`)

`Quét lượt đỗ đã hết giờ → Trừ khoảng cho phép trễ (TBD) → Kích hoạt W4`

### N3 — Đối soát cuối ngày
Kiểm tra cuối ngày xem lịch chia sẻ, ra vào thực tế và sổ cái có khớp nhau không.
- **Kích hoạt:** hằng ngày · **Đầu ra:** báo cáo gửi BQL khu (M12) · **Module:** M12 (`reporting/`)

`So lịch chia sẻ với log ra vào → Đối chiếu sổ cái → Lập báo cáo theo khu → Gửi BQL khu (M12)`

### N4 — Dự báo khung giờ trống
Dự đoán khi nào chỗ của chủ chỗ thường trống, để W2 đề xuất khung giờ chia sẻ. Kết quả chỉ để gợi ý, không tự đăng lịch.
- **Kích hoạt:** hằng đêm · **Đầu ra:** dự báo dùng cho W2 · **Module:** M4 (`sharing/`)

`Gom lịch sử ra vào theo giờ, thứ, ngày lễ (theo khu) → Tính dự báo → Lưu kết quả → Dùng cho W2`

### N5 — Phát hiện tranh chấp lặp lại
Tìm ô hoặc cặp người dùng hay tranh chấp với nhau để W6 đề xuất hoán đổi.
- **Kích hoạt:** định kỳ (chu kỳ TBD) · **Đầu ra:** kích hoạt W6 · **Module:** M10 (`dispute/`)

`Đếm tranh chấp theo ô / cặp người dùng trong khu → Vượt ngưỡng (TBD) → Kích hoạt W6`

### N6 — Quét tư cách hết hạn *(mới)*
Dọn trạng thái tư cách đã hết hạn và báo cho người liên quan. Việc chặn giao dịch mới không phụ thuộc N6: rule engine đã kiểm tra hạn ngay trong W1.
- **Kích hoạt:** hằng ngày · **Đầu ra:** vô hiệu tư cách; thông báo (M13) · **Module:** M1 (`eligibility/`)

`Quét tư cách đã hết hiệu lực (và tư cách sắp hết hạn) → Đánh dấu hết hiệu lực → Tìm giao dịch đang hiệu lực dựa trên các tư cách đó, giữ tới hết kỳ (BR-16) → Gửi thông báo cho người dùng và chủ chỗ liên quan (M13)`

### N7 — Tổng hợp KPI toàn chuỗi *(mới)*
Cho đơn vị vận hành chuỗi một bức tranh chung, chỉ từ số liệu đã tổng hợp của từng khu.
- **Kích hoạt:** hằng ngày · **Đầu ra:** dashboard chuỗi (M12) · **Module:** M12 (`reporting/`)

`Gom KPI đã tổng hợp của từng khu (không gom dữ liệu cá nhân) → Dashboard cho đơn vị vận hành chuỗi`

### N8 — Cân bằng cung–cầu liên khu *(mới)*
Phát hiện lệch cung–cầu giữa các khu theo giờ (P8) và gợi ý cách điều phối. Chỉ là gợi ý, không tự đổi cấu hình.
- **Kích hoạt:** hằng đêm · **Đầu ra:** gợi ý cho BQL / đơn vị vận hành · **Module:** M12 (`reporting/`)

`Từ dự báo N4 của các khu, tìm khung giờ khu này thiếu chỗ còn khu lân cận dư chỗ → Gợi ý cho BQL / đơn vị vận hành (ví dụ mở pool TH2 cho cả chuỗi trong khung giờ đó)`
