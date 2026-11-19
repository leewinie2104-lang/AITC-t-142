# Bài toán: Agent điều phối quyền sử dụng chỗ đỗ trong khu đô thị

> **File này trả lời câu hỏi**: đề bài gốc là gì? Mọi tài liệu trong `01-product/` suy ra từ file này.

> Liên quan: [Project Brief](01-project-brief.md) · [PRD](02-prd.md) · [Scope](03-scope.md)

## 1. Bối cảnh

Khu đô thị lớn gồm tòa hỗn hợp (căn hộ; shophouse, văn phòng, phòng khám ở tầng đế), trường, bệnh viện, tòa văn phòng, trung tâm thương mại có bãi riêng, và bãi công cộng nội khu. Mỗi tòa có hầm riêng với 3 loại chỗ:

| Loại | Quy tắc |
|------|---------|
| **TH1** | Chỗ cư dân đã mua; cho thuê, **chỉ cho cư dân hoặc người sử dụng tòa nhà**. |
| **TH2** | Chỗ thuê từ chủ đầu tư; cho thuê lại khi chủ đầu tư đã đồng ý, **một lần cho cả pool**. |
| **TH3** | Chỗ công cộng hoặc chỗ khách; BQL khai thác, cá nhân **không được** cho thuê. |

Chi tiết: [PRD §4](02-prd.md#4-phân-loại-chỗ-đỗ-và-phạm-vi-mở).

## 2. Vấn đề

| Tình huống | Vấn đề |
|------------|--------|
| Ban ngày | Chỗ cư dân trống; shophouse, văn phòng, phòng khám trong tòa thiếu chỗ. |
| Ban đêm, cuối tuần, Tết | Chỗ văn phòng và của người về quê trống; người thuê căn hộ, người thân thiếu chỗ. |
| Chủ chỗ | Không dám chia sẻ: sợ về sớm mất chỗ, sợ tranh chấp. |
| Chỗ không hợp xe | Đỗ sai nhu cầu, ví dụ SUV ở chỗ hẹp nên thường lấn vạch. |
| BQL | Xử lý tranh chấp thủ công, thiếu bằng chứng. |

## 3. Đối tượng

| Nhóm | Thành phần |
|------|-----------|
| **Cung cấp chỗ** | Cư dân có TH1, TH2; văn phòng có chỗ riêng. |
| **Cần chỗ, thuê chỗ riêng** | Cư dân không có chỗ; người thuê căn hộ; hộ có xe thứ hai; chủ và nhân viên shophouse; văn phòng, phòng khám, trường mầm non ở tầng đế. |
| **Cần chỗ, chỉ TH3 hoặc bãi công cộng** | Khách vãng lai, khách shophouse, phụ huynh, người nhà bệnh nhân, nhân viên tòa văn phòng độc lập. |
| **Quản lý, phê duyệt** | Chủ đầu tư, BQL, Ban quản trị, Hội nghị nhà chung cư, đơn vị trông giữ xe. |

## 4. Giả định pháp lý

- Hội nghị nhà chung cư đã thông qua nội quy chia sẻ: chỉ trong nội bộ tòa nhà, qua nền tảng chính thức, có khung giá và mẫu thỏa thuận.
- Chủ đầu tư đã chấp thuận chia sẻ toàn bộ chỗ TH2.
- Cư dân đồng ý xử lý biển số và ảnh khi đăng ký app.
- Cư dân chỉ cho khách của mình đỗ khi không thu phí; khách shophouse chuyển sang TH3.

## 5. Agent làm gì

| Năng lực | Nội dung |
|----------|----------|
| **1. Định tuyến** | Đủ điều kiện thuê riêng thì ghép TH1 hoặc TH2; không đủ thì chuyển TH3 hoặc bãi công cộng. |
| **2. Chia sẻ** | Đề xuất khung giờ, giữ khoảng dự phòng, ghép cung–cầu, sinh thỏa thuận điện tử để hai bên xác nhận rồi lưu bằng chứng xác nhận. |
| **3. Ngoại lệ** | Chủ về sớm: điều phối chỗ thay thế từ pool TH3. Quá giờ: nhắc và tính phí theo nội quy. |
| **4. Tranh chấp** | Đọc ảnh, đối chiếu bằng chứng xác nhận và dữ liệu cổng, lập ticket với biển số ẩn, chuyển BQL xác minh. |
| **5. Hoán đổi** | Từ tranh chấp lặp lại hoặc nhu cầu đã đăng ký: đề xuất hoán đổi 2 bên hoặc theo chuỗi; BQL duyệt. |

## 6. Ai được lợi gì

| Bên | Lợi ích |
|-----|---------|
| **Chủ chỗ** | Thu khoảng 1 triệu/tháng (giả định), bù 60–70% phí gửi xe; vẫn được bảo đảm quyền quay về. |
| **Người thuê** | Khoảng 50k/ngày, rẻ hơn gửi ngoài (20–70k/giờ), đỗ ngay trong tòa. |
| **BQL, chủ đầu tư** | Phí dịch vụ, ít tranh chấp, không phải lập giấy tờ cho từng lượt. |

## 7. Hợp đồng

| Giao dịch | Hình thức | Ai lập |
|-----------|-----------|--------|
| Khách theo lượt | Vé hoặc biên lai điện tử | BQL |
| Vé tháng | Hợp đồng ký một lần | BQL |
| Cư dân chia sẻ cho nhau | Thỏa thuận điện tử theo mẫu | Agent sinh; hai bên xác nhận; BQL ghi nhận |

## 8. KPI

Số giờ chỗ đỗ được khai thác thêm · tỷ lệ ghép thành công · tỷ lệ xung đột khi chủ về · thời gian lập hồ sơ tranh chấp · số giao dịch sai đối tượng bị chặn · tỷ lệ tranh chấp lặp lại sau khi hoán đổi. Mục tiêu: [Project Brief §7](01-project-brief.md#7-chỉ-số-thành-công-kpi).
