# User Flow — Agent điều phối quyền sử dụng chỗ đỗ trong chuỗi khu đô thị

> **File này trả lời:** yêu cầu, chia sẻ, ngoại lệ, tranh chấp, log LPR đi qua những bước nào; chỗ nào BQL phải duyệt.
> Liên quan: [User Stories](../04-user-stories.md) · [PRD](../02-prd.md) · [Wireframes](wireframes/README.md) (hành trình J1–J5) · [Backlog](../05-backlog.md)

Agent điều phối các nhánh; worker nền chỉ phát hiện và chuẩn bị dữ liệu. Nhãn *(Ưu tiên N)* theo backlog; flow không ghi nhãn là Ưu tiên 1.

## Flow 0 — Tư cách tại vị trí chỗ đỗ (US-19 → US-22)

Yêu cầu tại tòa T, khu K, lấy tư cách còn hiệu lực: tài sản trong T → **L1** · tài sản khác trong K → **L2** ·
tư cách ở khu khác (chỉ nhận kết quả xác nhận) → **L3** · không có → **L4** khách. Sang Flow 1.

## Flow 1 — Định tuyến (US-01 → US-03, US-25)

Pool TH1/TH2 trong K có phạm vi mở chứa cấp này?

- **Có** → tìm ô trống, vừa kích thước xe, đúng giờ và dự phòng: có ô → Flow 2; không có → vào hàng chờ tòa (BR-21), hoặc
  TH3 của K theo giá cấp; TH3 hết → bãi công cộng. Người ở TH3 được ưu tiên nếu liên quan khu đô thị (BR-28); khi còn ít chỗ, bảo vệ chặn khách vãng lai.
- **Không** → **chuyển** TH3 / bãi công cộng của K, giá theo cấp. Không phải vi phạm.

**Chặn** (ghi KPI) chỉ khi vi phạm rõ ràng: tư cách hết hạn, chia sẻ ngoài phạm vi hoặc chia sẻ TH3, ngoài nền tảng, cư dân thu phí khách
([PRD §5](../02-prd.md#5-quy-tắc-nghiệp-vụ), AC-03).

## Flow 2 — Chia sẻ chỗ (US-04 → US-08)

1. Chủ chỗ chọn khung giờ (hệ thống thêm dự phòng theo nội quy khu). *(Ưu tiên 3: đề xuất từ dự báo N4, thu hẹp phạm vi.)*
2. Agent ghép cung với cầu (giờ, kích thước, phạm vi) và gửi thỏa thuận theo mẫu khu cho hai bên.
3. Chủ nhập OTP xác nhận cho thuê **với hệ thống** lúc đăng (BR-25). Duyệt 2 lớp (BR-26): rule engine chốt; AI chỉ siết. BQL chỉ xem ca xấu (vùng xám / đáng ngờ), tối đa 10 phút.
4. Người thuê được gán khi ETA ≤ 30 phút (hoặc bấm "Tôi đang đến"), nhập OTP nhận chỗ trong 3 phút (BR-22). Lưu bằng chứng; ghi khoản vào sổ (không thanh toán QR).

**Pilot một tòa** ([07 Pilot](../07-pilot-mot-toa.md)): chỗ chỉ trống khi chủ đã đăng, đã nhập OTP **và** xe chủ đã ra; tin quá 30 phút chưa ra thì hết hạn.
Người thuê vào hàng chờ, chỗ trống trước ghép trước; GPS 15 phút/lần để tính ETA (BR-27); ETA > 30 phút thì chưa gán, vẫn thấy số chỗ còn lại (BR-29).
Không nhập OTP nhận chỗ: chuyển người kế tiếp, không mất tiền. Đã nhập OTP nhưng không tới trong thời hạn giữ: phí không tới 30% (BR-22).

## Flow 3 — Ngoại lệ (US-09 → US-11)

- *(Ưu tiên 2)* **Chủ về sớm** (nút trên app, vị trí một lần → ETA) → báo người thuê → dời? Có → đổi lượt, chủ về đúng ô;
  không / không trả lời → người thuê ở lại tới hết giờ, chủ đỗ ô dự phòng; hết ô → BQL, tòa tạm ngừng nhận lượt (BR-07, BR-24).
- *(Ưu tiên 2)* **Quá giờ** (US-11): N2 nhắc người thuê 2 lần (trước giờ kết thúc 20 phút; đúng lúc hết giờ, nêu 10 phút cho phép và mức phí) → xe ra (log cổng) → vượt 10 phút thì tính phí từ giờ kết thúc, mỗi 15 phút bắt đầu, 50 000 đ/giờ (mặc định, BQL xác nhận); quá giờ mà xe chưa ra → báo bảo vệ → người thuê trả, tiền về chủ chỗ hoặc về khu (TH3). Miễn phí chỉ qua khiếu nại.

## Flow 4 — Tranh chấp (Ưu tiên 2)

- **Tranh chấp** (US-12, US-13): cư dân báo kèm ảnh tại ô → hồ sơ thuộc khu có ô, chuyển BQL khu đó (BR-18) → W5 gom bằng chứng (ảnh, thỏa thuận và bằng chứng xác nhận, log cổng, phí quá giờ) → model đọc ảnh đã che biển số, xe xác định bằng log cổng và biển số đã băm → tóm tắt "Gợi ý" → BQL quyết định: giữ nguyên, bác, miễn phí quá giờ, khác.

## Flow 5 — Hoán đổi (Ưu tiên 3)

- **Hoán đổi** (US-14, US-15): tranh chấp lặp lại hoặc nhu cầu đã đăng ký → đề xuất 2 bên / nhiều bên theo vòng, cùng khu → BQL duyệt
  thì có hiệu lực, từ chối thì giữ nguyên.

## Flow 6 — Nạp log LPR (N1)

CSV mô phỏng của từng khu → worker chuẩn hóa, gắn khu nguồn → mã sự kiện đã có? Có → bỏ qua (trùng). Không → lưu `lpr_event`;
khớp booking đang hiệu lực → ghi giờ vào / ra. *(Ưu tiên 3: webhook / MQTT, hàng chờ OCR thấp, LPR tự kích hoạt W5 tranh chấp.)*

Thông tin nhận dạng được ẩn danh trước khi gửi LLM. OCR không chắc chắn cần người kiểm tra; Agent không tự phán quyết tranh chấp.
