# Scope — Agent điều phối quyền sử dụng chỗ đỗ trong chuỗi khu đô thị

> **File này trả lời câu hỏi**: bản demo làm gì, không làm gì, xử lý dữ liệu thế nào, giả định nào cần xác nhận?
> 
> Nguồn: [Bài toán](00-xac-dinh-bai-toan.md) · Kiến trúc: [Architecture Diagram](../02-architecture/01-architecture-diagram.md) · [Tech stack](../02-architecture/02-tech-stack.md) · Liên quan: [Project Brief](01-project-brief.md) · [PRD](02-prd.md)

## 1. Trong phạm vi bản demo

Hỗ trợ **1 chuỗi gồm N khu (N ≥ 2)**. Demo nạp dữ liệu mô phỏng cho **3 khu**, mỗi khu có vài tòa (có khối đế), bãi công cộng và pool TH1/TH2/TH3 riêng.

| Khu | Đặc điểm mô phỏng | Mục đích trong demo |
|-----|-------------------|---------------------|
| A | Khu ở, cụm shophouse thấp tầng | Chủ shophouse từ khu khác sang; trống ban ngày |
| B | Khu ở, trường liên cấp, phòng khám | Phụ huynh liên khu; cao điểm đưa đón |
| C | Trung tâm thương mại, tòa văn phòng | Trống ban đêm, cuối tuần; khách theo lượt |

| Hạng mục | Phạm vi |
|----------|---------|
| Tư cách, liên khu | Một tài khoản, nhiều tư cách và hạn hiệu lực. Tính cấp L1–L4 tại ô đỗ. Cấu hình phạm vi mở từng pool. Gợi ý khu khác khi hết chỗ. |
| Định tuyến | Kiểm tra quyền thuê riêng theo cấp và phạm vi mở; ghép TH1/TH2 hợp lệ, hoặc TH3 / bãi công cộng theo giá cấp. |
| Chia sẻ, ghép chỗ | Lịch, khoảng dự phòng, ghép theo giờ, kích thước xe, ưu tiên, phạm vi. Thỏa thuận theo mẫu khu; hai bên xác nhận; ghi nhận. |
| Ngoại lệ | Chủ về sớm: chuyển người thuê sang TH3 cùng khu. Quá giờ: nhắc, tính phí theo nội quy khu. |
| Tranh chấp | Ảnh và log LPR mô phỏng, đối chiếu bằng chứng xác nhận, ticket đã ẩn biển số, chuyển BQL khu xác minh. |
| Hoán đổi | Hai bên hoặc theo chuỗi trong một khu; chỉ có hiệu lực khi BQL khu phê duyệt. |
| Tác vụ nền | Nạp, chuẩn hóa log LPR qua adapter; nhắc quá giờ, đối soát cuối ngày, dự báo khung giờ trống, quét tư cách hết hạn. |
| Thanh toán demo | VietQR mock; voucher shophouse cho lượt TH3. Không xử lý tiền thật. |
| Dữ liệu, thông báo | PostgreSQL (RDS); phân quyền theo vai trò, khu, hộ; cảnh báo và yêu cầu chờ duyệt trong app. |

Thao tác ảnh hưởng quyền sử dụng chỗ hoặc kết luận tranh chấp cần người có thẩm quyền xác nhận: BQL khu có ô đỗ duyệt qua bước HITL.

## 2. Ngoài phạm vi bản demo

- Bãi riêng trường, bệnh viện, tòa văn phòng độc lập, TTTM: không điều phối, không tích hợp.
- Đặt chỗ tự động hoặc quản lý tồn chỗ bãi công cộng chưa tích hợp.
- Hoán đổi giữa các khu; chuyển nhượng quyền sở hữu chỗ.
- Khu ngoài chuỗi, hoặc của chủ đầu tư khác.
- Cá nhân cho thuê TH3; thu phí khách của cư dân.
- Vé lượt / vé tháng như nghiệp vụ độc lập (TH3 chỉ voucher/demo khi cần).
- Thanh toán thật, MoMo, ZaloPay (giai đoạn sau).
- Tích hợp LPR cụ thể, nhận diện ảnh bằng AI (demo: log mô phỏng, adapter webhook / MQTT / DB / CSV).
- Đồng bộ thật với hệ thống cư dân của khu (demo: danh sách mô phỏng).
- Agent tự phán quyết tranh chấp, duyệt hoán đổi, hoặc đổi phân bổ chỗ khi không có người duyệt.

## 3. Nguyên tắc dữ liệu và quyền riêng tư

| Nguyên tắc | Quy định |
|-----------|----------|
| **Biển số** | Mã hóa khi lưu; chỉ BQL khu liên quan xem bản gốc, mọi truy cập ghi log. |
| **Gửi tới LLM** | Biển số và tên thay bằng mã giả; ticket chỉ hiển thị biển số đã ẩn. |
| **Phân tách** | Theo khu và hộ, bằng RLS. Ảnh, log chỉ dùng khi người dùng đồng ý; thời hạn lưu theo chính sách vận hành. |
| **Giữa các khu** | Chỉ trao đổi kết quả xác nhận tư cách (cấp, hạn hiệu lực); không chia sẻ hồ sơ cư dân. |
| **OCR thấp** | Đánh dấu để người có thẩm quyền kiểm tra; so khớp mờ không tự kết luận. |

## 4. Giả định và quyết định cần xác nhận

| ID | Tên giả định / quyết định | Giả định / quyết định | Trạng thái / ai xác nhận |
|----|---------------------------|-----------------------|--------------------------|
| A-01 | **Chia sẻ theo nội quy** | Nội quy cho phép chia sẻ trong phạm vi mở đã cấu hình, qua nền tảng chính thức, theo khung giá và mẫu thỏa thuận. | Nội quy đã cấu hình |
| A-02 | **Pool TH2 được chấp thuận** | Chủ đầu tư đã chấp thuận cho chia sẻ toàn bộ pool TH2, ở tất cả các khu trong chuỗi. | Chủ đầu tư |
| A-03 | **Đồng ý xử lý biển số, ảnh** | Người dùng đồng ý cho xử lý biển số và ảnh khi đăng ký app. Phạm vi, thời hạn lưu và quy trình rút lại đồng ý cần được chốt khi triển khai thật. | Chốt khi triển khai: phạm vi, thời hạn lưu, rút đồng ý |
| A-04 | **Khách cư dân và khách shophouse** | Cư dân chỉ cho khách của mình đỗ miễn phí. Khách shophouse được điều hướng sang TH3 và shophouse có thể cấp voucher. | Quy tắc nghiệp vụ |
| A-05 | **VietQR mô phỏng** | VietQR trong demo là mô phỏng, không xác nhận hoặc đối soát giao dịch tiền thật. | Demo |
| A-06 | **Dữ liệu LPR mô phỏng** | Dữ liệu LPR demo là dữ liệu mô phỏng. Tích hợp với hệ thống thật cần được đơn vị vận hành cho phép. | Đơn vị vận hành |
| A-07 | **Tham số lấy từ nội quy khu** | Khoảng dự phòng, ngưỡng giao dịch vượt định mức, khung giá và phí quá giờ lấy từ nội quy đã cấu hình (theo khu). Giá trị cụ thể chưa được cung cấp. | Giá trị chưa được cung cấp |
| A-08 | **Phạm vi mở của TH1** | **Cần xác nhận pháp lý**: TH1 có được mở cho thành viên khu (L2) không, hay chỉ cho người sử dụng của chính tòa nhà. Mặc định trong demo là chỉ trong tòa; việc mở ra cả khu được bật bằng cấu hình theo từng tòa. | **Cần xác nhận pháp lý** |
| A-09 | **Một nền tảng cho cả chuỗi** | Các khu trong chuỗi dùng chung một nền tảng và một mô hình tài khoản. Mỗi BQL khu là nguồn xác minh tư cách duy nhất cho tài sản trong khu của mình. | Kiến trúc chung |
| A-10 | **Shophouse thuộc tòa hay khu** | Shophouse ở khối đế được xem là tài sản thuộc tòa (chủ shophouse là L1 của tòa đó). Shophouse thấp tầng không thuộc tòa nào (chủ shophouse là L2 của khu). | [PRD §3.2](02-prd.md#32-cấp-tư-cách-tại-vị-trí-chỗ-đỗ) |

## 5. Phụ thuộc

- **Nội quy, cấu hình** từng tòa, khu: loại chỗ, phạm vi mở, khung giá, dự phòng, ưu tiên, ngưỡng BQL duyệt.
- **Dữ liệu** từ BQL khu: tư cách (tài sản, vai trò, hạn hiệu lực); chỗ đỗ (kích thước ô, xe).
- **Log LPR** từng khu: mã sự kiện, cổng, hướng, thời điểm, độ tin cậy OCR; nguồn thật phụ thuộc đơn vị trông giữ xe.
- **Đối chiếu, dự báo, quy trình BQL**: ảnh bằng chứng, bằng chứng xác nhận, lịch sử; BQL xác minh ticket, duyệt đề xuất.
- **Pháp lý**: quy trình, thời hạn lưu, chuyển dữ liệu xuyên biên giới, xác nhận trước khi dùng dữ liệu thật.

## 6. Chỉ số theo dõi

Theo dõi **theo khu và toàn chuỗi**: số giờ chỗ đỗ được khai thác thêm; tỷ lệ ghép thành công; tỷ lệ yêu cầu liên khu được đáp ứng; số xung đột khi chủ về; thời gian lập hồ sơ tranh chấp; số giao dịch sai tư cách hoặc sai phạm vi bị chặn; tỷ lệ tranh chấp lặp lại sau hoán đổi. Mục tiêu số: TBD ([Project Brief §7](01-project-brief.md#7-chỉ-số-thành-công-kpi)).
