# Acceptance Criteria — Agent điều phối quyền sử dụng chỗ đỗ

> Nguồn: [01-xac-dinh-bai-toan.md](../01-xac-dinh-bai-toan.md)
> Liên quan: [User Stories](user-stories.md) · [PRD §4 Quy tắc nghiệp vụ](prd.md#4-quy-tắc-nghiệp-vụ)

Định dạng Given / When / Then. Các ngưỡng số chưa có trong nguồn được đánh dấu **TBD**.

## Epic 1 — Định tuyến

**AC-01 (US-01)** — Ghép chỗ riêng
- **Given** người yêu cầu thuộc nhóm "được thuê chỗ riêng"
- **When** gửi yêu cầu chỗ đỗ
- **Then** Agent ghép vào chỗ TH1 hoặc TH2 còn trống trong cùng tòa nhà.
- Tiêu chí ưu tiên giữa TH1 và TH2: TBD.

**AC-02 (US-02)** — Chuyển TH3 / bãi công cộng
- **Given** người yêu cầu thuộc nhóm "chỉ dùng TH3/bãi công cộng" (bao gồm khách shophouse)
- **When** gửi yêu cầu chỗ đỗ
- **Then** Agent không ghép vào TH1/TH2 mà chuyển sang TH3 hoặc bãi công cộng.

**AC-03 (US-03)** — Chặn giao dịch sai đối tượng
- **Then** Agent từ chối và ghi nhận (tính vào KPI "số giao dịch sai đối tượng bị chặn") khi:
  - chỗ TH1 được cho thuê cho người không phải cư dân / người sử dụng tòa nhà (BR-01);
  - cá nhân cố cho thuê chỗ TH3 (BR-03);
  - giao dịch ngoài nội bộ tòa nhà hoặc ngoài nền tảng chính thức (BR-04);
  - cư dân thu phí khi cho khách của mình đỗ (BR-05).

## Epic 2 — Chia sẻ

**AC-04 (US-04)** — Đề xuất khung giờ
- **Given** chủ chỗ TH1/TH2 hoặc văn phòng có chỗ riêng
- **Then** Agent đề xuất khung giờ có thể chia sẻ. Cơ sở dữ liệu để đề xuất: TBD.

**AC-05 (US-05)** — Khoảng dự phòng
- **Then** mỗi khung giờ chia sẻ có kèm một khoảng dự phòng. Độ dài khoảng dự phòng: TBD.

**AC-06 (US-06)** — Ghép cung–cầu
- **Then** người cần chỗ chỉ được ghép với chỗ chia sẻ hợp lệ theo AC-01 và AC-03.

**AC-07 (US-07)** — Thỏa thuận điện tử
- **When** ghép thành công
- **Then** Agent sinh thỏa thuận điện tử theo mẫu nội quy, áp dụng khung giá nội quy
- **And** thỏa thuận chỉ có hiệu lực khi **cả hai bên** xác nhận.

**AC-08 (US-08)** — Sổ cái
- **When** hai bên đã xác nhận
- **Then** giao dịch được ghi vào sổ cái và BQL ghi nhận.

## Epic 3 — Xử lý ngoại lệ

**AC-09 (US-09, US-10)** — Chủ về sớm
- **Given** chỗ đang được người thuê sử dụng theo thỏa thuận
- **When** chủ chỗ về sớm
- **Then** chủ được quay về chỗ của mình
- **And** Agent điều phối chỗ thay thế cho người thuê từ pool TH3.
- Trường hợp pool TH3 hết chỗ: TBD.

**AC-10 (US-11)** — Đỗ quá giờ
- **When** người thuê vẫn đỗ sau khi hết khung giờ thỏa thuận
- **Then** Agent gửi nhắc nhở cho người thuê
- **And** tính phí theo nội quy. Mức phí và thời điểm bắt đầu tính: TBD.

## Epic 4 — Tranh chấp

**AC-11 (US-12)** — Lập ticket
- **When** có tranh chấp phát sinh
- **Then** Agent đọc ảnh, đối chiếu sổ cái và dữ liệu cổng, lập ticket và chuyển BQL xác minh.
- Thời gian lập hồ sơ mục tiêu: TBD.

**AC-12 (US-13)** — Ẩn biển số
- **Then** mọi biển số trong ticket hiển thị ở dạng đã ẩn. Quy cách ẩn và ai được xem bản gốc: TBD.

## Epic 5 — Hoán đổi

**AC-13 (US-14)** — Đề xuất hoán đổi
- **Given** tranh chấp lặp lại hoặc nhu cầu đã đăng ký
- **Then** Agent đề xuất hoán đổi giữa 2 bên hoặc theo chuỗi.
- Định nghĩa "lặp lại" (số lần / khoảng thời gian): TBD.

**AC-14 (US-15)** — Phê duyệt
- **Then** hoán đổi chỉ có hiệu lực sau khi BQL phê duyệt; đề xuất bị từ chối không thay đổi phân bổ chỗ.
