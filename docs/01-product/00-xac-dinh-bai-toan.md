# Bài toán: Agent điều phối quyền sử dụng chỗ đỗ trong khu đô thị

> **File này trả lời:** đề bài gốc là gì? Mọi tài liệu trong `01-product/` suy ra từ file này.
> Liên quan: [Project Brief](01-project-brief.md) · [PRD](02-prd.md) · [Scope](03-scope.md)

## 1. Bối cảnh

Khu đô thị lớn gồm tòa hỗn hợp (căn hộ; shophouse, văn phòng, phòng khám ở tầng đế), trường, bệnh viện, tòa văn phòng,
trung tâm thương mại có bãi riêng, và bãi công cộng nội khu. Mỗi tòa có hầm riêng với 3 loại chỗ ([PRD §4](02-prd.md#4-phân-loại-chỗ-đỗ-và-phạm-vi-mở)):

| Loại | Quy tắc |
|------|---------|
| **TH1** | Chỗ cư dân đã mua; cho thuê, **chỉ cho cư dân hoặc người sử dụng tòa nhà**. |
| **TH2** | Chỗ thuê từ chủ đầu tư; cho thuê lại khi chủ đầu tư đồng ý, **một lần cho cả pool**. |
| **TH3** | Chỗ công cộng / chỗ khách; BQL khai thác, cá nhân **không được** cho thuê. |

## 2. Vấn đề

- **Ban ngày:** chỗ cư dân trống; shophouse, văn phòng, phòng khám trong tòa thiếu chỗ.
- **Ban đêm, cuối tuần, Tết:** chỗ văn phòng và của người về quê trống; người thuê căn hộ, người thân thiếu chỗ.
- **Chủ chỗ** không dám chia sẻ: sợ về sớm mất chỗ, sợ tranh chấp. **Chỗ không hợp xe:** SUV ở chỗ hẹp, lấn vạch.
- **BQL** xử lý tranh chấp thủ công, thiếu bằng chứng.

## 3. Đối tượng

| Nhóm | Thành phần |
|------|-----------|
| **Cung cấp chỗ** | Cư dân có TH1, TH2; văn phòng có chỗ riêng. |
| **Cần chỗ, thuê chỗ riêng** | Cư dân không có chỗ; người thuê căn hộ; hộ có xe thứ hai; chủ và nhân viên shophouse; văn phòng, phòng khám, mầm non tầng đế. |
| **Cần chỗ, chỉ TH3 / bãi công cộng** | Khách vãng lai, khách shophouse, phụ huynh, người nhà bệnh nhân, nhân viên tòa văn phòng độc lập. |
| **Quản lý, phê duyệt** | Chủ đầu tư, BQL, Ban quản trị, Hội nghị nhà chung cư, đơn vị trông giữ xe. |

## 4. Giả định pháp lý

- Hội nghị nhà chung cư đã thông qua nội quy chia sẻ: trong phạm vi mở nội quy cho phép (mặc định nội bộ tòa; mở theo khu / chuỗi khi
  cấu hình, A-01), qua nền tảng chính thức, có khung giá và mẫu thỏa thuận.
- Chủ đầu tư đã chấp thuận chia sẻ toàn bộ TH2. Cư dân đồng ý xử lý biển số, ảnh khi đăng ký; chỉ cho khách đỗ khi không thu phí; khách shophouse sang TH3.

## 5. Agent làm gì

| Năng lực | Nội dung |
|----------|----------|
| **1. Định tuyến** | Đủ điều kiện thuê riêng thì ghép TH1 / TH2; không đủ thì chuyển TH3 hoặc bãi công cộng. |
| **2. Chia sẻ** | Đề xuất khung giờ, giữ dự phòng, ghép cung–cầu, sinh thỏa thuận điện tử để hai bên xác nhận, lưu bằng chứng xác nhận. |
| **3. Ngoại lệ** | Chủ về sớm: chỗ thay thế từ pool TH3. Quá giờ: nhắc và tính phí theo nội quy. |
| **4. Tranh chấp** | Đọc ảnh, đối chiếu bằng chứng xác nhận và dữ liệu cổng, lập ticket biển số ẩn, chuyển BQL xác minh. |
| **5. Hoán đổi** | Từ tranh chấp lặp lại hoặc nhu cầu đã đăng ký: hoán đổi 2 bên hoặc nhiều bên theo vòng, cùng khu; BQL duyệt. |

## 6. Lợi ích và hợp đồng

- **Chủ chỗ:** ~1 triệu/tháng (giả định), bù 30–70% phí gửi xe, bảo đảm quyền quay về · **Người thuê:** ~50k/ngày, rẻ hơn gửi ngoài (20–70k/giờ) ·
  **BQL, chủ đầu tư:** phí dịch vụ, ít tranh chấp, không lập giấy tờ từng lượt.
- **Hợp đồng:** khách theo lượt = vé / biên lai điện tử; vé tháng = hợp đồng một lần (BQL lập); cư dân chia sẻ = thỏa thuận điện tử
  theo mẫu, Agent sinh, hai bên xác nhận, BQL ghi nhận.

## 7. KPI

Giờ chỗ đỗ khai thác thêm · tỷ lệ ghép thành công · tỷ lệ xung đột khi chủ về · thời gian lập hồ sơ tranh chấp · giao dịch sai đối tượng
bị chặn · tỷ lệ tranh chấp lặp lại sau hoán đổi. Mục tiêu: [Project Brief §7](01-project-brief.md#7-chỉ-số-thành-công-kpi).
