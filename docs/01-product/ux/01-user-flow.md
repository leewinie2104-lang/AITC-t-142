# User Flow — Agent điều phối quyền sử dụng chỗ đỗ trong chuỗi khu đô thị

> **File này trả lời:** yêu cầu, chia sẻ, ngoại lệ, tranh chấp, log LPR đi qua những bước nào; chỗ nào BQL phải duyệt.
> Liên quan: [User Stories](../04-user-stories.md) · [PRD](../02-prd.md) · [Wireframes](wireframes/README.md) (hành trình J1–J5) · [Backlog](../backlog/README.md)

Agent điều phối các nhánh; worker nền chỉ phát hiện và chuẩn bị dữ liệu. Nhãn *(Ưu tiên N)* theo backlog; flow không ghi nhãn là Ưu tiên 1.

## Flow 0 — Tư cách tại vị trí chỗ đỗ (US-19 → US-22)

Yêu cầu tại tòa T, khu K, lấy tư cách còn hiệu lực: tài sản trong T → **L1** · tài sản khác trong K → **L2** ·
tư cách ở khu khác (chỉ nhận kết quả xác nhận) → **L3** · không có → **L4** khách. Sang Flow 1.

## Flow 1 — Định tuyến (US-01 → US-03, US-25)

Pool TH1/TH2 trong K có phạm vi mở chứa cấp này?

- **Có** → tìm ô trống, vừa kích thước xe, đúng giờ và dự phòng: có ô → Flow 2; không có → TH3 của K theo giá cấp;
  hết TH3 → bãi công cộng, hoặc *(Ưu tiên 2)* gợi ý ô khu khác, người dùng tự chọn.
- **Không** → **chuyển** TH3 / bãi công cộng của K, giá theo cấp. Không phải vi phạm.

**Chặn** (ghi KPI) chỉ khi vi phạm rõ ràng: tư cách hết hạn, chia sẻ ngoài phạm vi hoặc chia sẻ TH3, ngoài nền tảng, cư dân thu phí khách
([PRD §5](../02-prd.md#5-quy-tắc-nghiệp-vụ), AC-03).

## Flow 2 — Chia sẻ chỗ (US-04 → US-08)

1. Chủ chỗ chọn khung giờ (hệ thống thêm dự phòng theo nội quy khu). *(Ưu tiên 3: đề xuất từ dự báo N4, thu hẹp phạm vi.)*
2. Agent ghép cung với cầu (giờ, kích thước, phạm vi) và gửi thỏa thuận theo mẫu khu cho hai bên.
3. Hai bên xác nhận OTP. Vượt ngưỡng của khu → HITL: BQL khu có ô **duyệt / từ chối**.
4. Lưu bằng chứng xác nhận; BQL khu có ô xem được. *(Ưu tiên 2: thanh toán VietQR mock.)*

## Flow 3 — Ngoại lệ (US-09 → US-11)

- *(Ưu tiên 2)* **Chủ về sớm** (nút trên app) → chủ quay về chỗ → TH3 cùng khu còn chỗ? Có → chuyển người thuê sang TH3;
  không → BQL khu xử lý *(Ưu tiên 3: gợi ý khu lân cận)*.
- *(Ưu tiên 3)* **Quá giờ** → Agent nhắc người thuê, tính phí theo nội quy khu.

## Flow 4–5 — Tranh chấp và hoán đổi (Ưu tiên 3)

- **Tranh chấp** (US-12, US-13): Agent đọc ảnh → đối chiếu bằng chứng xác nhận và dữ liệu cổng → ticket biển số ẩn → BQL khu có ô xác minh.
- **Hoán đổi** (US-14, US-15): tranh chấp lặp lại hoặc nhu cầu đã đăng ký → đề xuất 2 bên / nhiều bên theo vòng, cùng khu → BQL duyệt
  thì có hiệu lực, từ chối thì giữ nguyên.

## Flow 6 — Nạp log LPR (N1)

CSV mô phỏng của từng khu → worker chuẩn hóa, gắn khu nguồn → mã sự kiện đã có? Có → bỏ qua (trùng). Không → lưu `lpr_event`;
khớp booking đang hiệu lực → ghi giờ vào / ra. *(Ưu tiên 3: webhook / MQTT, hàng chờ OCR thấp, kích hoạt W4 quá giờ / W5 tranh chấp.)*

Thông tin nhận dạng được ẩn danh trước khi gửi LLM. OCR không chắc chắn cần người kiểm tra; Agent không tự phán quyết tranh chấp.
