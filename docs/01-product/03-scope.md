# Scope — Agent điều phối quyền sử dụng chỗ đỗ trong chuỗi khu đô thị

> **File này trả lời:** bản demo làm gì, không làm gì, xử lý dữ liệu thế nào, giả định nào cần xác nhận?
> Nguồn: [Bài toán](00-xac-dinh-bai-toan.md) · [Brief](01-project-brief.md) · [PRD](02-prd.md) · Việc theo tuần: [Backlog](backlog/README.md)

## 1. Trong phạm vi bản demo

**1 chuỗi, N ≥ 2 khu.** Seed 3 khu, mỗi khu vài tòa (có khối đế), bãi công cộng, pool TH1/TH2/TH3 riêng; kịch bản chạy trên ≥ 2 khu:
**A** khu ở + shophouse thấp tầng (chủ shophouse từ khu khác, trống ban ngày) · **B** khu ở, trường, phòng khám (phụ huynh liên khu, cao điểm
đưa đón) · **C** TTTM, văn phòng (trống ban đêm, cuối tuần, khách theo lượt). Cột *Mức* theo [Backlog §1](backlog/README.md#1-ba-mức-ưu-tiên).

| Hạng mục | Phạm vi | Mức |
|----------|---------|-----|
| Tư cách, liên khu | Một tài khoản, nhiều tư cách có hạn; cấp L1–L4 tại ô; phạm vi mở từng pool. Gợi ý khu khác khi hết chỗ | 1 · gợi ý: 2 |
| Định tuyến | Quyền thuê theo cấp và phạm vi mở; ghép TH1/TH2, hoặc TH3 / bãi công cộng theo giá cấp | 1 |
| Chia sẻ, ghép | Lịch, dự phòng, ghép theo giờ, kích thước, phạm vi; thỏa thuận theo mẫu khu, hai bên xác nhận OTP, bằng chứng xác nhận | 1 |
| Log LPR | Nạp CSV mô phỏng, chuẩn hóa, chống trùng (N1) | 1 |
| Thanh toán | VietQR mock, không tiền thật | 2 |
| Ngoại lệ | Chủ về sớm (từ app) → TH3 cùng khu. Quá giờ: nhắc 2 lần (trước 20 phút, đúng giờ hết), phí tính khi xe ra (N2, W4); mức phí mặc định, BQL xác nhận | 2 |
| Tranh chấp | Cư dân báo kèm ảnh → BQL khu có ô; W5 gom bằng chứng, đọc ảnh đã che biển số, tóm tắt "Gợi ý"; BQL quyết định. Demo dùng ảnh che sẵn bằng tay | 2 |
| Thiết kế, chưa làm | Hoán đổi (2 bên / theo vòng, cùng khu), voucher, N3–N8; xem biển số gốc có ghi log, làm mờ ảnh tự động, so khớp mờ / OCR thấp | 3 |

Thao tác ảnh hưởng quyền sử dụng chỗ hoặc kết luận tranh chấp cần **BQL khu có ô đỗ** duyệt qua HITL.

## 2. Ngoài phạm vi bản demo

Bãi riêng trường, bệnh viện, văn phòng độc lập, TTTM · đặt chỗ / quản lý tồn chỗ bãi công cộng · hoán đổi giữa các khu, chuyển nhượng sở hữu ·
khu ngoài chuỗi · cá nhân cho thuê TH3, thu phí khách của cư dân · vé lượt / vé tháng như nghiệp vụ độc lập · thanh toán thật, MoMo, ZaloPay ·
tích hợp LPR cụ thể và OCR từ ảnh camera (demo dùng log mô phỏng có độ tin cậy OCR; LLM đọc ảnh tranh chấp W5 không thuộc mục này; ảnh demo che biển số sẵn) ·
đồng bộ thật với hệ thống cư dân · Agent tự phán quyết tranh chấp, duyệt hoán đổi hay đổi phân bổ chỗ khi không có người duyệt.

## 3. Nguyên tắc dữ liệu và quyền riêng tư

- **Biển số:** mã hóa khi lưu; chỉ BQL khu liên quan xem bản gốc, mọi lượt xem ghi log (MVP chỉ hiển thị bản ẩn).
- **Gửi tới LLM:** biển số và tên thay bằng mã giả; ticket chỉ hiện biển số đã ẩn.
- **Phân tách:** theo khu và hộ bằng RLS; ảnh, log chỉ dùng khi người dùng đồng ý. **Giữa các khu:** chỉ trao đổi cấp và hạn tư cách.
- **OCR thấp:** đánh dấu để người có thẩm quyền kiểm tra; so khớp mờ không tự kết luận.

## 4. Giả định và quyết định cần xác nhận

| ID | Giả định / quyết định | Ai xác nhận |
|----|-----------------------|-------------|
| A-01 | **Chia sẻ theo nội quy:** trong phạm vi mở đã cấu hình, qua nền tảng chính thức, theo khung giá và mẫu thỏa thuận | Nội quy |
| A-02 | **Pool TH2 được chấp thuận** chia sẻ toàn bộ, ở mọi khu trong chuỗi | Chủ đầu tư |
| A-03 | **Đồng ý xử lý biển số, ảnh** khi đăng ký; phạm vi, hạn lưu, rút đồng ý chốt khi triển khai thật | Khi triển khai |
| A-04 | **Khách:** cư dân chỉ cho khách đỗ miễn phí; khách shophouse sang TH3, shophouse có thể cấp voucher | Quy tắc nghiệp vụ |
| A-05 | **VietQR mô phỏng:** không xác nhận hay đối soát tiền thật | Demo |
| A-06 | **LPR mô phỏng;** tích hợp thật cần đơn vị vận hành cho phép | Đơn vị vận hành |
| A-07 | **Tham số từ nội quy khu:** dự phòng, ngưỡng duyệt, khung giá, phí quá giờ (nhắc trước 20 phút, miễn 10 phút, 50 000 đ/giờ, bước 15 phút); giá trị demo là mặc định ([D-01, D-02, D-03, D-08](../03-design/07-db-decision-log.md)) | BQL khu |
| A-08 | **Phạm vi mở TH1:** mặc định chỉ trong tòa; mở cả khu (L2) bằng cấu hình từng tòa | **Cần xác nhận pháp lý** |
| A-09 | **Một nền tảng cho cả chuỗi;** BQL khu là nguồn xác minh tư cách duy nhất cho tài sản trong khu | Kiến trúc chung |
| A-10 | **Shophouse:** khối đế thuộc tòa (chủ là L1 của tòa); thấp tầng không thuộc tòa (chủ là L2 của khu) | [PRD §3.2](02-prd.md#32-cấp-tư-cách-tại-vị-trí-chỗ-đỗ) |

## 5. Phụ thuộc

Nội quy, cấu hình từng tòa / khu (loại chỗ, phạm vi mở, giá, dự phòng, ngưỡng duyệt) · tư cách và chỗ đỗ từ BQL khu · log LPR (mã sự kiện,
cổng, hướng, thời điểm, độ tin cậy OCR) từ đơn vị trông giữ xe · pháp lý: hạn lưu, chuyển dữ liệu xuyên biên giới trước khi dùng dữ liệu thật.

## 6. Chỉ số theo dõi

KPI theo khu và toàn chuỗi: [Brief §7](01-project-brief.md#7-chỉ-số-thành-công-kpi). Demo đo bằng view `kpi_daily_v` (yêu cầu, ghép, chuyển hướng, bị chặn, không có chỗ).
