# User Stories & Acceptance Criteria — Agent điều phối quyền sử dụng chỗ đỗ trong chuỗi khu đô thị

> **File này trả lời:** ai cần gì, vì sao (US), và làm sao biết đã làm đúng (AC Given → When → Then).
> Liên quan: [PRD](02-prd.md) (FR, BR) · [Traceability](06-traceability.md) (use case) · [User Flow](ux/01-user-flow.md) · [Backlog](05-backlog.md)

<blockquote style="border-left: 4px solid #22c55e; background: #f0fdf4; padding: 0.75em 1em; margin-left: 0; border-radius: 4px;">
  <strong style="color: #000;">KHÔNG CẦN NẮM RÕ, PHẦN BACKLOG CÓ GIẢI THÍCH</strong>
</blockquote>

Mỗi dòng: US và AC nghiệm thu nó. Cấp L1–L4: [PRD §3.2](02-prd.md#32-cấp-tư-cách-tại-vị-trí-chỗ-đỗ). **TBD** = ngưỡng chưa có nguồn.
Cột *Mức* = Ưu tiên của [Backlog §1](05-backlog.md#1-cách-đọc); 3 = chỉ làm nếu còn thời gian.

## Epic 0 — Tư cách và liên khu

| US · AC | Vai trò → muốn (để) | Nghiệm thu: Given → When → Then | FR / BR | Mức |
|---|---|---|---|---|
| US-19 · AC-19 | Chủ shophouse khu A, có căn hộ khu B → thuê chỗ ban ngày ở khu A (không gửi bãi ngoài giá khách) | Chủ shophouse thấp tầng khu A + chủ căn hộ khu B → yêu cầu chỗ tòa khu A 7h–19h → cấp **L2** tại khu A; chỉ ô phạm vi Khu/Chuỗi; không có quyền BR-05. Shophouse khối đế cùng tòa → **L1** (A-10) | FR-23, FR-24, FR-01 | 1 |
| US-20 · AC-20 | Cư dân khu B, con học khu C → thuê chỗ khung đưa đón (không đỗ dưới lòng đường) | Cư dân khu B (L3 ở khu C), TH2 khu C mở Chuỗi → yêu cầu 7h–8h và 16h30–17h30 → ghép TH2 khu C giá L3; nếu TH2 chỉ mở trong khu → TH3 khu C (AC-02) | FR-24, FR-26, FR-07 | 1 |
| US-21 · AC-21 | Người có tài sản nhiều khu → một tài khoản, tự áp đúng tư cách nơi đỗ | Nhiều tư cách còn hiệu lực → yêu cầu chỗ tòa *T* → lấy cấp **cao nhất** tại *T*; khu khác chỉ tính L3 (BR-15); không đăng ký lại | FR-23, FR-24 | 1 |
| US-22 · AC-22 | BQL khu → tư cách người thuê căn hộ tự hết hiệu lực khi hết hợp đồng | Tư cách hết hạn ngày *D* → qua *D* → chặn yêu cầu **mới** (KPI "sai tư cách"); giao dịch đang hiệu lực giữ tới hết kỳ (kỳ tối đa: TBD); thông báo người dùng và chủ chỗ | FR-25 · BR-16 | 1 (chặn) · 3 (quét, thông báo) |
| US-23 · AC-23 | Chủ chỗ TH1 → chỉ cho người cùng tòa thuê dù nội quy rộng hơn | Nội quy cho TH1 mở cả khu → chủ chọn "chỉ trong tòa" → chỉ L1 của tòa được ghép; không chọn rộng hơn nội quy | FR-26 | 3 |
| US-24 · AC-24 | Cư dân → BQL khu khác chỉ thấy "có tư cách hợp lệ" | Tư cách đã xác minh ở khu B → khu A kiểm tra → khu A chỉ nhận cấp và hạn; không thấy số căn hộ, giấy tờ, hồ sơ | BR-17 | 2 |
| US-25 · AC-25 | Người cần chỗ → được gợi ý khu khác khi khu đến hết chỗ | Khu hết ô phù hợp, kể cả TH3 → gửi yêu cầu → gợi ý ô khu khác người dùng đủ điều kiện; không tự đặt. "Lân cận": TBD | FR-27 | 2 |

## Epic 1 — Định tuyến

| US · AC | Vai trò → muốn (để) | Nghiệm thu | FR / BR | Mức |
|---|---|---|---|---|
| US-01 · AC-01 | Người đạt phạm vi mở của pool (cư dân không chỗ, người thuê, hộ 2 xe, shophouse, văn phòng, thành viên chuỗi khi TH2 mở chuỗi) → được ghép TH1/TH2 | Cấp tại ô nằm trong phạm vi mở → gửi yêu cầu → ghép TH1/TH2 còn trống đúng phạm vi. Ưu tiên TH1 vs TH2: TBD | FR-01, FR-02 | 1 |
| US-02 · AC-02 | Người không đạt phạm vi mở (khách, khách shophouse, thành viên chuỗi khi pool chỉ mở trong khu) → TH3 hoặc bãi công cộng, giá đúng cấp | Không đạt phạm vi mở của mọi pool TH1/TH2 → gửi yêu cầu → không ghép TH1/TH2; chuyển TH3 / bãi công cộng của khu, giá theo cấp | FR-01, FR-03 | 1 |
| US-03 · AC-03 | BQL khu → chặn giao dịch sai tư cách hoặc sai phạm vi | Vi phạm rõ ràng (PRD §5) → rule engine kiểm tra → từ chối kèm lý do, ghi KPI khi: TH1 ngoài phạm vi ô (BR-01), cá nhân cho thuê TH3 (BR-03), ngoài nền tảng (BR-04), cư dân thu phí khách (BR-05), tư cách hết hạn (BR-16). Chỉ không đạt phạm vi mở → **không** chặn, chuyển theo AC-02 | FR-04 | 1 |
| US-16 · AC-06 | Người cần chỗ → chỉ ghép ô đúng kích thước xe và khung giờ | Nghiệm thu theo AC-06 (phần kích thước ô) | FR-07 · BR-11 | 1 |

## Epic 2 — Chia sẻ

| US · AC | Vai trò → muốn (để) | Nghiệm thu | FR / BR | Mức |
|---|---|---|---|---|
| US-04 · AC-04 | Chủ chỗ → được đề xuất khung giờ có thể chia sẻ | Chủ chỗ TH1/TH2 mở màn hình chia sẻ → đề xuất khung giờ. Cơ sở dữ liệu đề xuất: TBD | FR-05 | 3 |
| US-05 · AC-05 | Chủ chỗ → có khoảng dự phòng (không sợ mất chỗ khi về) | Đăng một khung giờ → lịch được lưu → có khoảng dự phòng theo nội quy khu (A-07); không ghép vào khoảng dự phòng | FR-06 | 1 |
| US-06 · AC-06 | Người cần chỗ → ghép với chỗ chia sẻ mình đủ điều kiện | Có cấp tại ô, xe đã khai kích thước → gửi yêu cầu → chỉ ghép chỗ hợp lệ theo AC-01, AC-03; ô đúng kích thước; xét giờ, dự phòng, ưu tiên. Không có TH1/TH2 → TH3 cùng khu (AC-02); hết TH3 → AC-25 | FR-07 | 1 |
| US-07 · AC-07 | Chủ chỗ / người thuê → thỏa thuận điện tử theo mẫu khu có ô | Ghép thành công → tạo thỏa thuận → theo mẫu và khung giá của **khu có ô**; hiệu lực khi **cả hai bên** xác nhận (OTP) | FR-08 | 1 |
| US-08 · AC-08 | BQL khu → mỗi thỏa thuận đã xác nhận có bằng chứng | Hai bên đã xác nhận → thỏa thuận có hiệu lực (qua BQL duyệt nếu vượt ngưỡng, AC-15) → lưu bằng chứng xác nhận chỉ ghi thêm; BQL khu có ô xem được | FR-09 | 1 (lưu) · 2 (xem) |
| — · AC-15 | *(BQL khu, chưa có US)* | Giao dịch vượt ngưỡng của khu có ô → Agent tạo đề xuất → chờ BQL khu duyệt; chưa hiệu lực trước khi duyệt | FR-09a · BR-12 | 1 |
| — · AC-16 | *(chưa có US)* | Thỏa thuận có hiệu lực / hủy / quá giờ → hệ thống tính khoản → ghi vào sổ khoản phí, **không** hiện mã QR hay thu tiền. Voucher shophouse chỉ cho lượt TH3 | FR-21, FR-22 | 1 (sổ khoản) · 3 (voucher) |

## Epic 3 — Xử lý ngoại lệ

| US · AC | Vai trò → muốn (để) | Nghiệm thu | FR / BR | Mức |
|---|---|---|---|---|
| US-09 · AC-09 | Chủ chỗ về sớm → luôn có chỗ đỗ, người thuê biết trước | Chỗ đang được thuê → chủ bấm về sớm (vị trí một lần hoặc chọn số phút) → hệ thống ước tính giờ về, báo người thuê kèm ô khác còn trống và hạn trả lời; người thuê dời → chủ về đúng ô; người thuê ở lại hoặc không trả lời → chủ đỗ ô dự phòng, miễn phí; hết ô dự phòng → BQL, tòa tạm ngừng nhận lượt | FR-10, FR-31 · BR-07, BR-24 | 2 |
| US-10 · AC-09 | Người thuê bị chủ về sớm → được ở lại tới hết giờ đã đặt, dời là tự nguyện | Như AC-09; người thuê ở lại không bị tính thêm phí hay bị chuyển | FR-10 · BR-07 | 2 |
| US-11 · AC-10 | Chủ chỗ → người đỗ quá giờ bị nhắc, tính phí | Thỏa thuận có giờ kết thúc → N2 nhắc người thuê 2 lần (trước 20 phút; đúng lúc hết giờ, nêu 10 phút cho phép và mức phí), không nhắc thêm → khi xe ra (log cổng) vượt 10 phút thì tính từ giờ kết thúc, mỗi 15 phút bắt đầu, 50 000 đ/giờ (mặc định, BQL xác nhận: A-07, D-03). Người thuê trả; tiền về chủ chỗ, chỗ TH3 về khu. Miễn phí chỉ qua khiếu nại | FR-11, FR-12 · BR-08 | 2 |

## Epic 4–5 — Tranh chấp (Ưu tiên 2) và hoán đổi (Ưu tiên 3)

| US · AC | Vai trò → muốn (để) | Nghiệm thu | FR / BR | Mức |
|---|---|---|---|---|
| US-12 · AC-11 | BQL khu → nhận hồ sơ đã có ảnh, đã đối chiếu bằng chứng xác nhận và log cổng | Cư dân báo kèm ảnh tại ô khu K (chiếm chỗ, quá giờ, sai xe, hư hỏng, khác) → hồ sơ thuộc khu K, chuyển BQL khu K (BR-18) → W5 gom ảnh, thỏa thuận và bằng chứng xác nhận, log cổng quanh thời điểm, phí quá giờ → model đọc ảnh đã che biển số; xe xác định bằng log cổng và biển số đã băm → tóm tắt gắn nhãn "Gợi ý" → BQL quyết định: giữ nguyên, bác, miễn phí quá giờ, khác. Bằng chứng chỉ ghi thêm | FR-13, FR-14, FR-16 · BR-14, BR-18 | 2 |
| US-13 · AC-12 | Cư dân → biển số được ẩn trong ticket | Ticket có biển số → hiển thị hoặc gửi LLM → biển số ẩn; không gửi biển số cho LLM. MVP chỉ hiện bản ẩn; xem bản gốc có ghi log: Ưu tiên 3 | FR-15 · BR-09, BR-14 | 2 · 3 (xem bản gốc) |
| US-14 · AC-13 | Người có chỗ không hợp nhu cầu → đề xuất hoán đổi cùng khu (2 bên hoặc nhiều bên theo vòng) | Tranh chấp lặp hoặc nhu cầu đã đăng ký → N5 / người dùng kích hoạt W6 → đề xuất, mọi ô cùng **một khu**. "Lặp lại": TBD | FR-17 | 3 |
| US-15 · AC-14 | BQL khu → duyệt hoán đổi trước khi hiệu lực | Có đề xuất chờ duyệt → BQL duyệt / từ chối → chỉ hiệu lực sau khi duyệt | FR-18 | 3 |

## Epic 6 — Vận hành LPR và dự báo

| US · AC | Vai trò → muốn (để) | Nghiệm thu | FR / BR | Mức |
|---|---|---|---|---|
| US-17 · AC-17, AC-10a | BQL khu → log LPR trùng hoặc OCR thấp được xử lý đúng | Log qua bộ mô phỏng → worker xử lý → chuẩn hóa, gắn khu, chống trùng mã sự kiện (không tạo giao dịch trùng); OCR thấp vào hàng chờ, không tự kết luận | FR-16a · BR-13 | 1 (chống trùng) · 3 (OCR thấp, so khớp mờ) |
| US-18 · AC-18 | Chủ chỗ → xem khung giờ thường trống | Có lịch sử ra / vào → tạo dự báo → chỉ tham khảo, không tự đăng lịch | FR-20 | 3 |

## Epic 7 — Pilot một tòa ([07 Pilot](07-pilot-mot-toa.md))

| US · AC | Vai trò → muốn (để) | Nghiệm thu | FR / BR | Mức |
|---|---|---|---|---|
| US-26 · AC-26 | Chủ chỗ → chỗ chỉ được cho thuê khi xe mình đã ra (không bị ghép khi còn đỗ) | Chủ đã đăng, xe chưa ra → không ghép; log cổng thấy xe gắn ô đó ra → chỗ `available`, phát sự kiện ghép | FR-29 · BR-20 | 1 |
| US-27 · AC-27 | Người thuê → chờ chỗ phù hợp đầu tiên của tòa, không chờ riêng một chỗ | Anh B trong hàng chờ, chị A đăng chưa ra, anh C đăng và đã ra → anh B được ghép chỗ anh C | FR-28 · BR-21 | 1 |
| US-28 · AC-28 | Người kế tiếp trong hàng → nhận chỗ khi người trước không xác nhận kịp | Chỗ đang giữ cho anh B → quá `hold_ttl` chưa xác nhận → `expired`, ghép người kế tiếp, báo hai người | BR-22 | 1 |
| US-29 · AC-29 | BQL → Agent đề xuất ghép kèm lý do nhưng không vượt quy tắc | Có nhiều ứng viên → Agent xếp hạng theo giờ, kích thước, lịch sử → rule engine kiểm; sai quy tắc → dùng phương án tất định; ghi `ai_decision_log` | FR-30 · BR-14 | 1 |
| US-30 · AC-30 | Người thuê / chủ → hủy được và biết khoản hoàn | Lượt đã chốt → hủy → khoản hoàn theo mốc trong thỏa thuận ghi vào sổ; chỗ về hàng chờ | BR-23 | 2 |
| US-31 · AC-31 | Bảo vệ → biết xe nào quá giờ, chủ nào cần ô dự phòng | Quá giờ + thời gian miễn phí mà chưa có log ra → báo bảo vệ một lần; ca chủ về sớm cần ô dự phòng → báo bảo vệ số ô | FR-32 | 2 |
| US-32 · AC-32 | BQL → duyệt nhanh lúc cao điểm | Hàng chờ duyệt có nhãn "duyệt nhanh" / "cần xem kỹ" kèm lý do; trường hợp bắt buộc luôn "cần xem kỹ"; BQL vẫn bấm duyệt | FR-33 · BR-12 | 2 |
| US-33 · AC-33 | BQL → xem sự việc tranh chấp theo thời gian, có nguồn | Hồ sơ tranh chấp → dòng thời gian từ thỏa thuận, log cổng, ảnh; câu không có nguồn bị loại; BQL quyết định | FR-34 · BR-18 | 2 |

## Ưu tiên

| Mức | User Story |
|-----|-----------|
| **Ưu tiên 1** | **Pilot: US-26, US-27, US-28, US-29; AC-16 (sổ khoản)**; US-01, US-02, US-03, US-05, US-06, US-07, US-08 (lưu), US-16, US-19, US-20, US-21; US-22 (chặn khi hết hạn); US-17 (chống trùng); AC-15 |
| **Ưu tiên 2** | **Pilot: US-09, US-10, US-11, US-30, US-31, US-32, US-33**; US-08 (xem), US-12, US-13, US-24 |
| **Ưu tiên 3** | US-04, US-14, US-15, US-18, US-23, US-25 (khu khác: pilot chỉ một tòa); phần còn lại của US-13 (xem bản gốc), US-17, US-22; voucher (AC-16) |
