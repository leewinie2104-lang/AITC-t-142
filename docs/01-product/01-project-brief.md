# Project Brief — Agent điều phối quyền sử dụng chỗ đỗ trong chuỗi khu đô thị

> **File này trả lời câu hỏi**: vì sao cần sản phẩm, vấn đề nào cần giải, ai được lợi, đo bằng gì?

> Nguồn: [Bài toán](00-xac-dinh-bai-toan.md) · Liên quan: [PRD](02-prd.md) · [Scope](03-scope.md) · [User Stories & AC](04-user-stories.md) · [User Flow](ux/01-user-flow.md)

## 1. Bối cảnh

Chủ đầu tư vận hành **chuỗi từ 2 khu đô thị trở lên**. Mỗi khu có tòa hỗn hợp (khối đế: shophouse, văn phòng, phòng khám, trường mầm non), shophouse thấp tầng, tiện ích có bãi riêng và bãi công cộng. Cư dân thường **đi lại giữa các khu**. Mỗi tòa có 3 loại chỗ: **TH1**, **TH2**, **TH3** ([PRD §4](02-prd.md#4-phân-loại-chỗ-đỗ-và-phạm-vi-mở)). Cấu trúc: [PRD §2](02-prd.md#2-mô-hình-tổ-chức).

## 2. Vấn đề

| # | Vấn đề | Giải thích |
|---|--------|------------|
| P1 | Lệch cung–cầu ban ngày | Chỗ cư dân trống khi đi làm; shophouse, văn phòng, phòng khám, trường thiếu chỗ. |
| P2 | Lệch cung–cầu ban đêm, cuối tuần, lễ Tết | Chỗ văn phòng và của người về quê trống; người thuê căn hộ, người thân thiếu chỗ. |
| P3 | Chủ chỗ ngại chia sẻ | Sợ **về sớm mất chỗ** và sợ **tranh chấp**, nên thà để trống. |
| P4 | Chỗ đỗ không hợp xe | Xe lớn như SUV ở chỗ hẹp, thường lấn vạch, ảnh hưởng chỗ bên cạnh. |
| P5 | Tranh chấp thủ công | BQL xử lý **thủ công**, **thiếu bằng chứng** (ai đỗ, lúc nào, có quyền không). |
| P6 | Nhu cầu liên khu bị bỏ ngỏ | Người có tài sản hoặc việc ở khu khác (chủ shophouse, phụ huynh, người đi khám) không có quyền; phải gửi bãi công cộng giá khách hoặc đỗ lòng đường. |
| P7 | Tư cách không rõ ràng | Mỗi khu giữ danh sách riêng; người thuê hết hợp đồng vẫn dùng quyền. BQL không chắc ai thuê loại chỗ nào, ở đâu. |
| P8 | Không điều phối giữa các khu | Chưa có cách điều phối cung–cầu theo giờ giữa các khu. |

## 3. Ai cần thuê chỗ, vì sao?

| Người thuê | Lý do · khung giờ | Thuê ở đâu, tư cách |
|-----------|-------------------|---------------------|
| Chủ shophouse khu A, ở căn hộ khu B | Mở hàng, nhập hàng · 7h–19h, ngày thường | Khu A — thành viên khu |
| Nhân viên shophouse, văn phòng, phòng khám | Đi làm · giờ hành chính | Khu làm việc — nhân viên đơn vị |
| Cư dân khu B đưa con đến trường ở khu C | Đưa đón · 7h–8h, 16h30–17h30 | Khu C — thành viên chuỗi |
| Cư dân đi khám, gym, TTTM khu khác | Tiện ích · 1–3 giờ/lượt | Khu đến — thành viên chuỗi (thường TH3 giá ưu đãi) |
| Người thuê căn hộ không có chỗ; hộ có xe thứ hai | Qua đêm · 18h–7h | Tòa mình ở — thành viên tòa |
| Người thân thăm dài ngày (lễ Tết) | Khách cư dân · vài ngày | Chỗ chủ nhà (miễn phí) hoặc TH3 |
| Khách vãng lai, khách shophouse | Theo lượt | TH3 / bãi công cộng (shophouse có thể cấp voucher) |

**Bên cho thuê**: cư dân đi làm cả ngày; chủ căn hộ cho thuê lại nhưng giữ chỗ; người về quê dịp Tết; văn phòng trống ban đêm, cuối tuần; chủ đầu tư qua TH2.

## 4. Giải pháp đề xuất

Một **Agent** điều phối quyền sử dụng chỗ đỗ trên toàn chuỗi. Mỗi người **một tài khoản** cho cả chuỗi, nhiều **tư cách** gắn với tài sản. Agent có 6 năng lực ([PRD §6](02-prd.md#6-yêu-cầu-chức-năng)):

1. **Xác định tư cách**: tại khu có chỗ, lấy tư cách mạnh nhất (tòa > khu > chuỗi > khách).
2. **Định tuyến**: ghép TH1/TH2 theo tư cách và phạm vi mở, hoặc TH3 / bãi công cộng.
3. **Chia sẻ**: khung giờ, khoảng dự phòng, ghép cung–cầu, thỏa thuận điện tử, sổ cái.
4. **Ngoại lệ**: chủ về sớm, quá giờ; khi khu hết chỗ, gợi ý khu lân cận.
5. **Tranh chấp**: bằng chứng, ticket (biển số ẩn), chuyển BQL khu xác minh.
6. **Hoán đổi**: đề xuất 2 bên hoặc theo chuỗi trong một khu; BQL khu phê duyệt.

**Ví dụ** (chủ shophouse khu A, căn hộ khu B): ở khu A là thành viên khu, thuê TH1/TH2 nếu phạm vi mở cho phép, nhưng **không** có quyền chỉ dành cho chủ căn hộ (biểu quyết nội quy tòa, khách đỗ miễn phí). Ở khu B là thành viên tòa, chia sẻ TH1 của mình. Ở khu khác là thành viên chuỗi, thuê TH2 nếu pool mở cho chuỗi, dùng TH3 giá thành viên. Shophouse ở khối đế thì chủ cũng là thành viên tòa đó. Chi tiết: [PRD §3.2](02-prd.md#32-cấp-tư-cách-tại-vị-trí-chỗ-đỗ).

**Demo**: 1 chuỗi 3 khu (A, B, C), dữ liệu mô phỏng, có VietQR mock và voucher shophouse. Để sau: bãi riêng, thanh toán thật, MoMo/ZaloPay. Xem [Scope](03-scope.md).

## 5. Đối tượng

Bên cung cấp chỗ, bên cần chỗ (theo **tư cách tại khu có chỗ**), bên phê duyệt: [PRD §3](02-prd.md#3-đối-tượng-người-dùng-và-tư-cách).

## 6. Giá trị mang lại

| Bên | Lợi ích |
|-----|---------|
| **Chủ chỗ** | Thu khoảng **1 triệu/tháng** *(giả định)*, bù **30–70%** phí gửi xe; **bảo đảm quyền quay về**. |
| **Người thuê** | Khoảng **50k/ngày**, rẻ hơn gửi ngoài (**20–70k/giờ**), đỗ ngay tại khu cần đến. |
| **BQL, đơn vị vận hành chuỗi** | Phí dịch vụ, ít tranh chấp, biết ai dùng chỗ nào, điều phối cung–cầu liên khu. |

## 7. Chỉ số thành công (KPI)

| KPI | Mục tiêu |
|-----|----------|
| Số giờ chỗ đỗ được khai thác thêm (theo khu và toàn chuỗi) | TBD |
| Tỷ lệ ghép thành công | TBD |
| Tỷ lệ yêu cầu liên khu được đáp ứng | TBD |
| Tỷ lệ xung đột khi chủ về | TBD |
| Thời gian lập hồ sơ tranh chấp | TBD |
| Số giao dịch sai tư cách hoặc sai phạm vi bị chặn | TBD |
| Tỷ lệ tranh chấp lặp lại sau khi hoán đổi | TBD |

> Baseline và mục tiêu chưa được xác định trong tài liệu nguồn.

## 8. Nguyên tắc vận hành và dữ liệu

- **Ai quyết định**: rule engine quyết định quyền thuê và phí; Agent chỉ đề xuất; BQL khu có chỗ đỗ duyệt tranh chấp, hoán đổi, giao dịch vượt ngưỡng.
- **Tư cách và LPR**: BQL khu có tài sản xác minh tư cách ([PRD §3.1](02-prd.md#31-tài-khoản-và-tư-cách)); log trùng bỏ qua, OCR thấp cần người kiểm tra ([PRD §5](02-prd.md#5-quy-tắc-nghiệp-vụ)).
- **Biển số, quyền riêng tư**: [Scope §3–5](03-scope.md#3-nguyên-tắc-dữ-liệu-và-quyền-riêng-tư).
