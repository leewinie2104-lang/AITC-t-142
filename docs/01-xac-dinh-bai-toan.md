# Bài toán: Agent điều phối quyền sử dụng chỗ đỗ trong khu đô thị

## Bối cảnh

Khu đô thị lớn có nhiều tòa chung cư hỗn hợp: căn hộ, shophouse và văn phòng ở tầng đế. Ngoài ra có trường học, bệnh viện, tòa văn phòng và trung tâm thương mại với bãi xe riêng, cùng bãi công cộng nội khu.

Mỗi tòa có hầm riêng, gồm 3 loại chỗ:

- **TH1:** chỗ cư dân đã mua. Được cho thuê, nhưng **chỉ cho cư dân hoặc người sử dụng tòa nhà**.

- **TH2:** chỗ thuê từ chủ đầu tư. Được cho thuê lại khi chủ đầu tư đã đồng ý, chỉ cần đồng ý một lần cho cả pool.

- **TH3:** chỗ công cộng hoặc chỗ khách. Do BQL khai thác, cá nhân không được cho thuê.

## Vấn đề

Ban ngày chỗ của cư dân bỏ trống, trong khi shophouse, văn phòng và phòng khám trong tòa thiếu chỗ.

Ban đêm, cuối tuần, dịp lễ Tết thì ngược lại: chỗ của văn phòng và của người về quê bỏ trống, còn người thuê căn hộ và người thân đến thăm lại thiếu chỗ.

Chủ chỗ không dám chia sẻ vì sợ về sớm mà mất chỗ, và sợ xảy ra tranh chấp.

Nhiều người đang đỗ ở chỗ không hợp với nhu cầu của mình, ví dụ xe SUV ở chỗ hẹp nên thường lấn vạch.

BQL xử lý tranh chấp thủ công và thiếu bằng chứng.

## Đối tượng

**Bên cung cấp chỗ:** cư dân có chỗ TH1, TH2; văn phòng có chỗ riêng.

**Bên cần chỗ, được thuê chỗ riêng:** cư dân không có chỗ, người thuê căn hộ, hộ có xe thứ hai, chủ shophouse và nhân viên, văn phòng, phòng khám, trường mầm non ở tầng đế.

**Bên cần chỗ, chỉ được dùng TH3 hoặc bãi công cộng:** khách vãng lai, khách của shophouse, phụ huynh, người nhà bệnh nhân, nhân viên ở tòa văn phòng độc lập.

**Bên quản lý và phê duyệt:** chủ đầu tư, BQL, Ban quản trị, Hội nghị nhà chung cư, đơn vị trông giữ xe.

## Giả định pháp lý

Hội nghị nhà chung cư đã thông qua nội quy chia sẻ: chỉ trong nội bộ tòa nhà, qua nền tảng chính thức, có khung giá và mẫu thỏa thuận.

Chủ đầu tư đã chấp thuận cho chia sẻ toàn bộ chỗ TH2.

Cư dân đồng ý cho xử lý biển số và ảnh khi đăng ký app.

Cư dân chỉ được cho khách của chính mình đỗ khi không thu phí. Khách của shophouse được chuyển sang TH3.

## Agent làm gì

**1. Định tuyến:** kiểm tra người yêu cầu có đủ điều kiện thuê chỗ riêng không. Nếu đủ thì ghép vào TH1 hoặc TH2, nếu không thì chuyển sang TH3 hoặc bãi công cộng.

**2. Chia sẻ:** đề xuất khung giờ có thể chia sẻ, giữ một khoảng dự phòng, ghép cung với cầu, tự sinh thỏa thuận điện tử để hai bên xác nhận, rồi ghi vào sổ cái.

**3. Xử lý ngoại lệ:** khi chủ về sớm, Agent điều phối chỗ thay thế từ pool TH3. Khi người thuê đỗ quá giờ, Agent nhắc và tính phí theo nội quy.

**4. Tranh chấp:** đọc ảnh, đối chiếu sổ cái và dữ liệu cổng, lập ticket với biển số đã được ẩn, chuyển BQL xác minh.

**5. Hoán đổi:** từ những tranh chấp lặp lại hoặc nhu cầu đã đăng ký, Agent đề xuất hoán đổi 2 bên hoặc theo chuỗi, và BQL phê duyệt.

## Ai được lợi gì

**•** **Chủ chỗ:** thu khoảng 1 triệu/tháng (giả định), bù 60–70% phí gửi xe, vẫn được bảo đảm quyền quay về.

**•** **Người thuê:** khoảng 50k/ngày, rẻ hơn gửi ngoài (20–70k/giờ) và đỗ ngay trong tòa.

**•** **BQL, chủ đầu tư:** hưởng phí dịch vụ, ít tranh chấp, không phải lập giấy tờ cho từng lượt.

## Hợp đồng

| Giao dịch               | Hình thức                   | Ai lập                 a                    |
| ----------------------- | --------------------------- | ------------------------------------------ |
| Khách theo lượt         | Vé hoặc biên lai điện tử    | BQL                                        |
| Vé tháng                | Hợp đồng ký một lần         | BQL                                        |
| Cư dân chia sẻ cho nhau | Thỏa thuận điện tử theo mẫu | Agent sinh, hai bên xác nhận, BQL ghi nhận |

## KPI

Số giờ chỗ đỗ được khai thác thêm, tỷ lệ ghép thành công, tỷ lệ xung đột khi chủ về, thời gian lập hồ sơ tranh chấp, số giao dịch sai đối tượng bị chặn, tỷ lệ tranh chấp lặp lại sau khi hoán đổi.
