# Project Brief — Agent điều phối quyền sử dụng chỗ đỗ trong chuỗi khu đô thị

> **File này trả lời:** vì sao cần sản phẩm, vấn đề nào cần giải, ai được lợi, đo bằng gì?
> Nguồn: [Bài toán](00-xac-dinh-bai-toan.md) · Liên quan: [PRD](02-prd.md) · [Scope](03-scope.md) · [User Stories](04-user-stories.md) · [User Flow](ux/01-user-flow.md)

## 1. Bối cảnh

Chủ đầu tư vận hành **chuỗi ≥ 2 khu đô thị**. Mỗi khu có tòa hỗn hợp (khối đế: shophouse, văn phòng, phòng khám, mầm non),
shophouse thấp tầng, tiện ích có bãi riêng, bãi công cộng; cư dân **đi lại giữa các khu**. Mỗi tòa có chỗ **TH1, TH2, TH3**
([PRD §4](02-prd.md#4-phân-loại-chỗ-đỗ-và-phạm-vi-mở)); cấu trúc: [PRD §2](02-prd.md#2-mô-hình-tổ-chức).

## 2. Vấn đề

| # | Vấn đề | Giải thích |
|---|--------|------------|
| P1 | Lệch cung–cầu ban ngày | Chỗ cư dân trống khi đi làm; shophouse, văn phòng, phòng khám, trường thiếu chỗ. |
| P2 | Lệch ban đêm, cuối tuần, Tết | Chỗ văn phòng, người về quê trống; người thuê căn hộ, người thân thiếu chỗ. |
| P3 | Chủ chỗ ngại chia sẻ | Sợ **về sớm mất chỗ** và **tranh chấp**, thà để trống. |
| P4 | Chỗ không hợp xe | SUV ở chỗ hẹp, lấn vạch. |
| P5 | Tranh chấp thủ công | BQL **thiếu bằng chứng** (ai đỗ, lúc nào, có quyền không). |
| P6 | Nhu cầu liên khu bỏ ngỏ | Chủ shophouse, phụ huynh, người đi khám ở khu khác không có quyền; gửi bãi giá khách hoặc đỗ lòng đường. |
| P7 | Tư cách không rõ | Mỗi khu giữ danh sách riêng; người thuê hết hợp đồng vẫn dùng quyền. |
| P8 | Không điều phối giữa các khu | Chưa điều phối cung–cầu theo giờ giữa các khu. |

## 3. Ai cần thuê chỗ, vì sao?

- Chủ shophouse khu A ở khu B (7h–19h, khu A, thành viên khu)
- Nhân viên shophouse / văn phòng / phòng khám (giờ hành chính)
- Phụ huynh khu B đưa con sang khu C (7h–8h, 16h30–17h30, thành viên chuỗi)
- Cư dân đi khám, gym ở khu khác (1–3 giờ, thường TH3)
người thuê căn hộ không có chỗ, hộ xe thứ hai (18h–7h, thành viên tòa)
- Người thân dịp Tết (chỗ chủ nhà miễn phí hoặc TH3)
khách vãng lai, khách shophouse (TH3 / bãi công cộng)
 
**Bên cho thuê:** cư dân đi làm cả ngày, chủ căn hộ cho thuê lại nhưng giữ chỗ,
người về quê dịp Tết, văn phòng trống ban đêm, chủ đầu tư qua TH2.

## 4. Giải pháp đề xuất

Một **Agent** điều phối trên toàn chuỗi; mỗi người **một tài khoản**, nhiều **tư cách** gắn tài sản. 6 năng lực ([PRD §6](02-prd.md#6-yêu-cầu-chức-năng)):
- **Xác định tư cách** (mạnh nhất tại khu có chỗ: tòa > khu > chuỗi > khách)
- **Định tuyến** (TH1/TH2 theo phạm vi mở, hoặc TH3 / bãi công cộng)
- **Chia sẻ** (khung giờ, dự phòng, ghép, thỏa thuận, bằng chứng xác nhận)
- **Ngoại lệ** (chủ về sớm, quá giờ, gợi ý khu lân cận)
- **Tranh chấp** (bằng chứng, ticket biển số ẩn) · **hoán đổi** (2 bên hoặc theo vòng A→B→C→A trong một khu, BQL duyệt).

**Ví dụ:** chủ shophouse thấp tầng khu A có căn hộ khu B: khu A là thành viên khu (không có quyền riêng của chủ căn hộ), khu B là thành viên tòa,
khu khác là thành viên chuỗi ([PRD §3.2](02-prd.md#32-cấp-tư-cách-tại-vị-trí-chỗ-đỗ)).

**Demo:** 1 chuỗi, seed 3 khu, kịch bản ≥ 2 khu, dữ liệu mô phỏng; phạm vi 4 tuần ở [Backlog](05-backlog.md) và [Scope](03-scope.md).

## 5. Đối tượng và giá trị mang lại

Đối tượng theo **tư cách tại khu có chỗ**: [PRD §3](02-prd.md#3-đối-tượng-người-dùng-và-tư-cách). 
- **Chủ chỗ:** ~**1 triệu/tháng** *(giả định)*, bù **30–70%** phí gửi xe, **bảo đảm quyền quay về**
- **Người thuê:** ~**50k/ngày**, rẻ hơn
gửi ngoài (**20–70k/giờ**) · **BQL, vận hành chuỗi:** phí dịch vụ, ít tranh chấp, biết ai dùng chỗ nào, điều phối liên khu.

## 6. Chỉ số thành công (KPI)

Theo khu và toàn chuỗi; **baseline và mục tiêu: TBD** (chưa có trong nguồn):
- Giờ chỗ đỗ khai thác thêm 
- Tỷ lệ ghép thành công
- tỷ lệ yêu cầu liên khu được đáp ứng · tỷ lệ xung đột khi chủ về · thời gian lập hồ sơ tranh chấp · giao dịch sai tư cách / phạm vi bị chặn ·
tỷ lệ tranh chấp lặp lại sau hoán đổi.

## 7. Nguyên tắc vận hành và dữ liệu

Rule engine quyết định quyền thuê và phí; Agent chỉ đề xuất; BQL khu có chỗ duyệt tranh chấp, hoán đổi, vượt ngưỡng. BQL khu có tài sản
xác minh tư cách ([PRD §3.1](02-prd.md#31-tài-khoản-và-tư-cách)); log trùng bỏ qua, OCR thấp cần người kiểm tra. Riêng tư: [Scope §3–5](03-scope.md#3-nguyên-tắc-dữ-liệu-và-quyền-riêng-tư).
