# PRD — Agent điều phối quyền sử dụng chỗ đỗ trong chuỗi khu đô thị

> **File này trả lời:** sản phẩm làm gì, cho ai, theo quy tắc nào? Nơi **định nghĩa chuẩn** tư cách L1–L4, loại chỗ TH1–TH3, BR và FR.

> **Liên quan:** [Bài toán](00-xac-dinh-bai-toan.md) · [Brief](01-project-brief.md) · [Scope](03-scope.md) · [User Stories & AC](04-user-stories.md) · [Traceability](06-traceability.md) · KPI: [Brief §7](01-project-brief.md#7-chỉ-số-thành-công-kpi), [Scope §6](03-scope.md#6-chỉ-số-theo-dõi)

## 1. Mục tiêu sản phẩm

- Khai thác chỗ đỗ bỏ trống trong hầm các tòa, **trên toàn chuỗi khu đô thị**.
- Chia sẻ an toàn, đúng tư cách, đúng phạm vi, có bằng chứng.
- Đáp ứng nhu cầu đỗ xe giữa các khu; giảm tranh chấp và thời gian xử lý cho BQL.

Vấn đề: [Brief §2](01-project-brief.md#2-vấn-đề).

## 2. Mô hình tổ chức

Chuỗi (1) → Khu đô thị (N ≥ 2) → Phân khu → Tòa chung cư hỗn hợp (căn hộ; khối đế: shophouse, văn phòng, phòng khám, mầm non) · Cụm shophouse thấp tầng · Bãi công cộng

| Cấp | Vai trò quản lý | Thẩm quyền liên quan đến chỗ đỗ |
|-----|-----------------|----------------------------------|
| Chuỗi | Đơn vị vận hành chuỗi (chủ đầu tư) | Cấu hình chung; đồng ý mở pool TH2; bảng giá khung; báo cáo toàn chuỗi |
| Khu | BQL khu | Khai thác TH3; xác minh tư cách tài sản; duyệt HITL (tranh chấp, hoán đổi, vượt ngưỡng) |
| Tòa | Ban quản trị, Hội nghị nhà chung cư | Nội quy tòa, gồm **phạm vi mở của TH1** |
| Khu | Đơn vị trông giữ xe | Cung cấp dữ liệu cổng và log LPR |

Số khu, phân khu, tòa là **dữ liệu cấu hình**; thêm khu không đòi hỏi đổi logic.

## 3. Đối tượng người dùng và tư cách

### 3.1 Tài khoản và tư cách

- Một tài khoản cho cả chuỗi; một tài khoản giữ nhiều **tư cách** = *(tài sản, vai trò, hạn hiệu lực)*.
- Tài sản: căn hộ, shophouse, văn phòng, chỗ đỗ… · Vai trò trong tư cách: chủ sở hữu, người thuê, người được ủy quyền, nhân viên. Khác với vai trò tài khoản ở [§3.4](#34-vai-trò-tài-khoản).
- Tư cách **gắn với tài sản**: bán tài sản, hết hợp đồng thuê, hoặc đơn vị rút quyền nhân viên → hết hiệu lực. BQL khu có tài sản xác minh.

### 3.2 Cấp tư cách tại vị trí chỗ đỗ

Yêu cầu thuê chỗ ở tòa *T* thuộc khu *K* → lấy **cấp cao nhất** đạt **tại vị trí đó** (BR-15).

| Cấp | Điều kiện | Ví dụ |
|-----|-----------|-------|
| **L1 — Thành viên tòa** | Tư cách còn hiệu lực gắn với tài sản trong tòa *T* | Cư dân căn hộ ở *T*; chủ/nhân viên shophouse khối đế của *T* |
| **L2 — Thành viên khu** | Tư cách gắn với tài sản khác trong khu *K* | Cư dân tòa khác cùng khu; chủ shophouse thấp tầng ở *K* |
| **L3 — Thành viên chuỗi** | Tư cách ở một khu khác trong chuỗi | Cư dân khu B sang khu A |
| **L4 — Khách** | Không có tư cách nào còn hiệu lực | Khách vãng lai, khách shophouse |

Ví dụ: chủ shophouse thấp tầng khu A, có căn hộ khu B → khu A **L2**; tòa căn hộ **L1**; khu C **L3**.
Quyền riêng của chủ căn hộ (biểu quyết nội quy, cho khách đỗ miễn phí) **không** chuyển sang khu khác.

### 3.3 Nhóm người dùng

| Nhóm | Thành phần | Quyền liên quan đến chỗ đỗ |
|------|-----------|----------------------------|
| **Bên cung cấp chỗ** | Cư dân TH1/TH2; văn phòng có chỗ riêng; chủ đầu tư (pool TH2) | Chia sẻ trong phạm vi mở (§4) |
| **Bên cần chỗ** | Bất kỳ ai; quyền theo L1–L4 và loại tư cách | Ghép TH1/TH2 nếu đạt phạm vi mở; nếu không → TH3 / bãi công cộng |
| **Bên quản lý và phê duyệt** | Vận hành chuỗi; BQL khu; Ban quản trị; Hội nghị nhà chung cư; đơn vị trông giữ xe | Cấu hình, xác minh, phê duyệt. Demo: **BQL khu có chỗ đỗ** duyệt HITL |

### 3.4 Vai trò tài khoản

Vai trò tài khoản quyết định người dùng được mở màn hình và API nào. Nó nằm trong JWT ([ADR-0006](../10-adr/ADR-0006-self-issued-jwt-auth.md)) và trong `app.user_role` của schema. Vai trò tài khoản **không** quyết định quyền thuê: quyền thuê theo tư cách và cấp L1–L4 (§3.1–3.2).

| Vai trò (`app.user_role`) | Là ai | Phạm vi |
|---|---|---|
| `resident` | Cư dân, chủ / nhân viên shophouse, văn phòng: người có tư cách gắn tài sản | Xin chỗ, chia sẻ chỗ của mình, báo tranh chấp |
| `renter` | Người dùng chỉ thuê chỗ, có thể không có tư cách nào (L4) | Xin chỗ, thanh toán, báo tranh chấp |
| `guard` | Bảo vệ, đơn vị trông giữ xe của khu | Xem dòng thời gian ra vào, kiểm tra hàng chờ OCR thấp của khu mình |
| `zone_manager` | BQL khu | Xác minh tư cách, duyệt HITL, xử lý tranh chấp, hoán đổi của khu mình |
| `chain_operator` | Đơn vị vận hành chuỗi | Cấu hình chung, mở pool TH2 theo chuỗi; chỉ xem số liệu tổng hợp |

`guard` và `zone_manager` chỉ thấy các khu được gán (claim `zone_ids`).

## 4. Phân loại chỗ đỗ và phạm vi mở

**Phạm vi mở** = cấp thấp nhất được thuê một ô: **Tòa** = L1 · **Khu** = L1–L2 · **Chuỗi** = L1–L3 · **Công cộng** = mọi cấp.

| Loại | Quy tắc cho thuê | Phạm vi mở mặc định | Mở rộng tối đa |
|------|------------------|---------------------|----------------|
| **TH1** — chỗ cư dân đã mua | Chủ chỗ được cho thuê | **Tòa** | **Khu**, nếu nội quy tòa cho phép *(giả định A-08)* |
| **TH2** — chỗ thuê từ chủ đầu tư | Cho thuê lại khi chủ đầu tư đồng ý; **đồng ý một lần cho cả pool** | **Khu** | **Chuỗi**, nếu đơn vị vận hành chuỗi cấu hình |
| **TH3** — chỗ công cộng hoặc chỗ khách | Do **BQL khu khai thác**; **cá nhân không được cho thuê** | **Công cộng** | — (giá theo cấp tư cách) |

Chủ chỗ có thể **thu hẹp** phạm vi khi chia sẻ, không mở rộng quá nội quy.

## 5. Quy tắc nghiệp vụ

Rule engine (`policy`) áp dụng các quy tắc này một cách tất định. Quy tắc nào được kiểm tra ở use case nào: xem [Traceability](06-traceability.md).

**Chặn hay chuyển hướng.** Người yêu cầu chỉ không đạt phạm vi mở của pool → **chuyển** sang TH3 / bãi công cộng theo giá cấp (FR-03, AC-02). Trường hợp này không phải vi phạm, không ghi KPI. **Chặn** và ghi KPI "sai tư cách / sai phạm vi" chỉ khi có vi phạm rõ ràng (FR-04, AC-03): yêu cầu dựa trên tư cách đã hết hạn (BR-16), chủ chỗ chia sẻ TH1 ngoài phạm vi ô (BR-01), cá nhân chia sẻ TH3 (BR-03), giao dịch ngoài nền tảng (BR-04), cư dân thu phí khách hoặc dùng quyền khách ngoài tòa L1 (BR-05). Sau khi bị chặn, người yêu cầu vẫn được chỉ sang TH3 theo cấp còn hiệu lực.

| ID | Tên quy tắc | Nội dung |
|----|-------------|----------|
| BR-01 | **TH1 theo phạm vi mở** | TH1 chỉ cho người trong phạm vi mở của ô; mặc định L1. |
| BR-02 | **TH2 cho thuê theo pool** | TH2 cho thuê lại khi chủ đầu tư đã chấp thuận cả pool; phạm vi do đơn vị vận hành chuỗi cấu hình. |
| BR-03 | **TH3 chỉ BQL khai thác** | TH3 do BQL khu khai thác; cá nhân không được cho thuê. |
| BR-04 | **Chia sẻ qua kênh chính thức** | Chia sẻ chỉ trong phạm vi ô, qua **nền tảng chính thức**, theo **khung giá** và **mẫu thỏa thuận** của nội quy. |
| BR-05 | **Khách cư dân miễn phí** | Cư dân chỉ cho khách của mình đỗ **miễn phí**, và chỉ tại tòa nơi mình là L1. |
| BR-06 | **Khách shophouse sang TH3** | Khách shophouse chuyển sang TH3 của khu có shophouse. |
| BR-07 | **Quyền quay về** | Chủ chỗ được **bảo đảm quyền quay về** chỗ của mình. |
| BR-08 | **Phí quá giờ** | Phí quá giờ theo nội quy của khu có chỗ (mức phí: TBD). |
| BR-09 | **Đồng ý dữ liệu, ẩn biển số** | Xử lý biển số và ảnh theo đồng ý khi đăng ký app; biển số trong ticket phải ẩn. |
| BR-10 | **Hoán đổi cùng khu** | Hoán đổi chỉ trong **cùng một khu** và cần **BQL khu phê duyệt**. |
| BR-11 | **Ghép đúng kích thước** | Chỉ ghép ô đúng kích thước xe; xét khung giờ, khoảng dự phòng, quyền ưu tiên đã cấu hình. |
| BR-12 | **Duyệt giao dịch vượt ngưỡng** | Giao dịch vượt ngưỡng định mức (theo khu) chờ BQL khu duyệt trước khi có hiệu lực. |
| BR-13 | **Chống trùng log LPR** | Log LPR trùng mã sự kiện không xử lý hai lần; OCR độ tin cậy thấp đánh dấu để kiểm tra. |
| BR-14 | **LLM chỉ gợi ý** | Biển số và tên thành mã giả trước khi gửi LLM; LLM không thay rule engine hay người duyệt. |
| BR-15 | **Cấp tư cách tại vị trí ô** | Cấp tư cách xác định **tại vị trí ô**, lấy cấp cao nhất còn hiệu lực; khu khác chỉ tính L3. |
| BR-16 | **Tư cách hết hạn** | Tư cách hết hạn → chặn giao dịch **mới**; giao dịch đang hiệu lực giữ tới hết kỳ (kỳ tối đa: TBD). |
| BR-17 | **Chỉ trao đổi kết quả xác nhận** | Giữa các khu chỉ trao đổi **kết quả xác nhận tư cách**; hồ sơ, số căn hộ, giấy tờ không rời BQL khu sở hữu. |
| BR-18 | **BQL khu có ô xử lý tranh chấp** | Tranh chấp do **BQL khu có ô đỗ** xử lý, kể cả khi một bên là thành viên khu khác. |
| BR-19 | **Giá theo cấp tư cách** | Giá thuê theo **cấp tư cách** tại ô (xem [§8](#8-mô-hình-giá-giả-định-từ-nguồn)). |

## 6. Yêu cầu chức năng

Mỗi FR chỉ nêu việc cần làm; quy tắc chi tiết nằm ở BR được trích.

| ID | Nhóm | Yêu cầu |
|----|------|---------|
| FR-23 | Tư cách và liên khu | Quản lý một tài khoản cho cả chuỗi với nhiều tư cách; BQL khu xác minh. |
| FR-24 |  | Tính cấp L1–L4 tại vị trí ô (BR-15). |
| FR-25 |  | Vô hiệu tư cách khi hết hạn; chặn giao dịch mới; thông báo (BR-16). |
| FR-26 |  | Cấu hình phạm vi mở từng pool; chủ chỗ thu hẹp khi chia sẻ (§4). |
| FR-27 |  | Gợi ý ô khu khác trong chuỗi khi khu hết chỗ phù hợp (chỉ gợi ý). |
| FR-01 | Định tuyến | Kiểm tra đủ điều kiện thuê riêng theo cấp (FR-24) và phạm vi mở. |
| FR-02 |  | Ghép TH1 hoặc TH2 khi đủ điều kiện (BR-01, BR-02). |
| FR-03 |  | Chuyển TH3 hoặc bãi công cộng khi không đủ; giá theo cấp. |
| FR-04 |  | Chặn giao dịch sai tư cách hoặc phạm vi (BR-01, BR-03, BR-04, BR-05, BR-16). |
| FR-05 | Chia sẻ | Đề xuất khung giờ chỗ có thể chia sẻ. |
| FR-06 |  | Giữ khoảng dự phòng khi chia sẻ (độ dài: TBD). |
| FR-07 |  | Ghép cung–cầu theo khung giờ, kích thước ô/xe, dự phòng, ưu tiên, phạm vi. |
| FR-08 |  | Sinh thỏa thuận điện tử theo mẫu khu có ô đỗ để hai bên xác nhận. |
| FR-09 |  | Ghi giao dịch đã xác nhận vào sổ cái; BQL khu ghi nhận. |
| FR-09a |  | Chờ BQL khu duyệt giao dịch vượt ngưỡng trước khi có hiệu lực (BR-12). |
| FR-10 | Xử lý ngoại lệ | Chủ về sớm → chỗ thay thế từ TH3 cùng khu; hết chỗ → FR-27. |
| FR-11 |  | Nhắc người thuê đỗ quá giờ. |
| FR-12 |  | Tính phí quá giờ theo nội quy (BR-08). |
| FR-13 | Tranh chấp | Đọc ảnh liên quan tranh chấp. |
| FR-14 |  | Đối chiếu sổ cái và dữ liệu cổng của khu. |
| FR-15 |  | Lập ticket với biển số đã ẩn. |
| FR-16 |  | Chuyển ticket cho BQL khu có ô đỗ xác minh (BR-18). |
| FR-16a |  | Chuẩn hóa LPR; chống trùng; so khớp mờ biển số; đánh dấu OCR thấp để kiểm tra tay. |
| FR-17 | Hoán đổi | Đề xuất hoán đổi trong cùng khu (2 bên hoặc nhiều bên theo vòng) từ tranh chấp lặp lại hoặc nhu cầu đã đăng ký (BR-10). |
| FR-18 |  | Chỉ có hiệu lực sau khi BQL khu phê duyệt. |
| FR-19 | Tác vụ nền và tiện ích demo | Nhận log LPR qua webhook, MQTT, DB hoặc CSV; demo dùng log mô phỏng (ngày thường, cuối tuần, lễ Tết). |
| FR-20 |  | Dự báo khung giờ trống theo khu từ lịch sử; chỉ gợi ý, không tự tạo lịch. |
| FR-21 |  | Tính phí chia sẻ theo cấp (BR-19); ghi trạng thái thanh toán VietQR mock cho mọi khoản phí, kể cả phí quá giờ của FR-12. |
| FR-22 |  | Tạo voucher shophouse cho lượt đỗ TH3; không đổi cấp tư cách hay quyền TH1/TH2. |

## 7. Hình thức hợp đồng

| Giao dịch | Hình thức | Ai lập |
|-----------|-----------|--------|
| Khách theo lượt | Vé hoặc biên lai điện tử | BQL khu |
| Vé tháng | Hợp đồng ký một lần | BQL khu |
| Chia sẻ giữa người dùng (cùng khu hoặc liên khu) | Thỏa thuận điện tử theo mẫu khu có ô đỗ | Agent sinh; hai bên xác nhận; BQL khu ghi nhận |

Demo: VietQR mock; MoMo, ZaloPay và tiền thật để giai đoạn sau. Ranh giới: [Scope §1–2](03-scope.md#1-trong-phạm-vi-bản-demo).

## 8. Mô hình giá (giả định từ nguồn)

| Hạng mục | Giá trị |
|----------|---------|
| Thu nhập chủ chỗ | ~1 triệu/tháng *(giả định)*, bù 30–70% phí gửi xe |
| Giá thuê chỗ chia sẻ cho L1–L2 | ~50k/ngày |
| Giá thuê chỗ chia sẻ cho L3 (liên khu) | TBD (dự kiến cao hơn L1–L2, thấp hơn giá khách) |
| Giá TH3 theo cấp (thành viên / khách) | TBD, do BQL khu quy định |
| Giá gửi xe bên ngoài (tham chiếu) | 20–70k/giờ |
| Khung giá chính thức theo nội quy | TBD |
| Phí dịch vụ BQL khu / vận hành chuỗi | TBD |

## 9. Yêu cầu phi chức năng

| Nhóm | Yêu cầu |
|------|---------|
| **Phân quyền** | Dữ liệu tách theo khu và hộ; BQL chỉ thấy khu mình; đơn vị vận hành chuỗi chỉ thấy số liệu tổng hợp. |
| **Riêng tư** | Theo [Scope §3](03-scope.md#3-nguyên-tắc-dữ-liệu-và-quyền-riêng-tư); điều kiện: BR-09, BR-14, BR-17. |
| **Tính toàn vẹn** | Sổ cái chỉ ghi thêm (append-only); mỗi bản ghi băm liên kết với bản trước. |
| **Độ tin cậy nghiệp vụ** | Rule engine tất định quyết định tư cách, quyền thuê, tính phí; các bước vượt định mức, tranh chấp, hoán đổi có BQL duyệt. |
| **Mở rộng** | Thêm khu, phân khu, tòa hoặc pool chỉ bằng cấu hình và dữ liệu. |
| **LPR** | Chống trùng (BR-13, FR-16a); OCR không chắc chắn vào hàng chờ kiểm tra, không tự kết luận. |
| **Lưu trữ và vận hành** | Thời hạn lưu log/ảnh, hiệu năng, độ sẵn sàng, quy trình xóa: TBD trước khi dùng thật. |
| **Tuân thủ** | Xác nhận pháp lý và chuyển dữ liệu xuyên biên giới trước khi nối AI với dữ liệu thật ([Scope §5](03-scope.md#5-phụ-thuộc)). |
