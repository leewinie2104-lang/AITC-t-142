# Project Brief — Agent điều phối quyền sử dụng chỗ đỗ trong khu đô thị

> Nguồn: [01-xac-dinh-bai-toan.md](../01-xac-dinh-bai-toan.md)
> Tài liệu liên quan: [PRD](prd.md) · [Scope](scope.md) · [User Stories](user-stories.md) · [Acceptance Criteria](acceptance-criteria.md) · [User Flow](ux/user-flow.md)

## 1. Bối cảnh

Khu đô thị lớn có nhiều tòa chung cư hỗn hợp: căn hộ, shophouse và văn phòng ở tầng đế. Ngoài ra có trường học, bệnh viện, tòa văn phòng và trung tâm thương mại với bãi xe riêng, cùng bãi công cộng nội khu.

Mỗi tòa có hầm riêng gồm 3 loại chỗ đỗ: **TH1** (chỗ cư dân đã mua), **TH2** (chỗ thuê từ chủ đầu tư), **TH3** (chỗ công cộng / chỗ khách do BQL khai thác). Định nghĩa và quy tắc chi tiết: xem [PRD §3](prd.md#3-phân-loại-chỗ-đỗ).

## 2. Vấn đề

| # | Vấn đề |
|---|--------|
| P1 | **Ban ngày**: chỗ của cư dân bỏ trống, trong khi shophouse, văn phòng và phòng khám trong tòa thiếu chỗ. |
| P2 | **Ban đêm, cuối tuần, lễ Tết**: chỗ của văn phòng và của người về quê bỏ trống, còn người thuê căn hộ và người thân đến thăm lại thiếu chỗ. |
| P3 | Chủ chỗ không dám chia sẻ vì **sợ về sớm mà mất chỗ** và **sợ tranh chấp**. |
| P4 | Nhiều người đỗ ở chỗ không hợp nhu cầu (ví dụ xe SUV ở chỗ hẹp nên thường lấn vạch). |
| P5 | BQL xử lý tranh chấp **thủ công** và **thiếu bằng chứng**. |

## 3. Giải pháp đề xuất

Một **Agent** điều phối quyền sử dụng chỗ đỗ với 5 năng lực:

1. **Định tuyến** — xác định người yêu cầu được thuê chỗ riêng (TH1/TH2) hay chuyển sang TH3/bãi công cộng.
2. **Chia sẻ** — đề xuất khung giờ chia sẻ, giữ dự phòng, ghép cung–cầu, sinh thỏa thuận điện tử, ghi sổ cái.
3. **Xử lý ngoại lệ** — chủ về sớm, người thuê đỗ quá giờ.
4. **Tranh chấp** — thu thập bằng chứng, lập ticket (biển số đã ẩn), chuyển BQL xác minh.
5. **Hoán đổi** — đề xuất hoán đổi 2 bên hoặc theo chuỗi, BQL phê duyệt.

Yêu cầu chức năng chi tiết: [PRD §5](prd.md#5-yêu-cầu-chức-năng).

## 4. Đối tượng (tóm tắt)

- **Bên cung cấp chỗ** — cư dân có chỗ TH1/TH2, văn phòng có chỗ riêng.
- **Bên cần chỗ (được thuê chỗ riêng)** — cư dân không có chỗ, người thuê căn hộ, hộ có xe thứ hai, shophouse, văn phòng, phòng khám, trường mầm non ở tầng đế.
- **Bên cần chỗ (chỉ dùng TH3/bãi công cộng)** — khách vãng lai, khách shophouse, phụ huynh, người nhà bệnh nhân, nhân viên tòa văn phòng độc lập.
- **Bên quản lý & phê duyệt** — chủ đầu tư, BQL, Ban quản trị, Hội nghị nhà chung cư, đơn vị trông giữ xe.

Danh sách đầy đủ: [PRD §2](prd.md#2-đối-tượng-người-dùng).

## 5. Giá trị mang lại

| Bên | Lợi ích |
|-----|---------|
| **Chủ chỗ** | Thu khoảng **1 triệu/tháng** *(giả định)*, bù **60–70%** phí gửi xe; vẫn được **bảo đảm quyền quay về**. |
| **Người thuê** | Khoảng **50k/ngày**, rẻ hơn gửi ngoài (**20–70k/giờ**), đỗ ngay trong tòa. |
| **BQL, chủ đầu tư** | Hưởng phí dịch vụ, ít tranh chấp, không phải lập giấy tờ cho từng lượt. |

## 6. Chỉ số thành công (KPI)

| KPI | Mục tiêu |
|-----|----------|
| Số giờ chỗ đỗ được khai thác thêm | TBD |
| Tỷ lệ ghép thành công | TBD |
| Tỷ lệ xung đột khi chủ về | TBD |
| Thời gian lập hồ sơ tranh chấp | TBD |
| Số giao dịch sai đối tượng bị chặn | TBD |
| Tỷ lệ tranh chấp lặp lại sau khi hoán đổi | TBD |

> Baseline và giá trị mục tiêu chưa được xác định trong tài liệu nguồn.
