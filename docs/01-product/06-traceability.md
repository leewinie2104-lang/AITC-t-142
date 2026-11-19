# Traceability — User Story → Use case

> File này trả lời: một US nối tới AC, FR/BR, workflow, use case và màn hình nào; và một use case phục vụ US nào.

> Nguồn: [User Stories & AC](04-user-stories.md) · [PRD](02-prd.md) · [Modules](backlog/01-modules.md) · [Workflow AI](backlog/02-agent-workflows.md) · [Workflow nền](backlog/03-background-workflows.md)
> Kiến trúc: [ADR-0010](../10-adr/ADR-0010-backend-modules-agent-workflows-jobs.md) · [Cấu trúc server](../05-development/01-server-structure.md)

**Cách dùng:** chọn US ở mục 1, lấy use case chính, tra mục 2 nếu cần đủ danh sách. Module (M) dùng skill `new-usecase`; W (Agent) dùng `new-agent-workflow`; N (job nền) dùng `new-background-job`. Tên use case là **đề xuất** theo ADR-0010; `server/src/app/*/usecase/` chưa có file. **TBD** = chưa có nguồn hoặc quyết định.

## 1. Bảng tổng

Một dòng mỗi US, nhóm theo epic. Ưu tiên: [User Stories §Ưu tiên](04-user-stories.md#ưu-tiên). Cột *Use case chính* ghi 1–3 use case; `+N` là số còn lại, tra mục 2. TBD ở cột Màn hình = chưa có wireframe.

| US · AC | FR / BR | Workflow / Job | Use case chính | Màn hình |
|---|---|---|---|---|
| **Epic 0 — Tư cách và liên khu** | | | | |
| US-19 · AC-19 | FR-01, FR-23, FR-24 · BR-15 | W1 bước 2 | `eligibility.resolve_level`, `policy.check_rental_right` | TBD |
| US-20 · AC-20 | FR-07, FR-24, FR-26 · BR-02, BR-15 | W1 bước 2–5 | `booking.request_parking`, `eligibility.attest_cross_zone` +2 | TBD |
| US-21 · AC-21 | FR-23, FR-24 · BR-15 | W1 bước 2 | `eligibility.resolve_level`, `eligibility.verify_credential` | TBD |
| US-22 · AC-22 | FR-25 · BR-16 | N6 (+ W1 kiểm tra hạn) | `eligibility.expire_credentials`, `policy.check_rental_right` +1 | TBD |
| US-23 · AC-23 | FR-26 · PRD §4 | W2 bước 2 (bổ sung: chọn phạm vi) | `policy.validate_share_scope`, `sharing.create_share_slot` | TBD |
| US-24 · AC-24 | BR-17 | W1 bước 2 · API xác nhận liên khu | `eligibility.attest_cross_zone` | TBD |
| US-25 · AC-25 | FR-27 · — | W1 bổ sung · W3 bổ sung | `booking.suggest_other_zone`, `policy.check_rental_right` +1 | TBD |
| **Epic 1 — Định tuyến** | | | | |
| US-01 · AC-01 | FR-01, FR-02 · BR-01, BR-15 | W0 → W1 | `booking.request_parking`, `eligibility.resolve_level`, `policy.check_rental_right` +6 | [request-parking](ux/wireframes/request-parking.html) |
| US-02 · AC-02 | FR-01, FR-03 · BR-19 | W1 bước 7 | `booking.request_parking`, `booking.assign_th3_slot` +3 | [request-parking](ux/wireframes/request-parking.html) |
| US-03 · AC-03 | FR-04 · BR-01, BR-03, BR-04, BR-05, BR-16 | W1 bước 3–4 | `policy.check_rental_right`, `booking.request_parking` +1 | [request-parking](ux/wireframes/request-parking.html) |
| **Epic 2 — Chia sẻ** | | | | |
| US-04 · AC-04 | FR-05, FR-20 | W2 bước 1 · W2 bổ sung · N4 | `sharing.forecast_free_windows`, `sharing.suggest_share_windows`, `sharing.create_share_slot` | [owner-share-schedule](ux/wireframes/owner-share-schedule.html), [owner-home](ux/wireframes/owner-home.html) |
| US-05 · AC-05 | FR-06 · BR-07 | W2 bước 3 | `sharing.create_share_slot` | [owner-share-schedule](ux/wireframes/owner-share-schedule.html), [owner-home](ux/wireframes/owner-home.html) |
| US-06 · AC-06 | FR-07 · BR-11 | W2 bước 4 · W1 bước 5 | `sharing.match_share_slot`, `booking.request_parking` +1 | [request-parking](ux/wireframes/request-parking.html) |
| US-07 · AC-07 | FR-08 · BR-04 | W2 bước 5–6 | `ledger.generate_agreement`, `ledger.confirm_agreement` | [agreement](ux/wireframes/agreement.html) |
| US-08 · AC-08 | FR-09 · PRD §9 (bằng chứng xác nhận) | W2 bước 8 | `ledger.record_confirmation` | [admin-ledger](ux/wireframes/admin-ledger.html) |
| **Epic 3 — Xử lý ngoại lệ** | | | | |
| US-09 · AC-09 | FR-10 · BR-07 | W3 (M9 TBD) | `agent.start_workflow`, `access.get_active_stay` +3 | [owner-early-return](ux/wireframes/owner-early-return.html), [owner-home](ux/wireframes/owner-home.html) |
| US-10 · AC-09 | FR-10, FR-27 · BR-07 | W3 bước 3–4 · W3 bổ sung (khu lân cận) (M9 TBD) | `agent.start_workflow`, `booking.assign_th3_slot` +3 | [owner-early-return](ux/wireframes/owner-early-return.html), [renter-booking](ux/wireframes/renter-booking.html) |
| US-11 · AC-10 | FR-11, FR-12 · BR-08 | N2 → W4 | `access.detect_overstay`, `agent.start_workflow` +3 | [renter-booking](ux/wireframes/renter-booking.html), [owner-home](ux/wireframes/owner-home.html) |
| **Epic 4 — Tranh chấp** | | | | |
| US-12 · AC-11 | FR-13, FR-14, FR-16 · BR-18 | W5 bước 1–8 (HITL bước 7) | `dispute.create_ticket`, `dispute.review_ticket` +5 | [dispute-report](ux/wireframes/dispute-report.html), [admin-disputes](ux/wireframes/admin-disputes.html), [admin-dispute-detail](ux/wireframes/admin-dispute-detail.html) |
| US-13 · AC-12 | FR-15 · BR-09, BR-14 | W5 bước 2, 6 | `dispute.create_ticket`, `dispute.reveal_plate` | [dispute-report](ux/wireframes/dispute-report.html), [admin-disputes](ux/wireframes/admin-disputes.html), [admin-dispute-detail](ux/wireframes/admin-dispute-detail.html) |
| **Epic 5 — Hoán đổi** | | | | |
| US-14 · AC-13 | FR-17 · BR-10 | N5 → W6 | `dispute.detect_repeat`, `swap.propose_swap` +2 | [swap-proposal](ux/wireframes/swap-proposal.html), [admin-swaps](ux/wireframes/admin-swaps.html) |
| US-15 · AC-14 | FR-18 · BR-10 | W6 bước 4–6 (HITL) | `swap.apply_swap`, `approval.decide_pending` +2 | [admin-swaps](ux/wireframes/admin-swaps.html) |
| **Epic 6 — Ghép phù hợp và vận hành LPR** | | | | |
| US-16 · AC-06 (phần kích thước ô) | FR-07 · BR-11 | W1 bước 5 | `facility.check_slot_fits`, `booking.request_parking` | [request-parking](ux/wireframes/request-parking.html) |
| US-17 · AC-17, AC-10a | FR-16a · BR-13 | N1 | `access.ingest_lpr_log` | [admin-lpr-review](ux/wireframes/admin-lpr-review.html) |
| US-18 · AC-18 | FR-20 | N4 → W2 bổ sung | `sharing.forecast_free_windows` | [owner-share-schedule](ux/wireframes/owner-share-schedule.html) |

## 2. Danh mục use case

34 use case có ít nhất một US. Cột *Dùng bởi US* là đảo ngược của mục 1. Use case không gắn US nằm ở mục 3.

| Use case | Mô tả | Vào → ra | Quy tắc | Dùng bởi US |
|---|---|---|---|---|
| **M1 `eligibility` — Tư cách** | | | | |
| `eligibility.resolve_level` | Cấp L1–L4 tại tòa/khu của ô, kèm hạn. | user, tòa/khu → cấp, hạn | FR-24, BR-15, A-10 | US-01, US-02, US-03, US-19, US-21 |
| `eligibility.attest_cross_zone` | Trả khu khác kết quả xác nhận (cấp, hạn), không trả hồ sơ. | user, khu yêu cầu → cấp, hạn | BR-17, AC-24 | US-20, US-24 |
| `eligibility.verify_credential` | BQL khu xác minh tài sản, vai trò, hạn của tư cách. | tư cách, khu → đã xác minh | FR-23, A-09 | US-21 |
| `eligibility.expire_credentials` | Job N6: đánh dấu hết hạn, tìm giao dịch hiệu lực, gửi thông báo. | lịch quét ngày → hết hiệu lực; thông báo | FR-25, BR-16 | US-22 |
| **M3 `policy` — Rule engine & cấu hình** | | | | |
| `policy.check_rental_right` | Rule engine tất định: cấp × phạm vi mở của pool; chặn nếu sai. | cấp, pool, phạm vi, hạn → cho phép / chặn + lý do | FR-04, BR-01, BR-03, BR-04, BR-05, BR-16 | US-01, US-02, US-03, US-19, US-20, US-22, US-25 |
| `policy.quote_price` | Giá thuê theo cấp tại ô. | cấp, ô, khung giờ → đơn giá | BR-19, PRD §8 (giá L3 và TH3: TBD) | US-01, US-02, US-20 |
| `policy.validate_share_scope` | Phạm vi chủ chỗ chọn chỉ được thu hẹp, không vượt nội quy. | phạm vi, nội quy pool → hợp lệ / từ chối | FR-26, PRD §4, AC-23 | US-23 |
| **M2 `facility` — Xe & ô đỗ** | | | | |
| `facility.check_slot_fits` | Kích thước ô phù hợp kích thước xe. | ô, xe → phù hợp / không | BR-11, FR-07 | US-01, US-06, US-14, US-16, US-25 |
| **M4 `sharing` — Chia sẻ** | | | | |
| `sharing.forecast_free_windows` | Job N4 hằng đêm: dự báo khung giờ trống. Chỉ gợi ý. | lịch sử ra/vào → dự báo (không tự đăng lịch) | FR-20, AC-18 | US-04, US-18 |
| `sharing.suggest_share_windows` | Đề xuất khung giờ chia sẻ cho chủ chỗ, dựa trên dự báo. | chủ chỗ, ô → danh sách khung giờ | FR-05, AC-04 (cơ sở dữ liệu: TBD) | US-04 |
| `sharing.create_share_slot` | Tạo lịch chia sẻ + khoảng dự phòng; chặn TH3. | ô, khung giờ, dự phòng, phạm vi → lịch | FR-06, BR-03, BR-04, AC-05 (độ dài: TBD) | US-04, US-05, US-23 |
| `sharing.match_share_slot` | Ghép cầu với lịch hợp lệ (giờ, kích thước, dự phòng, phạm vi). | yêu cầu, lịch chia sẻ → ghép / không | FR-07, AC-06 | US-01, US-06 |
| **M5 `booking` — Đặt chỗ** | | | | |
| `booking.request_parking` | Nhận yêu cầu, định tuyến theo cấp, giữ chỗ tạm. | khu, tòa, khung giờ, xe → ghép / TH3 / chặn + lý do | FR-01, FR-02, FR-03 | US-01, US-02, US-03, US-06, US-16, US-20 |
| `booking.assign_th3_slot` | Cấp ô TH3 cùng khu, giá theo cấp (thiếu TH1/TH2 hoặc chủ về sớm). | cấp, khu, khung giờ → ô TH3 / hướng dẫn bãi công cộng | FR-03, FR-10, BR-03, BR-06 | US-02, US-09, US-10 |
| `booking.suggest_other_zone` | Gợi ý ô khu khác đủ điều kiện. Không tự đặt. | yêu cầu, danh sách khu → gợi ý (người dùng tự chọn) | FR-27, AC-25 (khoảng cách: TBD) | US-10, US-25 |
| **M6 `ledger` — Thỏa thuận & bằng chứng xác nhận** | | | | |
| `ledger.generate_agreement` | Sinh thỏa thuận điện tử theo mẫu của khu có ô đỗ. | giao dịch đã ghép → thỏa thuận | FR-08, BR-04 | US-07 |
| `ledger.confirm_agreement` | Ghi OTP xác nhận của từng bên; hiệu lực khi đủ hai bên. | thỏa thuận, OTP → trạng thái xác nhận | AC-07 (OTP có thời hạn: M6 BE) | US-07 |
| `ledger.record_confirmation` | Lưu bằng chứng hai bên xác nhận: chỉ ghi thêm. | thỏa thuận đã xác nhận → bản ghi bằng chứng | FR-09, PRD §9 (toàn vẹn) | US-08, US-09, US-11 |
| **M7 `payment` — Thanh toán** | | | | |
| `payment.charge_overstay_fee` | Phí quá giờ theo nội quy khu; trạng thái VietQR mock. | lượt quá giờ, nội quy khu → khoản phí, trạng thái | FR-12, FR-21, BR-08 (mức phí: TBD) | US-11 |
| **M8 `access` — LPR & lượt đỗ** | | | | |
| `access.ingest_lpr_log` | Job N1: chuẩn hóa log, gắn khu, bỏ trùng mã; OCR thấp vào hàng chờ. | log CSV / mô phỏng → sự kiện; hàng chờ OCR | FR-16a, FR-19, BR-13, AC-10a, AC-17 | US-17 |
| `access.get_active_stay` | Lượt đỗ đang diễn ra của ô hoặc người thuê. | ô hoặc người dùng → lượt đỗ hiện tại | W3 bước 2 (ADR-0010: access = M8 lượt đỗ) | US-09, US-10 |
| `access.detect_overstay` | Job N2: quét lượt hết giờ, trừ khoảng trễ, kích hoạt W4. | lượt đang mở → sự kiện OverstayDetected | FR-11; khoảng trễ và chu kỳ: TBD | US-11 |
| **M10 `dispute` — Tranh chấp** | | | | |
| `dispute.create_ticket` | Lập ticket từ ảnh, đối chiếu bằng chứng xác nhận và cổng; biển số ẩn. | báo cáo, ảnh, đối chiếu → ticket chờ BQL | FR-15, FR-16, BR-09, BR-18 | US-12, US-13 |
| `dispute.reveal_plate` | BQL khu liên quan xem biển số gốc; ghi log mỗi lượt. | ticket, người xem, lý do → biển số gốc (có log) | BR-09, PRD §9 (riêng tư) | US-13 |
| `dispute.review_ticket` | BQL khu có ô xác minh và đóng ticket. | ticket, quyết định → ticket đã đóng | BR-18, FR-16 | US-12 |
| `dispute.detect_repeat` | Job N5: đếm tranh chấp theo ô hoặc cặp người dùng; vượt ngưỡng → W6. | tranh chấp trong khu → sự kiện lặp | FR-17 (ngưỡng: TBD) | US-14 |
| **M11 `swap` — Hoán đổi** | | | | |
| `swap.propose_swap` | Đề xuất hoán đổi hai bên, mọi ô trong cùng khu. | nhu cầu đăng ký, lịch sử tranh chấp → đề xuất | FR-17, BR-10, AC-13 | US-14 |
| `swap.apply_swap` | Áp phân bổ mới sau khi BQL duyệt; từ chối giữ nguyên. | đề xuất đã duyệt → phân bổ chỗ mới | FR-18, BR-10, AC-14 | US-15 |
| **M12 `approval` — Hàng chờ duyệt (HITL)** | | | | |
| `approval.enqueue_pending` | Đưa workflow dừng ở HITL vào hàng chờ của khu có ô. | thread_id, zone_id → mục chờ | BR-12, BR-18, ADR-0010 | US-12, US-15 |
| `approval.decide_pending` | BQL duyệt hoặc từ chối; duyệt thì enqueue resume workflow. | mục chờ, quyết định, người duyệt → duyệt / từ chối | BR-10, BR-12, FR-18 | US-12, US-15 |
| **M13 `notification` — Thông báo** | | | | |
| `notification.notify_user` | Thông báo trong app (realtime) cho người liên quan. | người nhận, loại sự kiện → thông báo | FR-10, FR-11, FR-25; M13 | US-01, US-09, US-10, US-11, US-12, US-22 |
| **M14 `agent` — Agent (W0–W7)** | | | | |
| `agent.chat_turn` | W0 Supervisor: guardrail, ẩn danh, phân loại ý định, chuyển workflow, stream. | tin nhắn chat → câu trả lời stream | BR-14 | US-01 |
| `agent.start_workflow` | Điểm vào chung W1–W7 từ chat, app hoặc job (ví dụ POST early-return W3). | mã workflow, ngữ cảnh → workflow run | ADR-0010 | US-01, US-09, US-10, US-11, US-12, US-14 |
| `agent.resume_workflow` | Tiếp tục workflow đang chờ BQL duyệt. | thread_id, quyết định duyệt → workflow tiếp tục | BR-12, ADR-0010 | US-12, US-15 |

## 3. Chức năng chưa có user story
Mục backlog chưa có US. Cột *Mức* theo Ưu tiên 1/2/3 của [Backlog §1](backlog/README.md#1-ba-mức-ưu-tiên). Cần viết US hoặc xác nhận bỏ.

| Chức năng | Module | Mức | Nguồn và ghi chú |
|---|---|---|---|
| Đăng ký, đăng nhập, đăng xuất, hồ sơ | identity (M1) | 1 (đăng nhập, đăng xuất) · 2 (đăng ký, hồ sơ) | [01-modules §1](backlog/01-modules.md); [register](ux/wireframes/register.html). Xác thực [JWT tự cấp](../10-adr/ADR-0006-self-issued-jwt-auth.md). |
| Xem danh sách tư cách của mình | eligibility (M1) | 2 | 01-modules §1. US-21 nêu tự áp tư cách, chưa có màn hình xem. |
| Quên mật khẩu; rút lại đồng ý xử lý dữ liệu | identity (M1) | 3 | 01-modules §2. Rút đồng ý: TBD (A-03). |
| BQL thu hồi tư cách | eligibility (M1) | 3 | 01-modules §2. Có `eligibility.verify_credential` (US-21); thu hồi chưa có. |
| Thêm, sửa, xóa xe (biển số, kích thước) | facility (M2) | 2 (seed xe: 1) | 01-modules §1. US-16 dựa vào kích thước xe, chưa có US quản lý xe. |
| Danh sách ô và trạng thái; sơ đồ bãi realtime | facility (M2) | 2 (danh sách) · 3 (sơ đồ) | 01-modules §1–2. Có thể gắn US-01 hoặc US-06. |
| Cấu hình phạm vi mở, khung giá, ngưỡng duyệt của pool | policy (M3) | 1 (bằng seed) · 3 (BQL chỉnh) | 01-modules §1; FR-26. Đề xuất `policy.set_pool_scope` (TBD). |
| Hỏi đáp nội quy (RAG theo khu) | knowledge (M3 · W7) | 2 | 02-agent-workflows W7. Chưa có US và use case. |
| Trích dẫn nguồn; bộ nhớ hội thoại; eval và trace | agent (M14) | 2 (trích dẫn, eval, trace) · 3 (bộ nhớ) | 01-modules §2; 02-agent-workflows §2. |
| Guardrail và ẩn danh trước khi gửi LLM (BR-14) | agent (M14) | 1 | 02-agent-workflows W0 bước 2–3. Thuộc `agent.chat_turn` và LLMPort. Chỉ US-13 nêu một phần. |
| Xem lượt đỗ hiện tại; lịch sử và hủy đặt chỗ | booking (M5) | 2 | 01-modules §1–2; [renter-booking](ux/wireframes/renter-booking.html). Có màn hình, US chưa nêu. |
| Thu nhập và lịch sử chia sẻ | sharing (M4) | 3 | 01-modules §2. |
| Sửa, hủy lịch chia sẻ; nút "Tôi về sớm" trên lịch | sharing (M4) | 1 (hủy) · 2 (sửa, nút về sớm) | 01-modules §1. Tạo lịch có US-04/05; sửa, hủy chưa có. |
| Duyệt giao dịch vượt ngưỡng (FR-09a, AC-15, BR-12) | approval (M12) | 1 | 01-modules §1; 02-agent-workflows W2 bước 7. **Quan trọng:** `approval.*` chỉ có US-12, US-15; cần US riêng cho BQL. |
| VietQR mock và trạng thái thanh toán chia sẻ (FR-21, AC-16) | payment (M7) | 1 | 01-modules §1; [payment](ux/wireframes/payment.html). Đề xuất `payment.create_vietqr_mock` (TBD). |
| Voucher shophouse: tạo, áp dụng cho lượt TH3 (FR-22, AC-16) | payment (M7) | 3 | FR-22; [shophouse-voucher](ux/wireframes/shophouse-voucher.html). AC-16 không gắn US. |
| Lịch sử giao dịch | payment (M7) | 3 | 01-modules §2. |
| Xem bằng chứng xác nhận | ledger (M6) | 2 | 01-modules §2; [admin-ledger](ux/wireframes/admin-ledger.html). US-08 chỉ nêu lưu bằng chứng. |
| Thỏa thuận bị từ chối hoặc hết hạn chờ | ledger (M6) | 2 | 01-modules §2. |
| Dòng thời gian ra vào; hàng chờ OCR thấp cho bảo vệ và BQL | access (M8) | 3 | 01-modules §2; [admin-lpr-review](ux/wireframes/admin-lpr-review.html). Hàng chờ OCR có US-17. |
| Adapter webhook / MQTT; so khớp mờ biển số (FR-16a, FR-19) | access (M8) | 3 | FR-19; 03-background-workflows N1 (bổ sung). US-17 chỉ nêu log CSV và mô phỏng. |
| Phát hiện về sớm từ LPR (kích hoạt W3 từ N1) | access (M8) · agent (W3) | 3 | 02-agent-workflows W3 (bổ sung). Chưa có use case. M9 chưa có thư mục (TBD). |
| Đăng ký nhu cầu đổi chỗ; cư dân xem trạng thái hoán đổi | swap (M11) | 3 | 01-modules §2. US-14 nêu đề xuất từ nhu cầu đã đăng ký, chưa có US đăng ký. |
| Đối soát cuối ngày (N3) gửi BQL khu | reporting (M12) | 3 | 03-background-workflows N3. |
| Dashboard KPI theo khu; tình trạng nguồn LPR; hàng chờ ticket và hoán đổi | reporting (M12) | 2 (KPI cơ bản) · 3 (nguồn LPR, hàng chờ ticket, hoán đổi) | 01-modules §2; [admin-dashboard](ux/wireframes/admin-dashboard.html). Chỉ số: [Scope §6](03-scope.md#6-chỉ-số-theo-dõi). |
| Thông báo trong app realtime; đánh dấu đã đọc | notification (M13) | 1 (trong app) · 2 (realtime, đã đọc) | 01-modules §1; [notifications](ux/wireframes/notifications.html). Đánh dấu đã đọc chưa có US. |
| Nhắc tư cách sắp hết hạn | notification (M13) · eligibility (N6) | 3 | 01-modules §2 (M13). US-22 chỉ nêu thông báo khi đã hết hạn. |
