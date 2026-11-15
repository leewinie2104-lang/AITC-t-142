# Scope — Agent điều phối quyền sử dụng chỗ đỗ

> Nguồn: [01-xac-dinh-bai-toan.md](../01-xac-dinh-bai-toan.md)
> Liên quan: [Project Brief](project-brief.md) · [PRD](prd.md)

## 1. Trong phạm vi (In Scope)

| Hạng mục | Tham chiếu |
|----------|-----------|
| Định tuyến người yêu cầu vào TH1/TH2 hoặc TH3/bãi công cộng | [PRD §5.1](prd.md#51-định-tuyến) |
| Chia sẻ chỗ TH1/TH2 trong nội bộ tòa nhà: đề xuất khung giờ, dự phòng, ghép cung–cầu, thỏa thuận điện tử, sổ cái | [PRD §5.2](prd.md#52-chia-sẻ) |
| Xử lý ngoại lệ: chủ về sớm, người thuê đỗ quá giờ | [PRD §5.3](prd.md#53-xử-lý-ngoại-lệ) |
| Hỗ trợ tranh chấp: thu thập bằng chứng, lập ticket ẩn biển số, chuyển BQL | [PRD §5.4](prd.md#54-tranh-chấp) |
| Đề xuất hoán đổi chỗ (2 bên / theo chuỗi), BQL phê duyệt | [PRD §5.5](prd.md#55-hoán-đổi) |
| Hầm riêng của từng tòa chung cư hỗn hợp (TH1, TH2, TH3) | [PRD §3](prd.md#3-phân-loại-chỗ-đỗ) |

## 2. Ngoài phạm vi (Out of Scope)

Các hạng mục bị loại trừ bởi quy tắc trong tài liệu nguồn:

- Chia sẻ chỗ **ra ngoài nội bộ tòa nhà** hoặc **ngoài nền tảng chính thức**.
- Cá nhân cho thuê chỗ **TH3**.
- Cư dân **thu phí** khi cho khách của mình đỗ.
- Cho thuê chỗ TH1 cho đối tượng không phải cư dân / người sử dụng tòa nhà.
- Agent tự quyết định kết quả tranh chấp hoặc tự thực hiện hoán đổi (BQL xác minh / phê duyệt).

## 3. Chưa xác định (TBD)

- Bãi xe riêng của **trường học, bệnh viện, tòa văn phòng, trung tâm thương mại** — có thuộc phạm vi điều phối không: **TBD**.
- **Bãi công cộng nội khu** — Agent chỉ chuyển hướng hay quản lý chỗ trống/đặt chỗ: **TBD**.
- Phát hành vé theo lượt / vé tháng (do BQL lập) — có thuộc chức năng Agent không: **TBD**.
- Ghép chỗ theo kích thước xe (vấn đề SUV ở chỗ hẹp) — nêu trong vấn đề nhưng chưa có chức năng tương ứng rõ ràng: **TBD**.
- Thanh toán / thu phí trên nền tảng: **TBD**.

## 4. Giả định

| ID | Giả định pháp lý / nghiệp vụ |
|----|------------------------------|
| A-01 | Hội nghị nhà chung cư đã thông qua nội quy chia sẻ: chỉ trong nội bộ tòa nhà, qua nền tảng chính thức, có khung giá và mẫu thỏa thuận. |
| A-02 | Chủ đầu tư đã chấp thuận cho chia sẻ toàn bộ chỗ TH2. |
| A-03 | Cư dân đồng ý cho xử lý biển số và ảnh khi đăng ký app. |
| A-04 | Cư dân chỉ được cho khách của chính mình đỗ khi không thu phí; khách của shophouse được chuyển sang TH3. |
| A-05 | Thu nhập chủ chỗ ~1 triệu/tháng là con số giả định. |

## 5. Ràng buộc

- Mọi giao dịch chia sẻ phải tuân theo khung giá và mẫu thỏa thuận của nội quy.
- Chủ chỗ luôn được bảo đảm quyền quay về.
- Biển số phải được ẩn trong ticket tranh chấp.

## 6. Phụ thuộc

- **Dữ liệu cổng** (đối chiếu tranh chấp) — nguồn/hệ thống tích hợp: TBD.
- **Sổ cái** giao dịch — công nghệ/hình thức: TBD.
- **Ảnh** làm bằng chứng — nguồn (camera, người dùng chụp…): TBD.
- **App / nền tảng chính thức** — nơi cư dân đăng ký và đồng ý xử lý dữ liệu.
