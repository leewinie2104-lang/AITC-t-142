# PRD — Agent điều phối quyền sử dụng chỗ đỗ trong chuỗi khu đô thị

> **File này trả lời:** sản phẩm làm gì, cho ai, theo quy tắc nào. Nơi **định nghĩa chuẩn** tư cách L1–L4, loại chỗ TH1–TH3, BR và FR.
> **Pilot:** demo chạy trong **một tòa** theo [07 Pilot một tòa](07-pilot-mot-toa.md); quy tắc chuỗi nhiều khu giữ làm thiết kế.
> Liên quan: [Bài toán](00-xac-dinh-bai-toan.md) · [Brief](01-project-brief.md) · [Scope](03-scope.md) · [User Stories](04-user-stories.md) · [Traceability](06-traceability.md) · [Backlog](05-backlog.md)

## 1. Mục tiêu sản phẩm

Khai thác chỗ đỗ bỏ trống trong hầm các tòa **trên toàn chuỗi khu đô thị**; chia sẻ đúng tư cách, đúng phạm vi, có bằng chứng; đáp ứng nhu cầu đỗ giữa các khu, giảm tranh chấp và thời gian xử lý cho BQL.

## 2. Mô hình tổ chức
<blockquote style="border-left: 4px solid #22c55e; background: #f0fdf4; padding: 0.75em 1em; margin-left: 0; border-radius: 4px;"><strong style="color: #000;">CHỈ THAM KHẢO, KHÔNG CẦN ĐỌC</strong></blockquote>

- Chuỗi (1) → Khu (N ≥ 2) → Phân khu → Tòa hỗn hợp (căn hộ; khối đế: shophouse, văn phòng, phòng khám, mầm non) · Cụm shophouse thấp tầng · Bãi công cộng.
- Số khu, tòa là **dữ liệu cấu hình**. Thẩm quyền: **vận hành chuỗi** (chủ đầu tư) cấu hình chung, mở pool TH2, bảng giá khung, báo cáo chuỗi ·
- **BQL khu** khai thác TH3, xác minh tư cách, duyệt HITL · **Ban quản trị / Hội nghị nhà chung cư** đặt nội quy tòa, gồm phạm vi mở TH1 · **đơn vị trông giữ xe** cung cấp dữ liệu cổng, log LPR.

## 3. Đối tượng người dùng và tư cách

### 3.1 Tài khoản và tư cách
<blockquote style="border-left: 4px solid #22c55e; background: #f0fdf4; padding: 0.75em 1em; margin-left: 0; border-radius: 4px;"><strong style="color: #000;">CHỈ THAM KHẢO, KHÔNG CẦN ĐỌC</strong></blockquote>

Một tài khoản cho cả chuỗi, giữ nhiều **tư cách** = *(tài sản, vai trò, hạn)*. Tài sản: căn hộ, shophouse, văn phòng, chỗ đỗ. Vai trò trong tư cách: chủ sở hữu, người thuê, người được ủy quyền, nhân viên. Tư cách **gắn với tài sản**: bán tài sản, hết hợp đồng thuê, bị rút quyền → hết hiệu lực. BQL khu có tài sản xác minh. **Bên cung cấp chỗ** (cư dân TH1/TH2, văn phòng có chỗ riêng, chủ đầu tư với pool TH2) chia sẻ trong phạm vi mở (§4); **bên cần chỗ** là bất kỳ ai.

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
<blockquote style="border-left: 4px solid #22c55e; background: #f0fdf4; padding: 0.75em 1em; margin-left: 0; border-radius: 4px;"><strong style="color: #000;">CHỈ THAM KHẢO</strong></blockquote>

- Vai trò tài khoản (`app.user_role`, trong JWT, [ADR-0006](../07-adr/ADR-0006-self-issued-jwt-auth.md)) quyết định màn hình và API; **không** quyết định quyền thuê.
- `resident` có tư cách gắn tài sản: xin chỗ, chia sẻ chỗ mình · `renter` chỉ thuê, có thể L4 · `guard` bảo vệ / trông giữ xe của một khu (chưa có màn hình)
- `zone_manager` BQL một khu (`app_user.staff_zone_id`): xác minh, duyệt HITL · `chain_operator`: cấu hình chung, chỉ xem số liệu tổng hợp.

## 4. Phân loại chỗ đỗ và phạm vi mở

**Phạm vi mở** = cấp thấp nhất được thuê một ô: **Tòa** = L1 · **Khu** = L1–L2 · **Chuỗi** = L1–L3 · **Công cộng** = mọi cấp.

| Loại | Quy tắc cho thuê | Mặc định | Mở rộng tối đa |
|------|------------------|----------|----------------|
| **TH1** — chỗ cư dân đã mua | Chủ chỗ được cho thuê | **Tòa** | **Khu** nếu nội quy tòa cho phép *(A-08)* |
| **TH2** — chỗ thuê từ chủ đầu tư | Cho thuê lại khi chủ đầu tư **đồng ý một lần cho cả pool** | **Khu** | **Chuỗi** nếu vận hành chuỗi cấu hình |
| **TH3** — chỗ công cộng / khách | **BQL khu khai thác**; cá nhân không được cho thuê | **Công cộng** | — (giá theo cấp) |
| *Chủ chỗ* | Có thể **thu hẹp** phạm vi khi chia sẻ, không vượt nội quy (Ưu tiên 3) | | |

## 5. Quy tắc nghiệp vụ
<blockquote style="border-left: 4px solid #22c55e; background: #f0fdf4; padding: 0.75em 1em; margin-left: 0; border-radius: 4px;"><strong style="color: #000;">CHỈ THAM KHẢO</strong></blockquote>

Rule engine (`policy`) áp dụng tất định. **Chặn hay chuyển hướng:** chỉ không đạt phạm vi mở → **chuyển** sang TH3 / bãi công cộng theo giá cấp, không ghi KPI (FR-03). **Chặn** và ghi KPI "sai tư cách / sai phạm vi" chỉ khi vi phạm rõ ràng (FR-04): tư cách hết hạn (BR-16), TH1 ngoài phạm vi ô (BR-01), cá nhân chia sẻ TH3 (BR-03), ngoài nền tảng (BR-04), cư dân thu phí khách (BR-05).

| Nhóm | Quy tắc |
|------|---------|
| Loại chỗ | **BR-01** **TH1 theo phạm vi mở**: chỉ người trong phạm vi mở của ô; mặc định L1. · **BR-02** **TH2 theo pool**: cho thuê lại khi chủ đầu tư chấp thuận cả pool; phạm vi do vận hành chuỗi cấu hình. · **BR-03** **TH3 chỉ BQL khai thác**; cá nhân không được cho thuê. |
| Kênh, khách | **BR-04** **Kênh chính thức**: chia sẻ trong phạm vi ô, qua nền tảng, theo khung giá và mẫu thỏa thuận của nội quy. · **BR-05** **Khách cư dân miễn phí**, chỉ tại tòa nơi cư dân là L1. · **BR-06** **Khách shophouse** chuyển sang TH3 của khu có shophouse. |
| Tư cách | **BR-15** **Cấp tại vị trí ô**: lấy cấp cao nhất còn hiệu lực; khu khác chỉ tính L3. · **BR-16** **Hết hạn**: chặn giao dịch **mới**; giao dịch đang hiệu lực giữ tới hết kỳ (kỳ tối đa: TBD). · **BR-17** **Chỉ trao đổi kết quả xác nhận** giữa các khu; hồ sơ, số căn hộ, giấy tờ không rời BQL khu sở hữu. |
| Ghép, duyệt | **BR-11** **Đúng kích thước**: chỉ ghép ô đúng kích thước xe; xét khung giờ, dự phòng, ưu tiên. · **BR-12** **Vượt ngưỡng** (theo khu) là ca vùng xám ở lớp 1 của BR-26 → BQL khu xem trước khi hiệu lực. · **BR-10** **Hoán đổi cùng khu**, cần BQL khu phê duyệt. · **BR-18** **BQL khu có ô** xử lý tranh chấp và duyệt, kể cả khi một bên là thành viên khu khác. |
| Quyền quay về, giá, phí | **BR-07** **Chủ về sớm, ưu tiên người thuê**: người thuê được ở lại tới hết giờ đã đặt, dời chỗ là tự nguyện; chủ được bảo đảm một chỗ đỗ (ô dự phòng / bãi khách trong tòa, miễn phí), không bảo đảm đúng ô của mình. ETA chủ lấy một lần ([ADR-0014](../07-adr/ADR-0014-eta-location-and-renter-priority-on-early-return.md)); ETA người thuê theo [ADR-0015](../07-adr/ADR-0015-renter-gps-eta-otp-and-two-layer-approval.md). · **BR-19** **Giá theo cấp tư cách** tại ô ([§8](#8-mô-hình-giá-giả-định-từ-nguồn)). · **BR-08** **Phí quá giờ** theo nội quy khu có chỗ: miễn 10 phút, rồi tính từ giờ kết thúc theo mỗi 15 phút bắt đầu, 50 000 đ/giờ (mặc định, A-07; D-03 cần BQL xác nhận); người thuê trả, tiền về chủ chỗ hoặc về khu nếu là chỗ TH3; miễn phí chỉ qua khiếu nại do BQL quyết định. |
| Pilot: hàng chờ, chỗ trống | **BR-20** **Chỗ trống khi đủ 3 điều kiện**: chủ đã đăng, chủ đã nhập **OTP xác nhận cho thuê với hệ thống**, log cổng xác nhận xe gắn ô đã ra sau lúc đăng. Đăng quá **30 phút** mà xe chưa ra → tin đăng hết hạn, app báo chủ đăng lại. · **BR-21** **Hàng chờ**: người thuê chờ chỗ phù hợp đầu tiên của tòa; chỗ trống trước ghép trước. Người thuê **đủ điều kiện gán** khi lần GPS gần nhất cho **ETA ≤ 30 phút (có tính kẹt xe)**, hoặc bấm "Tôi đang đến", hoặc đang thừa chỗ và không ai gần hơn đang chờ. Trong nhóm đủ điều kiện, thứ tự theo `queued_at`. ETA > 30 phút: chưa gán, chưa trừ tiền, vẫn nhận số chỗ còn lại. |
| Pilot: giữ chỗ, OTP, hủy | **BR-22** **OTP nhận chỗ và giữ chỗ**: được gán → người thuê nhập **OTP nhận chỗ trong 3 phút**; có OTP mới trừ tiền (ghi nhận khoản) và bắt đầu giữ. Không nhập → chỗ chuyển người kế tiếp, người thuê về hàng chờ, không mất tiền. Thời hạn giữ = **ETA + 10 phút, tối đa 40 phút** (TH3: tối đa 60). Hết hạn mà camera chưa thấy xe vào → nhả chỗ, **phí không tới = 30% giá trị lượt, tối thiểu bằng phí 1 giờ**, hoàn 70%, phần giữ lại về chủ chỗ (TH3: về khu). · **BR-23** **Hủy và hoàn** theo quy định ghi trong thỏa thuận; hệ thống chỉ ghi nhận khoản, không thu tiền (không QR). · **BR-24** **Hết ô dự phòng**: BQL xử lý, tòa tạm ngừng nhận lượt thuê mới tới khi có lại ô dự phòng. · **BR-25** **Hai OTP, mỗi bên với hệ thống**: chủ xác nhận lúc đăng (đồng ý cho thuê khung giờ); người thuê xác nhận lúc được gán (đồng ý nhận chỗ và bị trừ tiền). Không có OTP giữa hai bên. |
| Pilot: duyệt, GPS, TH3, báo chỗ | **BR-26** **Duyệt 2 lớp, BQL chỉ xem ca xấu**: lớp 1 rule engine → đạt / vi phạm rõ ràng (tự từ chối, báo lý do) / vùng xám (thiếu dữ liệu, sát ngưỡng → BQL); lớp 2 AI đánh giá rủi ro ca đã đạt (lịch sử quá giờ, về sớm, tranh chấp, giá bất thường) → bình thường **tự duyệt**, đáng ngờ → BQL kèm lý do và dẫn chứng. **AI chỉ siết, không nới**: không cho qua ca rule đã chặn. Ca chờ BQL quá **10 phút** → coi như từ chối, không tự duyệt; người thuê được báo và gợi ý bãi khác. Đăng ký (chủ, người thuê) **tự đối chiếu** dữ liệu BQL có sẵn (danh sách cư dân, chủ shophouse, ô và kích thước từng hộ, biển số) nhập một lần lúc triển khai; khớp → tự kích hoạt, không khớp → BQL. · **BR-27** **GPS và ETA người thuê**: có đồng ý riêng (NĐ 13/2023, `consent_record`); app lấy GPS **mỗi 15 phút, chỉ khi đang có yêu cầu trong hàng chờ**, ngừng sau khi chốt gán (TH3: tới khi xe vào). ETA qua port `TravelTimeProvider` (mock ở dev/CI/demo; adapter Goong / VietMap / Google sau cờ). Không lưu tọa độ thô, chỉ lưu ETA, thời điểm, nguồn; không gửi tọa độ cho LLM. GPS chỉ dùng xếp ưu tiên / chốt thời điểm gán, **không** dùng xác nhận chỗ trống hay tính tiền (có thể giả GPS). GPS lỗi hoặc tắt → coi như còn xa; 2 lần liên tiếp không có GPS → nhắc, không loại khỏi hàng. · **BR-28** **Ưu tiên TH3**: TH1, TH2 hết chỗ → người thuê **liên quan khu đô thị** (cư dân tòa khác trong khu, chủ shophouse…) đã đặt và OTP được ưu tiên hơn khách vãng lai ở bãi khách, kể cả khi còn xa; gán ngay lúc đặt; giữ ETA + 10, tối đa 60 phút. Bãi khách còn **≤ 2 chỗ** hoặc ≤ số người ưu tiên đang tới → báo BQL và bảo vệ ("không nhận khách vãng lai"). Không tới → nhả và tính phí không tới, báo bảo vệ mở lại. Khách vãng lai không dùng app: hệ thống chỉ báo, bảo vệ chặn. Số chỗ còn lại ở bãi khách trừ chỗ đã giữ. · **BR-29** **Báo số chỗ còn lại**: mỗi khi một chỗ bị gán hoặc mất đi, báo người đang chờ "Còn N chỗ phù hợp xe bạn, bạn đứng thứ k"; khi ước tính không còn cơ hội → chủ động gợi ý bãi khác. |
| Dữ liệu, AI, LPR | **BR-09** **Đồng ý dữ liệu, ẩn biển số**: xử lý biển số, ảnh theo đồng ý khi đăng ký; biển số trong ticket phải ẩn. · **BR-13** **Chống trùng LPR**: trùng mã sự kiện không xử lý hai lần; OCR thấp đánh dấu kiểm tra. · **BR-14** **LLM chỉ gợi ý**: tên, biển số thành mã giả trước khi gửi LLM; LLM không thay rule engine hay người duyệt. Tiền, phí, nhắc giờ, tạm ngừng nhận lượt đều do code / job. |

## 6. Yêu cầu chức năng
<blockquote style="border-left: 4px solid #22c55e; background: #f0fdf4; padding: 0.75em 1em; margin-left: 0; border-radius: 4px;"><strong style="color: #000;">CHỈ THAM KHẢO</strong></blockquote>

| Nhóm | Yêu cầu | Mức |
|------|---------|-----|
| Tư cách, liên khu | **FR-23** một tài khoản, nhiều tư cách, BQL xác minh · **FR-24** cấp L1–L4 tại ô (BR-15) · **FR-25** hết hạn → chặn giao dịch mới, thông báo (BR-16) · **FR-26** phạm vi mở từng pool; chủ chỗ thu hẹp · **FR-27** gợi ý ô khu khác khi hết chỗ (chỉ gợi ý) | 1 · FR-25 thông báo: 3 · FR-26 thu hẹp: 3 · FR-27: 2 |
| Định tuyến | **FR-01** kiểm tra quyền thuê theo cấp và phạm vi mở · **FR-02** ghép TH1/TH2 (BR-01, BR-02) · **FR-03** chuyển TH3 / bãi công cộng, giá theo cấp · **FR-04** chặn sai tư cách / phạm vi | 1 |
| Chia sẻ | **FR-05** đề xuất khung giờ · **FR-06** khoảng dự phòng · **FR-07** ghép theo giờ, kích thước, dự phòng, ưu tiên, phạm vi · **FR-08** thỏa thuận theo mẫu khu có ô · **FR-09** bằng chứng xác nhận chỉ ghi thêm · **FR-09a** vượt ngưỡng chờ BQL duyệt (BR-12) | 1 · FR-05: 3 |
| Ngoại lệ | **FR-10** chủ về sớm → ETA chủ (FR-31) → báo người thuê; người thuê dời thì đổi lượt, ở lại thì chủ đỗ ô dự phòng; hết → BQL (BR-07, BR-24) · **FR-11** nhắc người thuê 2 lần: trước giờ kết thúc 20 phút và đúng lúc hết giờ (nêu 10 phút cho phép và mức phí) · **FR-12** phí quá giờ tính khi xe ra theo log cổng (BR-08) | FR-10: 2 · FR-11, 12: 2 |
| Tranh chấp | **FR-13** đọc ảnh đã che biển số (BR-14) · **FR-14** gom bằng chứng xác nhận, log cổng, phí quá giờ; xác định xe bằng log cổng và biển số đã băm · **FR-15** ticket ẩn biển số · **FR-16** chuyển BQL khu có ô (BR-18); BQL quyết định: giữ nguyên, bác, miễn phí quá giờ, khác · **FR-16a** chuẩn hóa LPR, chống trùng, so khớp mờ, OCR thấp | FR-13 → FR-16: 2 · FR-16a chống trùng: 1, còn lại: 3 |
| Pilot: hàng chờ, chỗ trống, Agent, ETA | **FR-28** hàng chờ người thuê (BR-21) · **FR-29** chỗ trống theo log cổng và OTP chủ (BR-20, BR-25) · **FR-30** Agent đề xuất ghép theo giờ, kích thước, lịch sử hai bên; rule engine chốt · **FR-31** ETA người thuê từ GPS mỗi 15 phút, ETA chủ về sớm một lần; không lưu tọa độ (BR-27) | FR-28…31: 1 |
| Pilot: duyệt, OTP, TH3, báo chỗ | **FR-32** quá giờ mà xe chưa ra → báo bảo vệ · **FR-33** duyệt 2 lớp: rule engine, AI đánh giá rủi ro ca đạt, BQL chỉ xem ca xấu (BR-26) · **FR-34** dòng thời gian tranh chấp có ghi nguồn · **FR-35** OTP nhận chỗ và giữ theo ETA (BR-22, BR-25) · **FR-36** ưu tiên TH3, báo BQL và bảo vệ (BR-28) · **FR-37** báo số chỗ còn lại, gợi ý bãi khác (BR-29) · **FR-38** đăng ký tự đối chiếu dữ liệu BQL (BR-26) | FR-33, FR-35, FR-38: 1 · FR-32, FR-34, FR-36, FR-37: 2 |
| Hoán đổi | **FR-17** đề xuất hoán đổi cùng khu (2 bên hoặc nhiều bên theo vòng) · **FR-18** hiệu lực sau khi BQL duyệt | 3 |
| Nền và tiện ích | **FR-19** nhận log LPR (CSV mô phỏng; webhook / MQTT) · **FR-20** dự báo khung giờ trống · **FR-21** phí chia sẻ theo cấp, ghi vào sổ khoản phí (không thanh toán trong app) · **FR-22** voucher shophouse cho lượt TH3 | FR-19 CSV: 1 · FR-21: 1 · FR-20, 22: 3 |

## 7. Hình thức hợp đồng
<blockquote style="border-left: 4px solid #22c55e; background: #f0fdf4; padding: 0.75em 1em; margin-left: 0; border-radius: 4px;"><strong style="color: #000;">CHỈ THAM KHẢO</strong></blockquote>

Khách theo lượt: vé / biên lai điện tử · Vé tháng: hợp đồng một lần (cả hai do BQL khu). Chia sẻ giữa người dùng: thỏa thuận điện tử theo mẫu khu có ô, Agent sinh; chủ và người thuê mỗi bên xác nhận OTP **với hệ thống** ([BR-25](#5-quy-tắc-nghiệp-vụ)), BQL khu ghi nhận.

## 8. Mô hình giá (giả định từ nguồn)

- Chủ chỗ ~1 triệu/tháng *(giả định)*, bù 30–70% phí gửi xe
- Chia sẻ cho L1–L2 ~50k/ngày
- L3 cao hơn L1–L2, thấp hơn giá khách
- TH3 do BQL quy định
- Gửi ngoài 20–70k/giờ. Giá demo: `zone_policy.prices`.
