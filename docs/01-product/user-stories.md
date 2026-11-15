# User Stories — Agent điều phối quyền sử dụng chỗ đỗ

> Nguồn: [01-xac-dinh-bai-toan.md](../01-xac-dinh-bai-toan.md)
> Yêu cầu: [PRD](prd.md) · Tiêu chí nghiệm thu: [Acceptance Criteria](acceptance-criteria.md) · Luồng: [User Flow](ux/user-flow.md)

Định dạng: *Là **[vai trò]**, tôi muốn **[hành động]**, để **[lợi ích]**.* Lợi ích được lấy từ phần Vấn đề / Ai được lợi gì của tài liệu nguồn.

## Epic 1 — Định tuyến

| ID | User Story | FR |
|----|-----------|----|
| US-01 | Là **người cần chỗ được thuê chỗ riêng** (cư dân không có chỗ, người thuê căn hộ, hộ có xe thứ hai, shophouse, văn phòng, phòng khám, trường mầm non), tôi muốn được ghép vào chỗ TH1 hoặc TH2, để đỗ ngay trong tòa với giá rẻ hơn gửi ngoài. | FR-01, FR-02 |
| US-02 | Là **người chỉ được dùng TH3/bãi công cộng** (khách vãng lai, khách shophouse, phụ huynh, người nhà bệnh nhân, nhân viên tòa văn phòng độc lập), tôi muốn được chuyển sang TH3 hoặc bãi công cộng, để có chỗ đỗ phù hợp quyền của mình. | FR-01, FR-03 |
| US-03 | Là **BQL**, tôi muốn hệ thống chặn giao dịch sai đối tượng, để chia sẻ tuân thủ nội quy. | FR-04 |

## Epic 2 — Chia sẻ

| ID | User Story | FR |
|----|-----------|----|
| US-04 | Là **chủ chỗ** (cư dân có TH1/TH2, văn phòng có chỗ riêng), tôi muốn được đề xuất khung giờ có thể chia sẻ, để khai thác chỗ đang bỏ trống. | FR-05 |
| US-05 | Là **chủ chỗ**, tôi muốn có khoảng dự phòng khi chia sẻ, để không sợ mất chỗ khi về. | FR-06 |
| US-06 | Là **người cần chỗ**, tôi muốn được ghép với chỗ đang được chia sẻ, để có chỗ đỗ trong tòa. | FR-07 |
| US-07 | Là **chủ chỗ / người thuê**, tôi muốn nhận thỏa thuận điện tử theo mẫu để xác nhận, để giảm rủi ro tranh chấp. | FR-08 |
| US-08 | Là **BQL**, tôi muốn mỗi giao dịch đã xác nhận được ghi vào sổ cái, để ghi nhận và có bằng chứng khi cần. | FR-09 |

## Epic 3 — Xử lý ngoại lệ

| ID | User Story | FR |
|----|-----------|----|
| US-09 | Là **chủ chỗ về sớm**, tôi muốn lấy lại chỗ của mình trong khi người thuê được điều phối sang chỗ thay thế, để được bảo đảm quyền quay về. | FR-10 |
| US-10 | Là **người thuê bị chủ về sớm**, tôi muốn được cấp chỗ thay thế từ pool TH3, để vẫn có chỗ đỗ. | FR-10 |
| US-11 | Là **chủ chỗ**, tôi muốn người thuê đỗ quá giờ được nhắc và bị tính phí theo nội quy, để chỗ của tôi được trả đúng hạn. | FR-11, FR-12 |

## Epic 4 — Tranh chấp

| ID | User Story | FR |
|----|-----------|----|
| US-12 | Là **BQL**, tôi muốn nhận ticket tranh chấp đã có ảnh, đối chiếu sổ cái và dữ liệu cổng, để xác minh nhanh và có bằng chứng thay vì xử lý thủ công. | FR-13, FR-14, FR-16 |
| US-13 | Là **cư dân**, tôi muốn biển số được ẩn trong ticket tranh chấp, để dữ liệu cá nhân được bảo vệ. | FR-15 |

## Epic 5 — Hoán đổi

| ID | User Story | FR |
|----|-----------|----|
| US-14 | Là **người dùng có chỗ không hợp nhu cầu** (ví dụ xe SUV ở chỗ hẹp) hoặc **liên quan tranh chấp lặp lại**, tôi muốn được đề xuất hoán đổi 2 bên hoặc theo chuỗi, để có chỗ phù hợp hơn. | FR-17 |
| US-15 | Là **BQL**, tôi muốn phê duyệt các đề xuất hoán đổi trước khi có hiệu lực, để kiểm soát thay đổi chỗ đỗ. | FR-18 |

## Epic 6 — Ghép phù hợp và vận hành LPR

| ID | User Story | FR |
|----|-----------|----|
| US-16 | Là **người cần chỗ**, tôi muốn chỉ được ghép vào ô phù hợp kích thước xe và khung giờ của mình, để đỗ an toàn, không lấn vạch. | FR-07 |
| US-17 | Là **BQL**, tôi muốn nhận các log LPR trùng hoặc có độ tin cậy OCR thấp trong quy trình xử lý phù hợp, để dữ liệu sai không tạo giao dịch hoặc kết luận tự động. | FR-16a |
| US-18 | Là **chủ chỗ**, tôi muốn xem gợi ý khung giờ thường trống dựa trên lịch sử, để chọn thời gian chia sẻ phù hợp. | FR-20 |

## Ưu tiên

Mức ưu tiên (MoSCoW / release) cho từng story: **TBD**.
