# PRD — Agent điều phối quyền sử dụng chỗ đỗ trong chuỗi khu đô thị

> **File này trả lời:** sản phẩm làm gì, cho ai, theo quy tắc nào. Nơi **định nghĩa chuẩn** tư cách L1–L4, loại chỗ TH1–TH3, BR và FR.
> Liên quan: [Bài toán](00-xac-dinh-bai-toan.md) · [Brief](01-project-brief.md) · [Scope](03-scope.md) · [User Stories](04-user-stories.md) · [Traceability](06-traceability.md) · [Backlog](backlog/README.md)

## 1. Mục tiêu sản phẩm

Khai thác chỗ đỗ bỏ trống trong hầm các tòa **trên toàn chuỗi khu đô thị**; chia sẻ đúng tư cách, đúng phạm vi, có bằng chứng;
đáp ứng nhu cầu đỗ giữa các khu, giảm tranh chấp và thời gian xử lý cho BQL. Vấn đề: [Brief §2](01-project-brief.md#2-vấn-đề).

## 2. Mô hình tổ chức

Chuỗi (1) → Khu (N ≥ 2) → Phân khu → Tòa hỗn hợp (căn hộ; khối đế: shophouse, văn phòng, phòng khám, mầm non) · Cụm shophouse thấp tầng · Bãi công cộng.
Số khu, tòa là **dữ liệu cấu hình**. Thẩm quyền: **vận hành chuỗi** (chủ đầu tư) cấu hình chung, mở pool TH2, bảng giá khung, báo cáo chuỗi ·
**BQL khu** khai thác TH3, xác minh tư cách, duyệt HITL · **Ban quản trị / Hội nghị nhà chung cư** đặt nội quy tòa, gồm phạm vi mở TH1 ·
**đơn vị trông giữ xe** cung cấp dữ liệu cổng, log LPR.

## 3. Đối tượng người dùng và tư cách

### 3.1 Tài khoản và tư cách

Một tài khoản cho cả chuỗi, giữ nhiều **tư cách** = *(tài sản, vai trò, hạn)*. Tài sản: căn hộ, shophouse, văn phòng, chỗ đỗ. Vai trò trong tư cách:
chủ sở hữu, người thuê, người được ủy quyền, nhân viên. Tư cách **gắn với tài sản**: bán tài sản, hết hợp đồng thuê, bị rút quyền → hết hiệu lực. BQL khu có tài sản xác minh.
**Bên cung cấp chỗ** (cư dân TH1/TH2, văn phòng có chỗ riêng, chủ đầu tư với pool TH2) chia sẻ trong phạm vi mở (§4); **bên cần chỗ** là bất kỳ ai.

### 3.2 Cấp tư cách tại vị trí chỗ đỗ

Yêu cầu chỗ ở tòa *T* thuộc khu *K* → lấy **cấp cao nhất** đạt **tại vị trí đó** (BR-15).

| Cấp | Điều kiện | Ví dụ |
|-----|-----------|-------|
| **L1 — Thành viên tòa** | Tư cách còn hiệu lực gắn tài sản trong tòa *T* | Cư dân căn hộ ở *T*; chủ / nhân viên shophouse khối đế của *T* |
| **L2 — Thành viên khu** | Tư cách gắn tài sản khác trong khu *K* | Cư dân tòa khác cùng khu; chủ shophouse thấp tầng ở *K* |
| **L3 — Thành viên chuỗi** | Tư cách ở khu khác trong chuỗi | Cư dân khu B sang khu A |
| **L4 — Khách** | Không có tư cách còn hiệu lực | Khách vãng lai, khách shophouse |

Ví dụ: chủ shophouse thấp tầng khu A, có căn hộ khu B → khu A **L2**, tòa căn hộ **L1**, khu C **L3**. Quyền riêng của chủ căn hộ (biểu quyết, cho khách đỗ miễn phí) **không** chuyển sang khu khác.

### 3.4 Vai trò tài khoản

Vai trò tài khoản (`app.user_role`, trong JWT, [ADR-0006](../07-adr/ADR-0006-self-issued-jwt-auth.md)) quyết định màn hình và API; **không** quyết định quyền thuê.
`resident` có tư cách gắn tài sản: xin chỗ, chia sẻ chỗ mình · `renter` chỉ thuê, có thể L4 · `guard` bảo vệ / trông giữ xe của một khu (chưa có màn hình) ·
`zone_manager` BQL một khu (`app_user.staff_zone_id`): xác minh, duyệt HITL · `chain_operator`: cấu hình chung, chỉ xem số liệu tổng hợp.

## 4. Phân loại chỗ đỗ và phạm vi mở

**Phạm vi mở** = cấp thấp nhất được thuê một ô: **Tòa** = L1 · **Khu** = L1–L2 · **Chuỗi** = L1–L3 · **Công cộng** = mọi cấp.

| Loại | Quy tắc cho thuê | Mặc định | Mở rộng tối đa |
|------|------------------|----------|----------------|
| **TH1** — chỗ cư dân đã mua | Chủ chỗ được cho thuê | **Tòa** | **Khu** nếu nội quy tòa cho phép *(A-08)* |
| **TH2** — chỗ thuê từ chủ đầu tư | Cho thuê lại khi chủ đầu tư **đồng ý một lần cho cả pool** | **Khu** | **Chuỗi** nếu vận hành chuỗi cấu hình |
| **TH3** — chỗ công cộng / khách | **BQL khu khai thác**; cá nhân không được cho thuê | **Công cộng** | — (giá theo cấp) |
| *Chủ chỗ* | Có thể **thu hẹp** phạm vi khi chia sẻ, không vượt nội quy (Ưu tiên 3) | | |

## 5. Quy tắc nghiệp vụ

Rule engine (`policy`) áp dụng tất định. **Chặn hay chuyển hướng:** chỉ không đạt phạm vi mở → **chuyển** sang TH3 / bãi công cộng theo giá cấp, không ghi KPI (FR-03).
**Chặn** và ghi KPI "sai tư cách / sai phạm vi" chỉ khi vi phạm rõ ràng (FR-04): tư cách hết hạn (BR-16), TH1 ngoài phạm vi ô (BR-01), cá nhân chia sẻ TH3 (BR-03), ngoài nền tảng (BR-04), cư dân thu phí khách (BR-05).

| Nhóm | Quy tắc |
|------|---------|
| Loại chỗ | **BR-01** **TH1 theo phạm vi mở**: chỉ người trong phạm vi mở của ô; mặc định L1. · **BR-02** **TH2 theo pool**: cho thuê lại khi chủ đầu tư chấp thuận cả pool; phạm vi do vận hành chuỗi cấu hình. · **BR-03** **TH3 chỉ BQL khai thác**; cá nhân không được cho thuê. |
| Kênh, khách | **BR-04** **Kênh chính thức**: chia sẻ trong phạm vi ô, qua nền tảng, theo khung giá và mẫu thỏa thuận của nội quy. · **BR-05** **Khách cư dân miễn phí**, chỉ tại tòa nơi cư dân là L1. · **BR-06** **Khách shophouse** chuyển sang TH3 của khu có shophouse. |
| Tư cách | **BR-15** **Cấp tại vị trí ô**: lấy cấp cao nhất còn hiệu lực; khu khác chỉ tính L3. · **BR-16** **Hết hạn**: chặn giao dịch **mới**; giao dịch đang hiệu lực giữ tới hết kỳ (kỳ tối đa: TBD). · **BR-17** **Chỉ trao đổi kết quả xác nhận** giữa các khu; hồ sơ, số căn hộ, giấy tờ không rời BQL khu sở hữu. |
| Ghép, duyệt | **BR-11** **Đúng kích thước**: chỉ ghép ô đúng kích thước xe; xét khung giờ, dự phòng, ưu tiên. · **BR-12** **Vượt ngưỡng** (theo khu) chờ BQL khu duyệt trước khi hiệu lực. · **BR-10** **Hoán đổi cùng khu**, cần BQL khu phê duyệt. · **BR-18** **BQL khu có ô** xử lý tranh chấp và duyệt, kể cả khi một bên là thành viên khu khác. |
| Quyền quay về, giá, phí | **BR-07** **Quyền quay về**: chủ chỗ được bảo đảm quay về chỗ của mình. · **BR-19** **Giá theo cấp tư cách** tại ô ([§8](#8-mô-hình-giá-giả-định-từ-nguồn)). · **BR-08** **Phí quá giờ** theo nội quy khu có chỗ: miễn 10 phút, rồi tính từ giờ kết thúc theo mỗi 15 phút bắt đầu, 50 000 đ/giờ (mặc định, A-07; D-03 cần BQL xác nhận); người thuê trả, tiền về chủ chỗ hoặc về khu nếu là chỗ TH3; miễn phí chỉ qua khiếu nại do BQL quyết định. |
| Dữ liệu, AI, LPR | **BR-09** **Đồng ý dữ liệu, ẩn biển số**: xử lý biển số, ảnh theo đồng ý khi đăng ký; biển số trong ticket phải ẩn. · **BR-13** **Chống trùng LPR**: trùng mã sự kiện không xử lý hai lần; OCR thấp đánh dấu kiểm tra. · **BR-14** **LLM chỉ gợi ý**: tên, biển số thành mã giả trước khi gửi LLM; LLM không thay rule engine hay người duyệt. |

## 6. Yêu cầu chức năng

Cột *Mức* = [Backlog §1](backlog/README.md#1-ba-mức-ưu-tiên) (3 = không làm trong 4 tuần).

| Nhóm | Yêu cầu | Mức |
|------|---------|-----|
| Tư cách, liên khu | **FR-23** một tài khoản, nhiều tư cách, BQL xác minh · **FR-24** cấp L1–L4 tại ô (BR-15) · **FR-25** hết hạn → chặn giao dịch mới, thông báo (BR-16) · **FR-26** phạm vi mở từng pool; chủ chỗ thu hẹp · **FR-27** gợi ý ô khu khác khi hết chỗ (chỉ gợi ý) | 1 · FR-25 thông báo: 3 · FR-26 thu hẹp: 3 · FR-27: 2 |
| Định tuyến | **FR-01** kiểm tra quyền thuê theo cấp và phạm vi mở · **FR-02** ghép TH1/TH2 (BR-01, BR-02) · **FR-03** chuyển TH3 / bãi công cộng, giá theo cấp · **FR-04** chặn sai tư cách / phạm vi | 1 |
| Chia sẻ | **FR-05** đề xuất khung giờ · **FR-06** khoảng dự phòng · **FR-07** ghép theo giờ, kích thước, dự phòng, ưu tiên, phạm vi · **FR-08** thỏa thuận theo mẫu khu có ô · **FR-09** bằng chứng xác nhận chỉ ghi thêm · **FR-09a** vượt ngưỡng chờ BQL duyệt (BR-12) | 1 · FR-05: 3 |
| Ngoại lệ | **FR-10** chủ về sớm → TH3 cùng khu; hết → FR-27 · **FR-11** nhắc người thuê 2 lần: trước giờ kết thúc 20 phút và đúng lúc hết giờ (nêu 10 phút cho phép và mức phí) · **FR-12** phí quá giờ tính khi xe ra theo log cổng (BR-08) | FR-10: 2 · FR-11, 12: 2 |
| Tranh chấp | **FR-13** đọc ảnh đã che biển số (BR-14) · **FR-14** gom bằng chứng xác nhận, log cổng, phí quá giờ; xác định xe bằng log cổng và biển số đã băm · **FR-15** ticket ẩn biển số · **FR-16** chuyển BQL khu có ô (BR-18); BQL quyết định: giữ nguyên, bác, miễn phí quá giờ, khác · **FR-16a** chuẩn hóa LPR, chống trùng, so khớp mờ, OCR thấp | FR-13 → FR-16: 2 · FR-16a chống trùng: 1, còn lại: 3 |
| Hoán đổi | **FR-17** đề xuất hoán đổi cùng khu (2 bên hoặc nhiều bên theo vòng) · **FR-18** hiệu lực sau khi BQL duyệt | 3 |
| Nền và tiện ích | **FR-19** nhận log LPR (CSV mô phỏng; webhook / MQTT) · **FR-20** dự báo khung giờ trống · **FR-21** phí chia sẻ theo cấp, VietQR mock · **FR-22** voucher shophouse cho lượt TH3 | FR-19 CSV: 1 · FR-21 phí: 1, VietQR: 2 · FR-20, 22: 3 |

## 7. Hình thức hợp đồng

Khách theo lượt: vé / biên lai điện tử · vé tháng: hợp đồng một lần (cả hai do BQL khu) · chia sẻ giữa người dùng: thỏa thuận điện tử theo mẫu khu có ô,
Agent sinh, hai bên xác nhận OTP, BQL khu ghi nhận. Demo: VietQR mock ([Scope §1–2](03-scope.md#1-trong-phạm-vi-bản-demo)).

## 8. Mô hình giá (giả định từ nguồn)

Chủ chỗ ~1 triệu/tháng *(giả định)*, bù 30–70% phí gửi xe · chia sẻ cho L1–L2 ~50k/ngày · L3 cao hơn L1–L2, thấp hơn giá khách · TH3 do BQL quy định ·
gửi ngoài 20–70k/giờ. Giá demo: `zone_policy.prices` (D-01, mặc định cần BQL xác nhận).

## 9. Yêu cầu phi chức năng

- **Phân quyền:** tách theo khu và hộ (RLS); BQL chỉ thấy khu mình; vận hành chuỗi chỉ thấy số liệu tổng hợp.
- **Riêng tư:** [Scope §3](03-scope.md#3-nguyên-tắc-dữ-liệu-và-quyền-riêng-tư); BR-09, BR-14, BR-17.
- **Toàn vẹn:** bằng chứng xác nhận và `ai_decision_log` chỉ ghi thêm. **Tin cậy:** rule engine tất định; vượt ngưỡng có BQL duyệt.
- **Mở rộng:** thêm khu, tòa, pool chỉ bằng cấu hình. **Lưu trữ, tuân thủ:** chốt trước khi dùng dữ liệu thật ([Scope §5](03-scope.md#5-phụ-thuộc)).
