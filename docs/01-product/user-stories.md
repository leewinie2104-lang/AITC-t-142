# User Stories — Agent điều phối quyền sử dụng chỗ đỗ trong chuỗi khu đô thị

> Nguồn: [01-xac-dinh-bai-toan.md](../01-xac-dinh-bai-toan.md)
> Yêu cầu: [PRD](prd.md) · Tiêu chí nghiệm thu: [Acceptance Criteria](acceptance-criteria.md) · Luồng: [User Flow](ux/user-flow.md)

Định dạng: *Là **[vai trò]**, tôi muốn **[hành động]**, để **[lợi ích]**.* Cấp tư cách L1–L4 (thành viên tòa / khu / chuỗi / khách): xem [PRD §3.2](prd.md#32-cấp-tư-cách-tại-vị-trí-chỗ-đỗ).

## Epic 0 — Tư cách và liên khu

| ID | User Story | FR |
|----|-----------|----|
| US-19 | Là **chủ shophouse ở khu A và sống ở căn hộ khu B**, tôi muốn được thuê chỗ ban ngày ở khu A với tư cách chủ shophouse, để mở hàng mà không phải gửi bãi ngoài với giá khách. | FR-23, FR-24, FR-01 |
| US-20 | Là **cư dân khu B đưa con đến trường ở khu C**, tôi muốn thuê chỗ theo khung giờ đưa đón với tư cách thành viên chuỗi, để không phải đỗ dưới lòng đường. | FR-24, FR-26, FR-07 |
| US-21 | Là **người dùng có tài sản ở nhiều khu**, tôi muốn dùng một tài khoản duy nhất và tự động được áp đúng tư cách tại nơi tôi đỗ, để không phải đăng ký lại ở mỗi khu. | FR-23, FR-24 |
| US-22 | Là **BQL khu**, tôi muốn tư cách của người thuê căn hộ tự hết hiệu lực khi hết hợp đồng, để người không còn quyền không tiếp tục thuê chỗ riêng. | FR-25 |
| US-23 | Là **chủ chỗ TH1**, tôi muốn giới hạn chỉ người cùng tòa được thuê chỗ của tôi, dù nội quy cho phép mở rộng hơn, để tôi yên tâm khi chia sẻ. | FR-26 |
| US-24 | Là **cư dân**, tôi muốn BQL các khu khác chỉ biết tôi "có tư cách hợp lệ" mà không thấy hồ sơ của tôi, để thông tin cá nhân được bảo vệ. | BR-17 |
| US-25 | Là **người cần chỗ**, khi khu tôi đến đã hết chỗ phù hợp, tôi muốn được gợi ý chỗ ở khu lân cận trong chuỗi, để vẫn có phương án đỗ. | FR-27 |

## Epic 1 — Định tuyến

| ID | User Story | FR |
|----|-----------|----|
| US-01 | Là **người cần chỗ có cấp tư cách nằm trong phạm vi mở của pool** (ví dụ cư dân không có chỗ, người thuê căn hộ, hộ có xe thứ hai, shophouse, văn phòng, phòng khám, trường mầm non, thành viên chuỗi với pool TH2 mở cho cả chuỗi), tôi muốn được ghép vào chỗ TH1 hoặc TH2, để đỗ ngay tại nơi cần đến với giá rẻ hơn gửi ngoài. | FR-01, FR-02 |
| US-02 | Là **người không đạt phạm vi mở** (khách vãng lai, khách shophouse, hoặc thành viên chuỗi khi pool chỉ mở trong khu), tôi muốn được chuyển sang TH3 hoặc bãi công cộng với giá đúng cấp của mình, để có chỗ đỗ phù hợp với quyền của mình. | FR-01, FR-03 |
| US-03 | Là **BQL khu**, tôi muốn hệ thống chặn giao dịch sai tư cách hoặc sai phạm vi, để việc chia sẻ tuân thủ nội quy. | FR-04 |

## Epic 2 — Chia sẻ

| ID | User Story | FR |
|----|-----------|----|
| US-04 | Là **chủ chỗ** (cư dân có TH1/TH2, văn phòng có chỗ riêng), tôi muốn được đề xuất khung giờ có thể chia sẻ, để khai thác chỗ đang bỏ trống. | FR-05 |
| US-05 | Là **chủ chỗ**, tôi muốn có khoảng dự phòng khi chia sẻ, để không sợ mất chỗ khi về. | FR-06 |
| US-06 | Là **người cần chỗ**, tôi muốn được ghép với chỗ đang được chia sẻ mà tôi đủ điều kiện thuê, để có chỗ đỗ tại nơi cần đến. | FR-07 |
| US-07 | Là **chủ chỗ / người thuê**, tôi muốn nhận thỏa thuận điện tử theo mẫu của khu có ô đỗ để xác nhận, để giảm rủi ro tranh chấp. | FR-08 |
| US-08 | Là **BQL khu**, tôi muốn mỗi giao dịch đã xác nhận được ghi vào sổ cái, để ghi nhận và có bằng chứng khi cần. | FR-09 |

## Epic 3 — Xử lý ngoại lệ

| ID | User Story | FR |
|----|-----------|----|
| US-09 | Là **chủ chỗ về sớm**, tôi muốn lấy lại chỗ của mình trong khi người thuê được điều phối sang chỗ thay thế, để được bảo đảm quyền quay về. | FR-10 |
| US-10 | Là **người thuê bị chủ về sớm**, tôi muốn được cấp chỗ thay thế từ pool TH3 cùng khu, hoặc được gợi ý chỗ ở khu lân cận nếu khu đó đã hết chỗ, để vẫn có chỗ đỗ. | FR-10, FR-27 |
| US-11 | Là **chủ chỗ**, tôi muốn người thuê đỗ quá giờ được nhắc và bị tính phí theo nội quy, để chỗ của tôi được trả đúng hạn. | FR-11, FR-12 |

## Epic 4 — Tranh chấp

| ID | User Story | FR |
|----|-----------|----|
| US-12 | Là **BQL khu**, tôi muốn nhận ticket tranh chấp đã có ảnh, đã đối chiếu sổ cái và dữ liệu cổng, kể cả khi một bên là thành viên khu khác, để xác minh nhanh và có bằng chứng thay vì xử lý thủ công. | FR-13, FR-14, FR-16 |
| US-13 | Là **cư dân**, tôi muốn biển số được ẩn trong ticket tranh chấp, để dữ liệu cá nhân được bảo vệ. | FR-15 |

## Epic 5 — Hoán đổi

| ID | User Story | FR |
|----|-----------|----|
| US-14 | Là **người dùng có chỗ không hợp nhu cầu** (ví dụ xe SUV ở chỗ hẹp) hoặc **liên quan đến tranh chấp lặp lại**, tôi muốn được đề xuất hoán đổi với người khác trong cùng khu (2 bên hoặc theo chuỗi), để có chỗ phù hợp hơn. | FR-17 |
| US-15 | Là **BQL khu**, tôi muốn phê duyệt các đề xuất hoán đổi trước khi chúng có hiệu lực, để kiểm soát thay đổi chỗ đỗ. | FR-18 |

## Epic 6 — Ghép phù hợp và vận hành LPR

| ID | User Story | FR |
|----|-----------|----|
| US-16 | Là **người cần chỗ**, tôi muốn chỉ được ghép vào ô phù hợp với kích thước xe và khung giờ của mình, để đỗ an toàn, không lấn vạch. | FR-07 |
| US-17 | Là **BQL khu**, tôi muốn các log LPR trùng hoặc có độ tin cậy OCR thấp được đưa vào quy trình xử lý phù hợp, để dữ liệu sai không tạo ra giao dịch hoặc kết luận tự động. | FR-16a |
| US-18 | Là **chủ chỗ**, tôi muốn xem gợi ý các khung giờ thường trống dựa trên lịch sử, để chọn thời gian chia sẻ phù hợp. | FR-20 |

## Ưu tiên

Theo 3 mức của [Backlog](backlog/README.md):

| Mức | User Story |
|-----|-----------|
| **Rất cần thiết** | US-01, US-02, US-03, US-05, US-06, US-07, US-08, US-09, US-10 (chỗ thay thế cùng khu), US-16, US-19, US-20, US-21, US-22 (chặn khi hết hạn), US-24 |
| **Nên có** | US-04, US-11, US-12, US-13, US-14, US-15, US-17, US-18, US-23, US-25; phần gợi ý khu lân cận của US-10; phần thông báo hết hạn của US-22 |
| **Có thể trong tương lai** | Chưa có story; xem mục 3 trong từng file backlog |
