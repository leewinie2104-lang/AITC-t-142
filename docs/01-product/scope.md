# Scope — Agent điều phối quyền sử dụng chỗ đỗ trong chuỗi khu đô thị

> Nguồn nghiệp vụ: [01-xac-dinh-bai-toan.md](../01-xac-dinh-bai-toan.md) · Kiến trúc đề xuất: `docs/images/ParkSmartAI.png` và tài liệu công nghệ ParkSmart AI.
> Liên quan: [Project Brief](project-brief.md) · [PRD](prd.md)

## 1. Trong phạm vi bản demo

Mô hình dữ liệu hỗ trợ **1 chuỗi gồm N khu (N ≥ 2)**. Bản demo nạp dữ liệu mô phỏng cho **3 khu**:

| Khu | Đặc điểm mô phỏng | Mục đích trong demo |
|-----|-------------------|---------------------|
| A | Khu ở, có cụm shophouse thấp tầng | Chủ shophouse từ khu khác sang; khu thuần ở nên trống chỗ ban ngày |
| B | Khu ở, có trường liên cấp và phòng khám | Phụ huynh liên khu; cao điểm đưa đón con |
| C | Khu có trung tâm thương mại và tòa văn phòng | Văn phòng trống chỗ ban đêm và cuối tuần; khách theo lượt |

Mỗi khu có vài tòa (có khối đế), một bãi công cộng và pool TH1/TH2/TH3 riêng.

| Hạng mục | Phạm vi |
|----------|---------|
| Tư cách và liên khu | Một tài khoản cho cả chuỗi, có nhiều tư cách và hạn hiệu lực. Tính cấp L1–L4 tại vị trí ô đỗ. Cấu hình phạm vi mở của từng pool. Gợi ý chỗ ở khu khác khi một khu hết chỗ. |
| Định tuyến yêu cầu | Kiểm tra quyền thuê chỗ riêng theo cấp tư cách và phạm vi mở. Ghép TH1/TH2 hợp lệ, hoặc chuyển sang TH3 / bãi công cộng với giá theo cấp. |
| Chia sẻ và ghép chỗ | Đề xuất lịch chia sẻ, giữ khoảng dự phòng, ghép theo khung giờ, kích thước xe, quyền ưu tiên và phạm vi. Sinh thỏa thuận theo mẫu của khu; hai bên xác nhận; ghi nhận giao dịch. |
| Ngoại lệ | Điều phối người thuê sang TH3 cùng khu khi chủ về sớm. Nhắc và tính phí quá giờ theo nội quy của khu. |
| Tranh chấp | Nhận ảnh và log LPR mô phỏng, đối chiếu sổ cái, tạo ticket đã ẩn biển số và chuyển cho BQL của khu có ô đỗ xác minh. |
| Hoán đổi | Đề xuất hoán đổi giữa hai bên hoặc theo chuỗi trong cùng một khu; chỉ có hiệu lực sau khi BQL khu phê duyệt. |
| Tác vụ nền | Nạp và chuẩn hóa log LPR theo khu qua adapter. Nhắc quá giờ, đối soát cuối ngày, dự báo khung giờ trống theo khu, quét tư cách hết hạn. |
| Thanh toán demo | VietQR mock; voucher shophouse dùng cho lượt đỗ TH3. Bản demo không xử lý tiền thật. |
| Dữ liệu và thông báo | Dữ liệu demo lưu trong PostgreSQL/Supabase. Phân quyền theo vai trò, khu và hộ. Cập nhật trạng thái, cảnh báo và yêu cầu chờ duyệt trong app. |

Các thao tác ảnh hưởng đến quyền sử dụng chỗ hoặc kết luận tranh chấp cần người có thẩm quyền xác nhận. BQL của khu có ô đỗ duyệt tranh chấp, hoán đổi và giao dịch vượt định mức qua bước HITL.

## 2. Ngoài phạm vi bản demo

- Điều phối hoặc tích hợp vận hành các bãi xe riêng của trường học, bệnh viện, tòa văn phòng độc lập và trung tâm thương mại.
- Tự động đặt chỗ hoặc quản lý tồn chỗ tại bãi công cộng chưa tích hợp. Agent chỉ chuyển hướng tới TH3 / bãi công cộng khi có dữ liệu phù hợp.
- Hoán đổi chỗ **giữa các khu**; chuyển nhượng quyền sở hữu chỗ đỗ.
- Liên kết với khu đô thị **ngoài chuỗi** hoặc của chủ đầu tư khác.
- Cá nhân cho thuê chỗ TH3; thu phí khách của cư dân.
- Phát hành và quản lý vé lượt / vé tháng của BQL như một nghiệp vụ độc lập. Vé lượt TH3 chỉ được mô phỏng ở mức voucher / demo khi cần.
- Thanh toán thật, kết nối MoMo hoặc ZaloPay. Các tích hợp này để giai đoạn sau.
- Tích hợp trực tiếp với nhà cung cấp LPR cụ thể, hoặc triển khai nhận diện ảnh / biển số bằng AI. Demo dùng log LPR mô phỏng và adapter webhook / MQTT / DB / CSV.
- Đồng bộ thật với hệ thống quản lý cư dân của từng khu. Demo dùng danh sách tư cách mô phỏng.
- Agent tự động phán quyết tranh chấp, phê duyệt hoán đổi, hoặc tự thay đổi phân bổ chỗ mà không có người duyệt.

## 3. Nguyên tắc dữ liệu và quyền riêng tư

- **Biển số**: mã hóa khi lưu. Chỉ BQL của khu liên quan được xem bản gốc và mọi lần truy cập bản gốc đều được ghi log.
- **Dữ liệu gửi tới LLM**: biển số và tên được thay bằng mã giả trước khi gửi. Ticket hiển thị biển số đã ẩn.
- **Phân tách dữ liệu**: dữ liệu được phân tách theo khu và theo hộ bằng chính sách truy cập theo dòng (RLS). Ảnh và log chỉ được dùng theo sự đồng ý của người dùng và thời hạn lưu giữ do chính sách vận hành quy định.
- **Dữ liệu giữa các khu**: chỉ trao đổi kết quả xác nhận tư cách (cấp tư cách và hạn hiệu lực). Hồ sơ cư dân không được chia sẻ giữa các BQL.
- **OCR độ tin cậy thấp**: dữ liệu LPR loại này được đánh dấu để người có thẩm quyền kiểm tra. So khớp mờ không tự tạo kết luận cuối cùng.

## 4. Giả định và quyết định cần xác nhận

| ID | Giả định / quyết định |
|----|-----------------------|
| A-01 | Nội quy cho phép chia sẻ trong phạm vi mở đã cấu hình, qua nền tảng chính thức, theo khung giá và mẫu thỏa thuận. |
| A-02 | Chủ đầu tư đã chấp thuận cho chia sẻ toàn bộ pool TH2, ở tất cả các khu trong chuỗi. |
| A-03 | Người dùng đồng ý cho xử lý biển số và ảnh khi đăng ký app. Phạm vi, thời hạn lưu và quy trình rút lại đồng ý cần được chốt khi triển khai thật. |
| A-04 | Cư dân chỉ cho khách của mình đỗ miễn phí. Khách shophouse được điều hướng sang TH3 và shophouse có thể cấp voucher. |
| A-05 | VietQR trong demo là mô phỏng, không xác nhận hoặc đối soát giao dịch tiền thật. |
| A-06 | Dữ liệu LPR demo là dữ liệu mô phỏng. Tích hợp với hệ thống thật cần được đơn vị vận hành cho phép. |
| A-07 | Khoảng dự phòng, ngưỡng giao dịch vượt định mức, khung giá và phí quá giờ lấy từ nội quy đã cấu hình (theo khu). Giá trị cụ thể chưa được cung cấp. |
| A-08 | **Cần xác nhận pháp lý**: TH1 có được mở cho thành viên khu (L2) không, hay chỉ cho người sử dụng của chính tòa nhà. Mặc định trong demo là chỉ trong tòa; việc mở ra cả khu được bật bằng cấu hình theo từng tòa. |
| A-09 | Các khu trong chuỗi dùng chung một nền tảng và một mô hình tài khoản. Mỗi BQL khu là nguồn xác minh tư cách duy nhất cho tài sản trong khu của mình. |
| A-10 | Shophouse ở khối đế được xem là tài sản thuộc tòa (chủ shophouse là L1 của tòa đó). Shophouse thấp tầng không thuộc tòa nào (chủ shophouse là L2 của khu). |

## 5. Phụ thuộc

- **Nội quy và cấu hình nghiệp vụ** của từng tòa và từng khu: loại chỗ, phạm vi mở, khung giá theo cấp tư cách, khoảng dự phòng, quyền ưu tiên, ngưỡng cần BQL duyệt.
- **Dữ liệu tư cách** từ BQL từng khu: tài sản, vai trò, hạn hiệu lực.
- **Dữ liệu chỗ đỗ**: kích thước ô và kích thước xe đủ chính xác để ghép.
- **Log LPR từng khu**: có mã sự kiện, cổng, hướng vào/ra, thời điểm và độ tin cậy OCR. Nguồn thật phụ thuộc quyền truy cập của đơn vị trông giữ xe.
- **Dữ liệu đối chiếu và dự báo**: ảnh bằng chứng, sổ cái giao dịch và dữ liệu lịch sử.
- **Quy trình BQL**: quy trình BQL khu xác minh ticket và duyệt đề xuất.
- **Pháp lý**: quy trình pháp lý, thời hạn lưu dữ liệu và hồ sơ chuyển dữ liệu xuyên biên giới cần được xác nhận trước khi dùng dữ liệu thật.

## 6. Chỉ số theo dõi

Các chỉ số dưới đây được theo dõi **theo khu và trên toàn chuỗi**:
- Số giờ chỗ đỗ được khai thác thêm.
- Tỷ lệ ghép thành công.
- Tỷ lệ yêu cầu liên khu được đáp ứng.
- Số xung đột khi chủ về.
- Thời gian lập hồ sơ tranh chấp.
- Số giao dịch sai tư cách hoặc sai phạm vi bị chặn.
- Tỷ lệ tranh chấp lặp lại sau hoán đổi.

Mục tiêu số cụ thể: TBD.
