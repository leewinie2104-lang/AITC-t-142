# Scope — Agent điều phối quyền sử dụng chỗ đỗ trong chuỗi khu đô thị

> **File này trả lời:** bản demo làm gì, không làm gì, xử lý dữ liệu thế nào, giả định nào cần xác nhận?
> Nguồn: [Bài toán](00-xac-dinh-bai-toan.md) · [Brief](01-project-brief.md) · [PRD](02-prd.md) · Việc theo tuần: [Backlog](05-backlog.md)

## 1. Trong phạm vi bản demo

**Ưu tiên số 1: pilot một tòa** theo [07 Pilot một tòa](07-pilot-mot-toa.md): chỗ trống khi chủ đã đăng và xe chủ đã ra, hàng chờ
người thuê (ETA từ GPS mỗi 15 phút), Agent đề xuất ghép (rule engine chốt), giữ chỗ theo ETA với OTP nhận chỗ, OTP chủ cho
thuê, duyệt 2 lớp (BQL chỉ ca xấu), ưu tiên TH3 cho người liên quan khu, báo số chỗ còn lại, hủy và hoàn theo nội quy, quá giờ
báo bảo vệ, chủ về sớm theo ETA với ưu tiên người thuê. Tính năng ngoài use case này làm sau. Phần chuỗi nhiều khu bên dưới giữ
làm thiết kế.

**1 chuỗi, N ≥ 2 khu.** Seed 3 khu, mỗi khu vài tòa (có khối đế), bãi công cộng, pool TH1/TH2/TH3 riêng; kịch bản chạy trên ≥ 2 khu:
- **A** khu ở + shophouse thấp tầng (chủ shophouse từ khu khác, trống ban ngày)
- **B** khu ở, trường, phòng khám (phụ huynh liên khu, cao điểm
đưa đón)
- **C** TTTM, văn phòng (trống ban đêm, cuối tuần, khách theo lượt). Cột *Mức* theo [Backlog §1](05-backlog.md#1-cách-đọc).
<blockquote style="border-left: 4px solid #22c55e; background: #f0fdf4; padding: 0.75em 1em; margin-left: 0; border-radius: 4px;">
  <strong style="color: #000;">CHỈ THAM KHẢO, CÒN SỬA ĐỔI</strong>
</blockquote>

| Hạng mục | Phạm vi | Mức |
|----------|---------|-----|
| Tư cách, liên khu | Một tài khoản, nhiều tư cách có hạn; cấp L1–L4 tại ô; phạm vi mở từng pool. Gợi ý khu khác khi hết chỗ | 1 · gợi ý: 2 |
| Định tuyến | Quyền thuê theo cấp và phạm vi mở; ghép TH1/TH2, hoặc TH3 / bãi công cộng theo giá cấp; TH3 ưu tiên người liên quan khu (BR-28) | 1 |
| Hàng chờ, ETA | Hàng chờ người thuê; đủ điều kiện gán khi ETA ≤ 30 phút (có kẹt xe); GPS mỗi 15 phút khi đang chờ; báo số chỗ còn lại (BR-21, BR-27, BR-29) | 1 · báo số chỗ: 2 |
| Chia sẻ, ghép | Lịch, dự phòng, ghép theo giờ, kích thước, phạm vi; thỏa thuận theo mẫu khu; OTP chủ cho thuê và OTP người thuê nhận chỗ (BR-25); bằng chứng xác nhận | 1 |
| Duyệt, đăng ký | Duyệt 2 lớp: rule engine, AI đánh giá rủi ro, BQL chỉ xem ca xấu (BR-26); đăng ký tự đối chiếu dữ liệu BQL có sẵn | 2 |
| Log LPR | Nạp CSV mô phỏng, chuẩn hóa, chống trùng (N1) | 1 |
| Khoản phí | Ghi nhận khoản (giá thuê, hoàn khi hủy, phí quá giờ) vào sổ; **không thanh toán QR** trong app | 1 |
| Ngoại lệ | Chủ về sớm (từ app, ETA mock) → người thuê chọn dời hay ở lại; ở lại thì chủ đỗ ô dự phòng; hết ô → BQL, tạm ngừng nhận lượt. Quá giờ: nhắc 2 lần, quá hạn báo bảo vệ, phí tính khi xe ra (N2, W4) | 2 |
| Tranh chấp | Cư dân báo kèm ảnh → BQL khu có ô; W5 gom bằng chứng, đọc ảnh đã che biển số, tóm tắt "Gợi ý"; BQL quyết định. Demo dùng ảnh che sẵn bằng tay | 2 |
| Thiết kế, chưa làm | Hoán đổi (2 bên / theo vòng, cùng khu), voucher, N3–N8; xem biển số gốc có ghi log, làm mờ ảnh tự động, so khớp mờ / OCR thấp | 3 |

Thao tác ảnh hưởng quyền sử dụng chỗ hoặc kết luận tranh chấp cần **BQL khu có ô đỗ** duyệt qua HITL.

## 2. Ngoài phạm vi bản demo

- Bãi riêng trường, bệnh viện, văn phòng độc lập, TTTM.
- Đặt chỗ / quản lý tồn chỗ bãi công cộng · hoán đổi giữa các khu, chuyển nhượng sở hữu.
- Khu ngoài chuỗi.
- Cá nhân cho thuê TH3, thu phí khách của cư dân.
- Vé lượt / vé tháng như nghiệp vụ độc lập.
- Thanh toán trong app (QR / VietQR, kể cả mô phỏng) và thanh toán thật.
- API bản đồ thật cho ETA (demo dùng mock, adapter thật sau cờ); theo dõi vị trí liên tục (GPS chỉ mỗi 15 phút, và chỉ khi đang chờ).
- Tích hợp LPR cụ thể và OCR từ ảnh camera. 
- Đồng bộ thật với hệ thống cư dân
- Agent tự phán quyết tranh chấp, duyệt hoán đổi hay đổi phân bổ chỗ khi không có người duyệt.

## 3. Nguyên tắc dữ liệu và quyền riêng tư

- **Biển số:** mã hóa khi lưu; chỉ BQL khu liên quan xem bản gốc, mọi lượt xem ghi log (MVP chỉ hiển thị bản ẩn).
- **Gửi tới LLM:** biển số và tên thay bằng mã giả; ticket chỉ hiện biển số đã ẩn.
- **Phân tách:** theo khu và hộ bằng RLS; ảnh, log chỉ dùng khi người dùng đồng ý. **Giữa các khu:** chỉ trao đổi cấp và hạn tư cách.
- **OCR thấp:** đánh dấu để người có thẩm quyền kiểm tra; so khớp mờ không tự kết luận.

## 4. Giả định và quyết định cần xác nhận
<blockquote style="border-left: 4px solid #22c55e; background: #f0fdf4; padding: 0.75em 1em; margin-left: 0; border-radius: 4px;">
  <strong style="color: #000;">CHỈ THAM KHẢO, CẦN CHỈNH SỬA THÊM</strong>
</blockquote>

| ID | Giả định / quyết định | Ai xác nhận |
|----|-----------------------|-------------|
| A-01 | **Chia sẻ theo nội quy:** trong phạm vi mở đã cấu hình, qua nền tảng chính thức, theo khung giá và mẫu thỏa thuận | Nội quy |
| A-02 | **Pool TH2 được chấp thuận** chia sẻ toàn bộ, ở mọi khu trong chuỗi | Chủ đầu tư |
| A-03 | **Đồng ý xử lý biển số, ảnh** khi đăng ký; phạm vi, hạn lưu, rút đồng ý chốt khi triển khai thật | Khi triển khai |
| A-04 | **Khách:** cư dân chỉ cho khách đỗ miễn phí; khách shophouse sang TH3, shophouse có thể cấp voucher | Quy tắc nghiệp vụ |
| A-05 | **Không thanh toán trong app:** hệ thống chỉ ghi nhận khoản; hai bên tự thanh toán theo thỏa thuận | Demo |
| A-06 | **LPR mô phỏng;** tích hợp thật cần đơn vị vận hành cho phép | Đơn vị vận hành |
| A-07 | **Tham số từ nội quy khu:** dự phòng, ngưỡng duyệt, khung giá, phí quá giờ (nhắc trước 20 phút, miễn 10 phút, 50 000 đ/giờ, bước 15 phút); giá trị demo là mặc định ([D-01, D-02, D-03, D-08](../03-design/07-db-decision-log.md)) | BQL khu |
| A-08 | **Phạm vi mở TH1:** mặc định chỉ trong tòa; mở cả khu (L2) bằng cấu hình từng tòa | **Cần xác nhận pháp lý** |
| A-09 | **Một nền tảng cho cả chuỗi;** BQL khu là nguồn xác minh tư cách duy nhất cho tài sản trong khu | Kiến trúc chung |
| A-10 | **Shophouse:** khối đế thuộc tòa (chủ là L1 của tòa); thấp tầng không thuộc tòa (chủ là L2 của khu) | [PRD §3.2](02-prd.md#32-cấp-tư-cách-tại-vị-trí-chỗ-đỗ) |
| A-11 | **Đồng ý GPS riêng** (`consent_record`): người thuê khi vào hàng chờ, chủ một lần khi bấm "Tôi về sớm"; không lưu tọa độ thô, chỉ ETA; không gửi tọa độ cho LLM ([ADR-0015](../07-adr/ADR-0015-renter-gps-eta-otp-and-two-layer-approval.md), chủ về sớm: [ADR-0014](../07-adr/ADR-0014-eta-location-and-renter-priority-on-early-return.md)) | Pháp lý khi bật API thật |
| A-12 | **Ưu tiên người thuê khi chủ về sớm** và số ô dự phòng tối thiểu của tòa (BR-07, BR-24) | BQL tòa pilot |
| A-13 | **Ưu tiên TH3:** người liên quan khu đô thị (cư dân tòa khác trong khu, chủ shophouse…) được ưu tiên hơn khách vãng lai ở bãi khách; bãi còn ≤ 2 chỗ → báo BQL và bảo vệ (BR-28) | BQL tòa pilot |
| A-14 | **Tham số pilot:** ETA 30 phút; giữ ETA + 10 (tối đa 40, TH3 60); OTP nhận chỗ 3 phút; phí không tới 30% (tối thiểu 1 giờ), hoàn 70%; tin đăng 30 phút; ca chờ BQL 10 phút; review sau 2 tuần pilot | BQL, nhóm sản phẩm |

## 5. Phụ thuộc
- Nội quy, cấu hình từng tòa / khu (loại chỗ, phạm vi mở, giá, dự phòng, ngưỡng duyệt). 
- Tư cách và chỗ đỗ từ BQL khu.
- Log LPR (mã sự kiện,
cổng, hướng, thời điểm, độ tin cậy OCR) từ đơn vị trông giữ xe.
- Pháp lý: hạn lưu, chuyển dữ liệu xuyên biên giới trước khi dùng dữ liệu thật.