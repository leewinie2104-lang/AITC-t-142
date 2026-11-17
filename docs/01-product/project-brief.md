# Project Brief — Agent điều phối quyền sử dụng chỗ đỗ trong chuỗi khu đô thị

> Nguồn: [01-xac-dinh-bai-toan.md](../01-xac-dinh-bai-toan.md)
> Tài liệu liên quan: [PRD](prd.md) · [Scope](scope.md) · [User Stories](user-stories.md) · [Acceptance Criteria](acceptance-criteria.md) · [User Flow](ux/user-flow.md)

## 1. Bối cảnh

Một chủ đầu tư phát triển và vận hành một **chuỗi gồm nhiều khu đô thị** (từ 2 khu trở lên) trong cùng thành phố. Mỗi khu đô thị là một quần thể lớn, chia thành nhiều **phân khu**, gồm:

- **Tòa chung cư hỗn hợp**: căn hộ ở các tầng trên; shophouse, văn phòng, phòng khám, trường mầm non ở **khối đế**.
- **Shophouse / nhà phố thấp tầng** dọc các trục phố của khu.
- **Tiện ích dùng chung**: trường liên cấp, bệnh viện / phòng khám, trung tâm thương mại, tòa văn phòng, clubhouse. Các tiện ích này có bãi xe riêng.
- **Bãi công cộng nội khu** do Ban quản lý (BQL) khu khai thác.

Cư dân thường **di chuyển giữa các khu** trong chuỗi: ở khu này, kinh doanh hoặc làm việc ở khu khác, đưa con đến trường ở khu thứ ba, cuối tuần đi trung tâm thương mại ở khu thứ tư.

Mỗi tòa có hầm riêng với 3 loại chỗ đỗ: **TH1** (chỗ cư dân đã mua), **TH2** (chỗ thuê từ chủ đầu tư) và **TH3** (chỗ công cộng / chỗ khách do BQL khai thác). Định nghĩa, quy tắc và **phạm vi mở** của từng loại: xem [PRD §4](prd.md#4-phân-loại-chỗ-đỗ-và-phạm-vi-mở).

Cấu trúc tổ chức: **Chuỗi → Khu đô thị → Phân khu → Tòa / cụm shophouse / bãi**. Chi tiết: [PRD §2](prd.md#2-mô-hình-tổ-chức).

## 2. Vấn đề

| # | Vấn đề |
|---|--------|
| P1 | **Ban ngày**: chỗ của cư dân bỏ trống, trong khi shophouse, văn phòng, phòng khám và trường học lại thiếu chỗ. |
| P2 | **Ban đêm, cuối tuần, lễ Tết**: chỗ của văn phòng và của người về quê bỏ trống, còn người thuê căn hộ và người thân đến thăm lại thiếu chỗ. |
| P3 | Chủ chỗ không dám chia sẻ vì **sợ về sớm mà mất chỗ** và **sợ tranh chấp**. |
| P4 | Nhiều người đỗ ở chỗ không hợp nhu cầu (ví dụ xe SUV ở chỗ hẹp nên thường lấn vạch). |
| P5 | BQL xử lý tranh chấp **thủ công** và **thiếu bằng chứng**. |
| P6 | **Nhu cầu liên khu không được phục vụ**: người có tài sản hoặc công việc ở khu khác (chủ shophouse, phụ huynh, người đi khám) không có quyền gì ở khu đến. Họ phải gửi bãi công cộng với giá khách hoặc đỗ dưới lòng đường. |
| P7 | **Tư cách không rõ ràng**: một người có thể có tài sản ở nhiều khu, mỗi khu lại giữ danh sách cư dân riêng. Người thuê căn hộ đã hết hợp đồng vẫn tiếp tục dùng quyền. BQL không biết chắc ai được thuê loại chỗ nào, ở đâu. |
| P8 | **Cung và cầu lệch giữa các khu theo giờ**: khu nhiều trường học và văn phòng thì trống chỗ ban đêm, khu thuần ở thì trống chỗ ban ngày. Hiện chưa có cách điều phối giữa các khu. |

## 3. Ai cần thuê chỗ, vì sao?

| Người thuê | Lý do | Khung giờ điển hình | Thuê ở đâu, với tư cách gì |
|-----------|-------|---------------------|-----------------------------|
| Chủ shophouse ở khu A, sống ở căn hộ khu B | Sang khu A mở hàng, nhập hàng | 7h–19h, ngày thường | Khu A — thành viên khu A (chủ shophouse) |
| Nhân viên shophouse, văn phòng, phòng khám | Đi làm | Giờ hành chính | Khu nơi làm việc — nhân viên của đơn vị |
| Cư dân khu B đưa con đến trường liên cấp ở khu C | Đưa đón con | 7h–8h và 16h30–17h30 | Khu C — thành viên chuỗi |
| Cư dân đi khám, đi gym, đi trung tâm thương mại ở khu khác | Dùng tiện ích | Theo lượt, 1–3 giờ | Khu đến — thành viên chuỗi (thường là TH3 với giá ưu đãi) |
| Người thuê căn hộ không có chỗ; hộ có xe thứ hai | Cần chỗ qua đêm | 18h–7h | Tòa mình ở — thành viên tòa |
| Người thân đến thăm dài ngày (lễ Tết) | Là khách của cư dân | Vài ngày | Chỗ của chủ nhà (miễn phí) hoặc TH3 |
| Khách vãng lai, khách của shophouse | Mua sắm, giao dịch | Theo lượt | TH3 / bãi công cộng (shophouse có thể cấp voucher) |

**Bên cho thuê chỗ**:
- Cư dân đi làm ngoài khu cả ngày.
- Chủ căn hộ đã cho thuê lại căn nhưng giữ chỗ đỗ.
- Người về quê dịp lễ Tết.
- Văn phòng có chỗ riêng nhưng trống ban đêm và cuối tuần.
- Chủ đầu tư, qua pool TH2.

## 4. Giải pháp đề xuất

Một **Agent** điều phối quyền sử dụng chỗ đỗ trên toàn chuỗi. Mỗi người dùng chỉ có **một tài khoản cho cả chuỗi**, kèm nhiều **tư cách** gắn với tài sản cụ thể. Agent có 6 năng lực:

1. **Xác định tư cách** — tại khu có chỗ đỗ, lấy tư cách mạnh nhất của người yêu cầu: thành viên tòa > thành viên khu > thành viên chuỗi > khách. Agent không xét tư cách ở khu khác.
2. **Định tuyến** — dựa vào tư cách và phạm vi mở của pool để ghép vào TH1/TH2, hoặc chuyển sang TH3 / bãi công cộng.
3. **Chia sẻ** — đề xuất khung giờ chia sẻ, giữ khoảng dự phòng, ghép cung–cầu, sinh thỏa thuận điện tử và ghi sổ cái.
4. **Xử lý ngoại lệ** — chủ về sớm, người thuê đỗ quá giờ. Khi khu đó hết chỗ, Agent gợi ý chỗ ở khu lân cận trong chuỗi.
5. **Tranh chấp** — thu thập bằng chứng, lập ticket (biển số đã ẩn) và chuyển cho BQL của khu có chỗ đỗ xác minh.
6. **Hoán đổi** — đề xuất hoán đổi giữa 2 bên hoặc theo chuỗi trong cùng một khu; BQL khu phê duyệt.

Yêu cầu chức năng chi tiết: [PRD §6](prd.md#6-yêu-cầu-chức-năng).

### Ví dụ: chủ shophouse ở khu A, có căn hộ ở khu B

| Ở đâu | Tư cách | Được gì |
|-------|---------|---------|
| Khu A | Thành viên khu A, với tư cách chủ shophouse | Được thuê TH1/TH2 ở khu A nếu phạm vi mở của pool cho phép. **Không** có các quyền chỉ dành cho chủ căn hộ (biểu quyết nội quy tòa ở, cho khách đỗ miễn phí vào chỗ của tòa). |
| Khu B | Thành viên tòa (cư dân căn hộ) | Có đầy đủ quyền cư dân, được chia sẻ chỗ TH1 của mình. |
| Khu khác | Thành viên chuỗi | Được thuê TH2 nếu pool mở cho cả chuỗi; được dùng TH3 với giá thành viên. |

Nếu shophouse nằm ở **khối đế** của một tòa chung cư, chủ shophouse cũng là **thành viên của tòa đó**.

### Phạm vi bản demo

Mô hình hỗ trợ **N khu** (từ 2 khu trở lên). Bản demo mô phỏng **1 chuỗi gồm 3 khu** (A, B, C). Mỗi khu có vài tòa, một cụm shophouse và một bãi công cộng. Demo bao gồm:

- Xác định tư cách và định tuyến TH1/TH2/TH3 theo phạm vi mở.
- Ghép chỗ theo thời gian và kích thước xe.
- Xử lý ngoại lệ, tranh chấp, hoán đổi có BQL duyệt.
- Log LPR (nhận diện biển số) mô phỏng.
- VietQR mock và voucher shophouse cho lượt đỗ TH3.

Để giai đoạn sau: điều phối bãi riêng của trường học, bệnh viện, trung tâm thương mại; thanh toán thật; MoMo/ZaloPay. Ranh giới đầy đủ: [Scope](scope.md).

## 5. Đối tượng (tóm tắt)

- **Bên cung cấp chỗ** — cư dân có chỗ TH1/TH2, văn phòng có chỗ riêng, chủ đầu tư (pool TH2).
- **Bên cần chỗ** — được phân loại theo **tư cách tại khu có chỗ đỗ**, không theo "là ai".
- **Bên quản lý và phê duyệt** — đơn vị vận hành chuỗi, BQL từng khu, Ban quản trị và Hội nghị nhà chung cư từng tòa, đơn vị trông giữ xe.

Danh sách đầy đủ: [PRD §3](prd.md#3-đối-tượng-người-dùng-và-tư-cách).

## 6. Giá trị mang lại

| Bên | Lợi ích |
|-----|---------|
| **Chủ chỗ** | Thu khoảng **1 triệu/tháng** *(giả định)*, kỳ vọng bù **30–70%** phí gửi xe; vẫn được **bảo đảm quyền quay về**. |
| **Người thuê** | Khoảng **~50k/ngày**, rẻ hơn gửi ngoài (**20–70k/giờ**). Đỗ ngay tại khu mình cần đến, kể cả khi không sống ở khu đó. |
| **BQL khu, đơn vị vận hành chuỗi** | Hưởng phí dịch vụ, ít tranh chấp, biết rõ ai được dùng chỗ nào. Điều phối được cung–cầu giữa các khu. |

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

> Baseline và giá trị mục tiêu chưa được xác định trong tài liệu nguồn.

## 8. Nguyên tắc vận hành và dữ liệu

- **Ai quyết định**: rule engine quyết định quyền thuê và phí. Agent chỉ đề xuất. BQL của khu có chỗ đỗ duyệt tranh chấp, hoán đổi và giao dịch vượt ngưỡng.
- **Dữ liệu tư cách**: tư cách do BQL khu nơi có tài sản xác minh. Khu khác chỉ nhận **kết quả xác nhận** (cấp tư cách và hạn hiệu lực), không nhận hồ sơ cư dân.
- **Log LPR**: log trùng được bỏ qua; kết quả OCR có độ tin cậy thấp cần người kiểm tra.
- **Biển số**: được mã hóa khi lưu, ẩn trong ticket và ẩn danh trước khi gửi tới LLM.

Điều kiện lưu trữ và tuân thủ trước khi dùng dữ liệu thật: [Scope §3–5](scope.md#3-nguyên-tắc-dữ-liệu-và-quyền-riêng-tư).
