# User Flow — Agent điều phối quyền sử dụng chỗ đỗ trong chuỗi khu đô thị

> File này trả lời: một yêu cầu, chia sẻ, ngoại lệ, tranh chấp hay log LPR đi qua những bước nào, và chỗ nào BQL phải duyệt.
> Nguồn: [Bài toán](../00-xac-dinh-bai-toan.md) · Liên quan: [User Stories & AC](../04-user-stories.md) · [PRD](../02-prd.md)
> Wireframes: [index.html](wireframes/index.html) (chưa cập nhật cho bối cảnh nhiều khu) · [README wireframes](wireframes/README.md) · UI design: [ui-design/](ui-design/) (chưa có)

Luồng của bản demo (1 chuỗi, N khu). Agent điều phối các nhánh; worker nền nạp log LPR, phát hiện quá giờ, đối soát cuối ngày, dự báo và quét tư cách hết hạn, rồi kích hoạt workflow Agent khi cần hành động. Màn hình: [wireframes](wireframes/README.md) (hành trình J1–J8).

## Flow 0 — Xác định tư cách tại vị trí chỗ đỗ (US-19 → US-22)

Yêu cầu tại tòa T, khu K → lấy tư cách còn hiệu lực trong chuỗi:

1. Có tư cách gắn tài sản trong T? → **L1** Thành viên tòa.
2. Không: có tư cách gắn tài sản khác trong K? → **L2** Thành viên khu.
3. Không: có tư cách ở khu khác trong chuỗi? → **L3** Thành viên chuỗi (chỉ nhận kết quả xác nhận từ khu kia).
4. Không → **L4** Khách.

L1–L4 → Flow 1.

## Flow 1 — Định tuyến yêu cầu chỗ đỗ (US-01 → US-03, US-25)

Cấp từ Flow 0 → pool TH1/TH2 trong K có phạm vi mở chứa cấp này?

- **Có** → tìm ô TH1/TH2 trống, vừa kích thước xe, đúng khung giờ và dự phòng:
  - Có ô → Flow 2.
  - Không có ô → TH3 của K theo giá cấp; hết TH3 → gợi ý ô khu khác trong chuỗi (Ưu tiên 2, người dùng tự chọn) hoặc bãi công cộng.
- **Không** → **chuyển** TH3 / bãi công cộng của K, giá theo cấp. Đây không phải vi phạm.

**Chặn** (ghi KPI "sai tư cách / sai phạm vi") chỉ khi có vi phạm rõ ràng: yêu cầu dựa trên tư cách đã hết hạn, chủ chỗ chia sẻ ngoài phạm vi hoặc chia sẻ TH3, giao dịch ngoài nền tảng, cư dân thu phí khách ([PRD §5](../02-prd.md#5-quy-tắc-nghiệp-vụ), AC-03).

## Flow 2 — Chia sẻ chỗ (US-04 → US-08, US-23)

Tác nhân: Chủ chỗ, Agent, Người thuê, BQL khu có ô đỗ.

1. *(Ưu tiên 3)* Agent đề xuất khung giờ chia sẻ từ dự báo N4. Ở demo, Chủ chỗ tự chọn.
2. Chủ chỗ chọn khung giờ (hệ thống thêm khoảng dự phòng theo nội quy khu) và phạm vi (≤ mức nội quy cho phép).
3. Agent ghép cung với cầu (khung giờ, kích thước, phạm vi).
4. Agent gửi thỏa thuận điện tử theo mẫu của khu cho Chủ chỗ và Người thuê.
5. Hai bên xác nhận.
6. Vượt ngưỡng cần duyệt của khu? → có: gửi HITL cho BQL → BQL **duyệt / từ chối**.
7. Ghi giao dịch có hiệu lực vào sổ cái và ghi nhận cho BQL.

## Flow 3 — Xử lý ngoại lệ (US-09 → US-11)

- **Chủ về sớm** → Chủ quay về chỗ → pool TH3 cùng khu còn chỗ?
  - Có → điều phối người thuê sang TH3 cùng khu.
  - Không → gợi ý chỗ khu lân cận trong chuỗi.
- **Người thuê đỗ quá giờ** → Agent nhắc người thuê → tính phí theo nội quy khu.

## Flow 4 — Tranh chấp (US-12, US-13)

Phát sinh tranh chấp (kênh báo: TBD) → Agent đọc ảnh → đối chiếu sổ cái và dữ liệu cổng của khu → lập ticket (biển số ẩn) → BQL khu có ô xác minh → kết quả: TBD.

## Flow 5 — Hoán đổi (US-14, US-15)

Tranh chấp lặp lại hoặc nhu cầu đã đăng ký → Agent đề xuất hoán đổi (2 bên hoặc nhiều bên theo vòng, cùng khu) → BQL khu phê duyệt?

- **Có** → hoán đổi có hiệu lực.
- **Không** → giữ nguyên phân bổ.

## Flow 6 — Nạp và xử lý log LPR

Webhook / MQTT / DB / CSV của từng khu hoặc log demo → worker chuẩn hóa, gắn khu nguồn → mã sự kiện đã xử lý?

- **Có** → bỏ qua sự kiện trùng.
- **Không** → OCR đạt ngưỡng tin cậy?
  - Không → hàng chờ người kiểm tra.
  - Có → đối chiếu lịch chia sẻ và sổ cái → quá giờ hay dấu hiệu tranh chấp?
    - Quá giờ → kích hoạt W4: Agent nhắc người thuê, tính phí theo nội quy.
    - Tranh chấp → kích hoạt W5: Agent lập ticket ẩn danh.
    - Không → cập nhật trạng thái chỗ.

Thông tin nhận dạng được ẩn danh trước khi gửi ngữ cảnh tới LLM. Log OCR không chắc chắn cần người kiểm tra; Agent không tự phán quyết tranh chấp.
