# User Stories & Acceptance Criteria — Agent điều phối quyền sử dụng chỗ đỗ trong chuỗi khu đô thị

> **File này trả lời:** ai cần gì, vì sao (US), và làm sao biết đã làm đúng (AC, kịch bản Given / When / Then kiểm được). Mỗi US gắn FR/BR ([PRD](02-prd.md)); ánh xạ sang module và use case ở [Traceability](06-traceability.md).

> **Liên quan:** [Bài toán](00-xac-dinh-bai-toan.md) · [PRD §5 Quy tắc nghiệp vụ](02-prd.md#5-quy-tắc-nghiệp-vụ) · [User Flow](ux/01-user-flow.md) · [Backlog](backlog/README.md)

Mỗi epic gồm bảng **User story** (Vai trò · Muốn · Để) rồi bảng **Nghiệm thu** (AC). Ô trống (—) = không áp dụng; ngưỡng chưa có trong nguồn ghi **TBD**. Cấp L1–L4: [PRD §3.2](02-prd.md#32-cấp-tư-cách-tại-vị-trí-chỗ-đỗ).

## Epic 0 — Tư cách và liên khu

**User story**

| US | Vai trò | Muốn | Để | FR / BR |
|----|---------|------|----|---------|
| US-19 | Chủ shophouse khu A, có căn hộ khu B | Thuê chỗ ban ngày khu A với tư cách chủ shophouse | Mở hàng, không gửi bãi ngoài giá khách | FR-23, FR-24, FR-01 |
| US-20 | Cư dân khu B, con học khu C | Thuê chỗ theo khung đưa đón với tư cách thành viên chuỗi | Không đỗ dưới lòng đường | FR-24, FR-26, FR-07 |
| US-21 | Người có tài sản ở nhiều khu | Dùng một tài khoản, tự áp đúng tư cách tại nơi đỗ | Không đăng ký lại ở mỗi khu | FR-23, FR-24 |
| US-22 | BQL khu | Tư cách người thuê căn hộ tự hết hiệu lực khi hết hợp đồng | Người hết quyền không thuê chỗ riêng | FR-25 |
| US-23 | Chủ chỗ TH1 | Giới hạn chỉ người cùng tòa được thuê, dù nội quy rộng hơn | Yên tâm khi chia sẻ | FR-26 |
| US-24 | Cư dân | BQL khu khác chỉ thấy "có tư cách hợp lệ", không thấy hồ sơ | Thông tin cá nhân được bảo vệ | BR-17 |
| US-25 | Người cần chỗ | Được gợi ý khu lân cận trong chuỗi khi khu đến đã hết chỗ | Vẫn có phương án đỗ | FR-27 |

**Nghiệm thu**

| AC | US | Given | When | Then |
|----|----|-------|------|------|
| AC-19 | US-19 | Chủ shophouse thấp tầng khu A và chủ căn hộ khu B | Yêu cầu chỗ ở tòa khu A, 7h–19h | Cấp **L2** tại khu A; chỉ ô phạm vi Khu/Chuỗi; không có quyền BR-05 tại khu A. Shophouse khối đế cùng tòa → **L1** (A-10) |
| AC-20 | US-20 | Cư dân khu B (L3 tại khu C); TH2 khu C mở Chuỗi | Yêu cầu chỗ khu C, 7h–8h và 16h30–17h30 | Ghép TH2 khu C, giá L3. Nếu TH2 chỉ mở trong khu → TH3 khu C (AC-02) |
| AC-21 | US-21 | Nhiều tư cách còn hiệu lực ở các khu khác | Yêu cầu chỗ tòa *T* bất kỳ | Lấy cấp **cao nhất** tại *T*; khu khác chỉ tính L3 (BR-15). Không đăng ký lại theo khu |
| AC-22 | US-22 | Tư cách người thuê căn hộ hết hiệu lực ngày *D* | Qua ngày *D* | Chặn yêu cầu **mới** (KPI "sai tư cách bị chặn"). Giao dịch đang hiệu lực giữ tới hết kỳ; thông báo người dùng và chủ chỗ. Kỳ tối đa: TBD |
| AC-23 | US-23 | Nội quy tòa cho TH1 mở cả khu | Chủ chỗ chọn "chỉ trong tòa" | Chỉ L1 của tòa được ghép. Không cho chọn rộng hơn nội quy |
| AC-24 | US-24 | Người dùng có tư cách đã xác minh ở khu B | Khu A kiểm tra tư cách người có tài sản ở khu B | Khu A chỉ nhận cấp và hạn hiệu lực; số căn hộ, giấy tờ, hồ sơ không hiển thị với BQL khu A |
| AC-25 | US-25 | Khu không còn ô phù hợp trong khung giờ yêu cầu, kể cả TH3 | Gửi yêu cầu chỗ đỗ | Gợi ý ô khu khác trong chuỗi mà người dùng đủ điều kiện; không tự đặt khi chưa xác nhận. "Lân cận" (khoảng cách / thời gian): TBD |

## Epic 1 — Định tuyến

**User story**

| US | Vai trò | Muốn | Để | FR / BR |
|----|---------|------|----|---------|
| US-01 | Người đạt phạm vi mở pool (ví dụ: cư dân không chỗ, người thuê, hộ 2 xe, shophouse, văn phòng, phòng khám, mầm non, thành viên chuỗi khi TH2 mở chuỗi; [PRD §3.2](02-prd.md#32-cấp-tư-cách-tại-vị-trí-chỗ-đỗ)) | Được ghép TH1 hoặc TH2 | Đỗ ngay nơi cần, rẻ hơn gửi ngoài | FR-01, FR-02 |
| US-02 | Người không đạt phạm vi mở: khách vãng lai, khách shophouse, thành viên chuỗi khi pool chỉ mở trong khu | Được chuyển TH3 hoặc bãi công cộng, giá đúng cấp | Có chỗ phù hợp với quyền của mình | FR-01, FR-03 |
| US-03 | BQL khu | Hệ thống chặn giao dịch sai tư cách hoặc sai phạm vi | Chia sẻ tuân thủ nội quy | FR-04 |

**Nghiệm thu**

| AC | US | Given | When | Then |
|----|----|-------|------|------|
| AC-01 | US-01 | Cấp tư cách tại ô nằm trong phạm vi mở của pool | Gửi yêu cầu chỗ đỗ | Ghép TH1 hoặc TH2 còn trống đúng phạm vi. Ưu tiên TH1 vs TH2: TBD |
| AC-02 | US-02 | Không đạt phạm vi mở của mọi pool TH1/TH2 còn trống (kể cả khách shophouse) | Gửi yêu cầu chỗ đỗ | Không ghép TH1/TH2; chuyển TH3 hoặc bãi công cộng của khu, giá theo cấp |
| AC-03 | US-03 | Yêu cầu, lịch chia sẻ hoặc giao dịch có vi phạm rõ ràng (PRD §5, *Chặn hay chuyển hướng*) | Rule engine kiểm tra | Từ chối kèm lý do và ghi nhận (KPI "sai tư cách hoặc sai phạm vi bị chặn") khi: TH1 cho người ngoài phạm vi ô (BR-01); cá nhân cho thuê TH3 (BR-03); ngoài phạm vi hoặc ngoài nền tảng chính thức (BR-04); cư dân thu phí hoặc dùng quyền ngoài tòa L1 (BR-05); tư cách đã hết hạn (BR-16). Người yêu cầu chỉ không đạt phạm vi mở thì **không** bị chặn mà được chuyển theo AC-02 |

## Epic 2 — Chia sẻ

**User story**

| US | Vai trò | Muốn | Để | FR / BR |
|----|---------|------|----|---------|
| US-04 | Chủ chỗ (cư dân TH1/TH2, văn phòng có chỗ riêng) | Được đề xuất khung giờ có thể chia sẻ | Khai thác chỗ đang bỏ trống | FR-05 |
| US-05 | Chủ chỗ | Có khoảng dự phòng khi chia sẻ | Không sợ mất chỗ khi về | FR-06 |
| US-06 | Người cần chỗ | Được ghép với chỗ chia sẻ mà mình đủ điều kiện thuê | Có chỗ tại nơi cần đến | FR-07 |
| US-07 | Chủ chỗ / người thuê | Nhận thỏa thuận điện tử theo mẫu khu có ô đỗ để xác nhận | Giảm rủi ro tranh chấp | FR-08 |
| US-08 | BQL khu | Mỗi thỏa thuận đã được hai bên xác nhận được lưu bằng chứng xác nhận | Có bằng chứng khi cần | FR-09 |

**Nghiệm thu**

| AC | US | Given | When | Then |
|----|----|-------|------|------|
| AC-04 | US-04 | Chủ chỗ TH1/TH2 hoặc văn phòng có chỗ riêng | Mở màn hình chia sẻ | Đề xuất khung giờ chia sẻ. Cơ sở dữ liệu đề xuất: TBD |
| AC-05 | US-05 | Chủ chỗ đăng một khung giờ chia sẻ | Lịch được lưu | Lịch có khoảng dự phòng theo nội quy khu (A-07); không ghép người thuê vào khoảng dự phòng. Độ dài: TBD |
| AC-06 | US-06 | Người cần chỗ có cấp tư cách tại ô và xe đã khai báo kích thước | Gửi yêu cầu trong một khung giờ | Chỉ ghép chỗ hợp lệ theo AC-01, AC-03 và phạm vi chủ chỗ (AC-23); ô đúng kích thước xe; xét khung giờ, dự phòng, ưu tiên. Không có ô TH1/TH2 → cấp TH3 cùng khu theo giá cấp (AC-02); hết TH3 → gợi ý theo AC-25 |
| AC-07 | US-07 | Ghép thành công | Hệ thống tạo thỏa thuận | Sinh thỏa thuận theo mẫu và khung giá nội quy của **khu có ô đỗ**; chỉ có hiệu lực khi **cả hai bên** xác nhận |
| AC-08 | US-08 | Hai bên đã xác nhận | Thỏa thuận có hiệu lực (đã qua BQL duyệt nếu vượt ngưỡng, AC-15) | Lưu bằng chứng xác nhận (chỉ ghi thêm); BQL khu có ô đỗ xem được thỏa thuận và bằng chứng |

## Epic 3 — Xử lý ngoại lệ

**User story**

| US | Vai trò | Muốn | Để | FR / BR |
|----|---------|------|----|---------|
| US-09 | Chủ chỗ về sớm | Lấy lại chỗ; người thuê được điều phối sang chỗ thay thế | Được bảo đảm quyền quay về | FR-10 |
| US-10 | Người thuê bị chủ về sớm | Được cấp chỗ thay thế từ TH3 cùng khu; nếu hết chỗ, được gợi ý khu lân cận | Vẫn có chỗ đỗ | FR-10, FR-27 |
| US-11 | Chủ chỗ | Người thuê đỗ quá giờ được nhắc và bị tính phí theo nội quy | Chỗ được trả đúng hạn | FR-11, FR-12 |

**Nghiệm thu**

| AC | US | Given | When | Then |
|----|----|-------|------|------|
| AC-09 | US-09, US-10 | Chỗ đang được người thuê dùng theo thỏa thuận | Chủ chỗ về sớm | Chủ được quay về chỗ. Agent điều phối chỗ thay thế từ TH3 cùng khu; hết chỗ → AC-25. Ai chịu chênh lệch: TBD |
| AC-10 | US-11 | Thỏa thuận chia sẻ có giờ kết thúc | Người thuê vẫn đỗ sau khung giờ thỏa thuận | Gửi nhắc nhở; tính phí theo nội quy khu có ô đỗ. Mức phí và thời điểm bắt đầu: TBD |
| AC-10a | — | Log LPR có mã sự kiện | Mã đó đã được xử lý trước đó | Không tạo thêm giao dịch hoặc cảnh báo trùng. OCR thấp vào hàng chờ kiểm tra, không kết luận tự động |

*AC-09 nghiệm thu cả US-09 và US-10. AC-10a (chống trùng log LPR) chưa gắn US.*

## Epic 4 — Tranh chấp

**User story**

| US | Vai trò | Muốn | Để | FR / BR |
|----|---------|------|----|---------|
| US-12 | BQL khu | Nhận ticket đã có ảnh, đã đối chiếu bằng chứng xác nhận và dữ liệu cổng (kể cả khi một bên là thành viên khu khác) | Xác minh nhanh, không xử lý thủ công | FR-13, FR-14, FR-16 |
| US-13 | Cư dân | Biển số được ẩn trong ticket | Dữ liệu cá nhân được bảo vệ | FR-15 |

**Nghiệm thu**

| AC | US | Given | When | Then |
|----|----|-------|------|------|
| AC-11 | US-12 | Người dùng báo tranh chấp kèm ảnh tại một ô của khu K | Tranh chấp phát sinh | Đọc ảnh, đối chiếu bằng chứng xác nhận và dữ liệu cổng, lập ticket, chuyển BQL khu có ô đỗ (kể cả thành viên khu khác, BR-18). Thời gian lập hồ sơ mục tiêu: TBD |
| AC-12 | US-13 | Ticket tranh chấp có biển số | Ticket được hiển thị, hoặc ngữ cảnh được gửi tới LLM | Biển số trong ticket ở dạng ẩn; chỉ BQL khu liên quan xem bản gốc; biển số và tên thay mã giả trước khi gửi LLM; mọi lượt xem bản gốc được ghi log |

## Epic 5 — Hoán đổi

**User story**

| US | Vai trò | Muốn | Để | FR / BR |
|----|---------|------|----|---------|
| US-14 | Người có chỗ không hợp nhu cầu (ví dụ SUV ở chỗ hẹp) hoặc có tranh chấp lặp lại | Được đề xuất hoán đổi trong cùng khu (2 bên hoặc nhiều bên theo vòng) | Có chỗ phù hợp hơn | FR-17 |
| US-15 | BQL khu | Phê duyệt đề xuất hoán đổi trước khi có hiệu lực | Kiểm soát thay đổi chỗ đỗ | FR-18 |

**Nghiệm thu**

| AC | US | Given | When | Then |
|----|----|-------|------|------|
| AC-13 | US-14 | Có tranh chấp lặp lại hoặc nhu cầu đã đăng ký | N5 hoặc người dùng kích hoạt W6 | Đề xuất hoán đổi 2 bên hoặc nhiều bên theo vòng; mọi ô cùng **một khu**. "Lặp lại" (số lần / khoảng thời gian): TBD |
| AC-14 | US-15 | Có đề xuất hoán đổi chờ duyệt | BQL khu duyệt hoặc từ chối | Hoán đổi chỉ có hiệu lực sau khi BQL khu phê duyệt; đề xuất bị từ chối không đổi phân bổ chỗ |

## Epic 6 — Ghép phù hợp và vận hành LPR

**User story**

| US | Vai trò | Muốn | Để | FR / BR |
|----|---------|------|----|---------|
| US-16 | Người cần chỗ | Chỉ được ghép vào ô đúng kích thước xe và khung giờ | Đỗ an toàn, không lấn vạch | FR-07 |
| US-17 | BQL khu | Log LPR trùng hoặc OCR độ tin cậy thấp được xử lý phù hợp | Dữ liệu sai không tạo giao dịch hay kết luận tự động | FR-16a |
| US-18 | Chủ chỗ | Xem gợi ý khung giờ thường trống theo lịch sử | Chọn thời gian chia sẻ phù hợp | FR-20 |

**Nghiệm thu**

| AC | US | Given | When | Then |
|----|----|-------|------|------|
| AC-17 | US-17 | Log của khu qua adapter hỗ trợ hoặc bộ mô phỏng | Worker xử lý log | Chuẩn hóa, gắn khu nguồn, chống trùng theo mã sự kiện; OCR thấp vào hàng chờ kiểm tra |
| AC-18 | US-18 | Có dữ liệu lịch sử ra/vào của khu | Hệ thống tạo dự báo | Dự báo theo giờ, thứ, ngày lễ như thông tin tham khảo; không tự đăng lịch chia sẻ. Độ chính xác mục tiêu và dữ liệu tối thiểu: TBD |

*US-16 chưa có AC riêng: nghiệm thu theo AC-06 (ô đúng kích thước xe).*

## AC chưa có user story

Tiêu chí bắt buộc của bản demo (HITL và thanh toán mô phỏng) nhưng chưa có US tương ứng.

| AC | US | Given | When | Then |
|----|----|-------|------|------|
| AC-15 | — | Giao dịch vượt ngưỡng định mức đã cấu hình cho khu có ô đỗ | Agent tạo đề xuất giao dịch | Chờ BQL khu duyệt; chưa có hiệu lực trước khi được duyệt |
| AC-16 | — | Người dùng thanh toán trong bản demo | Chọn VietQR mock | Chỉ ghi nhận trạng thái mô phỏng, không xác nhận thu tiền thật. Voucher shophouse chỉ cho lượt đỗ TH3; không nâng cấp tư cách, không cho khách shophouse thuê TH1/TH2 |

## Ưu tiên

Theo 3 mức của [Backlog §1](backlog/README.md#1-ba-mức-ưu-tiên): Ưu tiên 1 = bắt buộc, hết tuần 2 · Ưu tiên 2 = xong trước demo · Ưu tiên 3 = chưa cần ở demo.

| Mức | User Story |
|-----|-----------|
| **Ưu tiên 1** | US-01, US-02, US-03, US-05, US-06, US-07, US-08, US-16, US-19, US-20, US-21; phần chặn giao dịch mới khi hết hạn của US-22 |
| **Ưu tiên 2** | US-09, US-23, US-24, US-25; phần chỗ TH3 thay thế cùng khu của US-10; phần chống trùng log của US-17 |
| **Ưu tiên 3** | US-04, US-11, US-12, US-13, US-14, US-15, US-18; phần gợi ý khu lân cận của US-10; phần quét và thông báo hết hạn của US-22; phần OCR thấp và so khớp mờ của US-17 |
