# Scope — Agent điều phối quyền sử dụng chỗ đỗ

> Nguồn nghiệp vụ: [01-xac-dinh-bai-toan.md](../01-xac-dinh-bai-toan.md) · Kiến trúc đề xuất: `docs/images/ParkSmartAI.png` và tài liệu công nghệ ParkSmart AI.
> Liên quan: [Project Brief](project-brief.md) · [PRD](prd.md)

## 1. Trong phạm vi bản demo

| Hạng mục | Phạm vi |
|----------|---------|
| Định tuyến yêu cầu | Kiểm tra quyền thuê chỗ riêng; ghép TH1/TH2 hợp lệ hoặc chuyển sang TH3/bãi công cộng theo dữ liệu có sẵn. |
| Chia sẻ và ghép chỗ | Đề xuất lịch chia sẻ, giữ khoảng dự phòng, ghép theo khung giờ, kích thước xe và quyền ưu tiên; sinh thỏa thuận theo mẫu, hai bên xác nhận và ghi nhận giao dịch. |
| Ngoại lệ | Điều phối người thuê sang chỗ TH3 khi chủ về sớm; nhắc và tính phí quá giờ theo nội quy. |
| Tranh chấp | Nhận ảnh và log LPR mô phỏng, đối chiếu sổ cái, tạo ticket đã ẩn biển số và chuyển BQL xác minh. |
| Hoán đổi | Đề xuất hoán đổi hai bên hoặc theo chuỗi; chỉ có hiệu lực sau khi BQL phê duyệt. |
| Tác vụ nền | Nạp và chuẩn hóa log LPR qua adapter; nhắc quá giờ, đối soát cuối ngày và dự báo khung giờ trống từ dữ liệu lịch sử. |
| Thanh toán demo | VietQR mock; voucher shophouse dùng cho lượt đỗ TH3. Không xử lý tiền thật trong bản demo. |
| Dữ liệu và thông báo | Dữ liệu demo trong PostgreSQL/Supabase; phân quyền theo vai trò và hộ; cập nhật trạng thái, cảnh báo và yêu cầu chờ duyệt trong app. |

Các thao tác có ảnh hưởng đến quyền sử dụng chỗ hoặc kết luận tranh chấp cần người có thẩm quyền xác nhận. BQL duyệt tranh chấp, hoán đổi và giao dịch vượt định mức qua bước HITL.

## 2. Ngoài phạm vi bản demo

- Điều phối hoặc tích hợp vận hành các bãi xe riêng của trường học, bệnh viện, tòa văn phòng độc lập và trung tâm thương mại.
- Tự động đặt chỗ hoặc quản lý tồn chỗ tại bãi công cộng chưa tích hợp. Agent chỉ chuyển hướng tới TH3/bãi công cộng khi có dữ liệu phù hợp.
- Cá nhân cho thuê chỗ TH3; thu phí khách của cư dân.
- Phát hành và quản lý vé lượt/vé tháng của BQL như một nghiệp vụ độc lập; vé lượt TH3 chỉ được mô phỏng ở mức voucher/demo khi cần.
- Thanh toán thật, kết nối MoMo hoặc ZaloPay; các tích hợp này để giai đoạn sau.
- Tích hợp trực tiếp với nhà cung cấp LPR cụ thể hoặc triển khai nhận diện ảnh/biển số bằng AI. Demo dùng log LPR mô phỏng và adapter webhook/MQTT/DB/CSV.
- Agent tự động phán quyết tranh chấp, phê duyệt hoán đổi hoặc tự thay đổi phân bổ chỗ mà không có người duyệt.

## 3. Nguyên tắc dữ liệu và quyền riêng tư

- Biển số được mã hóa khi lưu; chỉ vai trò BQL được xem bản gốc và mọi lần truy cập bản gốc được ghi log.
- Biển số và tên được thay bằng mã giả trước khi gửi nội dung tới LLM; ticket hiển thị biển số đã ẩn.
- Dữ liệu phân tách theo hộ bằng chính sách truy cập hàng (RLS). Ảnh/log chỉ được dùng theo sự đồng ý và thời hạn lưu giữ do chính sách vận hành quy định.
- Dữ liệu LPR có OCR độ tin cậy thấp được đánh dấu để người có thẩm quyền kiểm tra; so khớp mờ không tự tạo kết luận cuối cùng.

## 4. Giả định và quyết định cần xác nhận

| ID | Giả định / quyết định |
|----|-----------------------|
| A-01 | Nội quy cho phép chia sẻ trong nội bộ tòa nhà qua nền tảng chính thức, theo khung giá và mẫu thỏa thuận. |
| A-02 | Chủ đầu tư đã chấp thuận cho chia sẻ toàn bộ pool TH2. |
| A-03 | Người dùng đồng ý xử lý biển số và ảnh khi đăng ký app; phạm vi, thời hạn lưu và quy trình rút đồng ý cần được chốt khi triển khai thật. |
| A-04 | Cư dân chỉ cho khách của mình đỗ miễn phí; khách shophouse được điều hướng sang TH3 và shophouse có thể cấp voucher. |
| A-05 | VietQR trong demo là mô phỏng, không xác nhận hoặc đối soát giao dịch tiền thật. |
| A-06 | Dữ liệu LPR demo là dữ liệu mô phỏng; tích hợp hệ thống thật cần được đơn vị vận hành cho phép. |
| A-07 | Khung dự phòng, ngưỡng giao dịch vượt định mức, khung giá và phí quá giờ lấy từ nội quy cấu hình; giá trị cụ thể chưa được cung cấp. |

## 5. Phụ thuộc

- Nội quy và cấu hình nghiệp vụ: nhóm người dùng, loại chỗ, khung giá, khoảng dự phòng, quyền ưu tiên, ngưỡng cần BQL duyệt.
- Dữ liệu chỗ đỗ, kích thước ô và kích thước xe đủ chính xác để ghép.
- Log LPR có mã sự kiện, cổng, hướng vào/ra, thời điểm và độ tin cậy OCR; nguồn thật phụ thuộc quyền truy cập của đơn vị trông giữ xe.
- Ảnh bằng chứng, sổ cái giao dịch và dữ liệu lịch sử để đối chiếu/dự báo.
- Tài khoản và vai trò người dùng; quy trình BQL xác minh ticket và duyệt đề xuất.
- Quy trình pháp lý, thời hạn lưu dữ liệu và hồ sơ chuyển dữ liệu xuyên biên giới cần được xác nhận trước khi dùng dữ liệu thật.

## 6. Chỉ số theo dõi

Theo dõi số giờ chỗ được khai thác thêm, tỷ lệ ghép thành công, xung đột khi chủ về, thời gian lập hồ sơ tranh chấp, giao dịch sai đối tượng bị chặn và tỷ lệ tranh chấp lặp lại sau hoán đổi. Mục tiêu số cụ thể: TBD.
