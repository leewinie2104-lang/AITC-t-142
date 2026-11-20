# 05 — Backlog 4 tuần

> **File này trả lời:** mỗi tính năng cần làm gì ở DB, BE, worker và FE; mức ưu tiên và tuần xong.
> Bản xem có bộ lọc: [05-backlog.html](05-backlog.html) · Liên quan: [PRD](02-prd.md) · [Traceability](06-traceability.md) · [ADR-0010](../07-adr/ADR-0010-backend-modules-agent-workflows-jobs.md)

## 1. Cách đọc

Mỗi dòng là **một tính năng**; mỗi ô có nội dung là **một task** cho người làm cột đó; "—" là không cần.

| Cột | Người làm | Code ở |
|-----|-----------|--------|
| **DB** | DB / seed | `server/migrations/`, seed |
| **BE** | Server core | `server/src/app/<module>/` (usecase + `delivery/rest/`) |
| **Worker nền** | Server core / Hạ tầng | `<module>/delivery/jobs/`, queue `bg`, đăng ký ở `main_worker.py` |
| **Worker Agent** | AI Agent | `agent/` (W0–W7), queue `agent` |
| **FE** | Client | `client/` |

- **Mức:** **1** siêu cần thiết (xong hết tuần 2) · **2** cố gắng trước demo (tuần 3) · **3** nếu còn thời gian (§6).
- **Tuần 4:** chỉ sửa lỗi, test tích hợp, eval, demo. Mốc: cuối tuần 2 luồng chính chạy end-to-end; cuối tuần 3 đóng băng tính năng.
- Mã **N1–N9** (worker nền) giải thích ở §4, mã **W0–W7** (worker Agent) ở §5.
- Endpoint bỏ tiền tố `/api/v1`. Worker Agent: LLM chỉ gợi ý, rule engine quyết định (BR-14); `[HITL]` chờ BQL của khu có ô duyệt.

## 2. Tính năng

### M1 — Tài khoản & tư cách

| Tính năng | Mức | Tuần | DB | BE | Worker nền | Worker Agent | FE |
|-----------|-----|------|----|----|------------|--------------|----|
| Đăng nhập | 1 | 1 | `app_user`, seed 5 vai trò | `POST /auth/login` (JWT 8 giờ; khóa tạm theo `failed_logins` / `locked_until`) | — | — | Màn đăng nhập |
| Lấy người dùng + tư cách | 1 | 1 | `asset`, `eligibility` | `GET /me` (cấp L1–L4, hạn) | — | — | Thông tin trên header |
| Đăng xuất | 2 | 3 | — | `POST /auth/logout` | — | — | Nút đăng xuất |
| Đăng ký kèm đồng ý | 2 | 3 | `consent_record`: 2 dòng `registration_terms`, `plate_processing` | `POST /registrations` | — | — | Màn đăng ký |
| Xem hồ sơ & tư cách | 2 | 3 | — | dùng `GET /me` | — | — | Màn hồ sơ |

### M2 — Khu, tòa, ô, xe

| Tính năng | Mức | Tuần | DB | BE | Worker nền | Worker Agent | FE |
|-----------|-----|------|----|----|------------|--------------|----|
| Dữ liệu khu, tòa, ô | 1 | 1 | `zone`, `building`, `slot_pool`, `slot`; seed 3 khu | — | — | — | — |
| Xem xe của tôi | 1 | 1 | `vehicle` (biển số mã hóa) | `GET /me/vehicles` | — | — | Danh sách xe |
| Thêm xe | 2 | 3 | — | `POST /me/vehicles` | — | — | Form thêm xe |
| Sửa xe | 2 | 3 | — | `PATCH /me/vehicles/{id}` | — | — | Form sửa xe |
| Xóa xe | 2 | 3 | — | `DELETE /me/vehicles/{id}` (xóa mềm `is_active = false`: booking, LPR còn tham chiếu) | — | — | Nút xóa |

### M3 — Nội quy & rule engine

| Tính năng | Mức | Tuần | DB | BE | Worker nền | Worker Agent | FE |
|-----------|-----|------|----|----|------------|--------------|----|
| Nội quy từng khu | 1 | 1 | `zone_policy` seed: giá, dự phòng, ngưỡng duyệt, phạm vi mở, mẫu thỏa thuận | — | — | — | — |
| Kiểm tra quyền thuê | 1 | 1 | — | Rule engine `policy/`: cấp × phạm vi mở; unit test | — | Gọi trong W1, W2 | — |
| Tính phí theo cấp | 1 | 2 | — | Use case trong `policy/` | — | Gọi trong W2, W3 | — |
| Xem nội quy khu | 2 | 3 | — | `GET /zones/{id}/rules` | — | — | Màn nội quy |
| Hỏi đáp nội quy | 2 | 3 | `knowledge_chunk` + nạp nội quy | — | — | W7: RAG theo khu / tòa, có trích dẫn | Dùng lại màn chat |

### M14 — Chat với Agent

| Tính năng | Mức | Tuần | DB | BE | Worker nền | Worker Agent | FE |
|-----------|-----|------|----|----|------------|--------------|----|
| Gửi tin nhắn chat | 1 | 1 | `agent_thread`, `ai_decision_log` | `POST /chat/stream` (SSE) | — | W0: guardrail, mã giả, phân loại ý định | Màn chat |
| Xem lại hội thoại | 2 | 3 | — | `GET /agent/threads/{id}`: chỉ trả trạng thái, `pending_card` và tin đã mã giả (DB không lưu nội dung, BR-14) | — | — | Tải lại lịch sử chat |

### M5 — Đặt chỗ

| Tính năng | Mức | Tuần | DB | BE | Worker nền | Worker Agent | FE |
|-----------|-----|------|----|----|------------|--------------|----|
| Xin chỗ qua chat | 1 | 2 | `parking_request`, `booking`, `slot_holding` | Use case giữ chỗ tạm (`hold_ttl`) | N9: giữ chỗ quá hạn → `expired` | W1: tính cấp, rule engine, ghép | Thẻ kết quả ghép trong chat |
| Chuyển TH3 / bãi công cộng | 1 | 2 | — | — | — | W1: nhánh không đủ quyền / hết ô | Thẻ kết quả kèm lý do |
| Gợi ý ô khu khác (FR-27) | 2 | 3 | — | — | — | W1: bước `[LLM]` gợi ý | Chọn ô được gợi ý |
| Xem lượt đỗ hiện tại | 2 | 3 | — | `GET /me/bookings/current` | — | — | Màn lượt đỗ (kể cả quá giờ) |
| Xem yêu cầu của tôi | 2 | 3 | — | `GET /me/parking-requests` | — | — | Danh sách yêu cầu |

### M4 — Chia sẻ chỗ

| Tính năng | Mức | Tuần | DB | BE | Worker nền | Worker Agent | FE |
|-----------|-----|------|----|----|------------|--------------|----|
| Đăng lịch chia sẻ | 1 | 2 | `share_window` | `POST /share-windows` (dự phòng, chặn TH3) | — | W2: ghép người thuê theo phạm vi mở | Màn chia sẻ |
| Hủy lịch chia sẻ | 1 | 2 | — | `DELETE /share-windows/{id}` | — | — | Nút hủy |
| Xem lịch chia sẻ của tôi | 2 | 3 | — | `GET /me/share-windows` | — | — | Danh sách lịch |

### M6 — Thỏa thuận & bằng chứng

| Tính năng | Mức | Tuần | DB | BE | Worker nền | Worker Agent | FE |
|-----------|-----|------|----|----|------------|--------------|----|
| Xem thỏa thuận | 1 | 2 | `agreement` | `GET /agreements/{id}` | — | W2: sinh thỏa thuận theo mẫu khu | Màn thỏa thuận |
| Xác nhận bằng OTP | 1 | 2 | `consent_record` (chỉ ghi thêm); OTP trong Redis | `POST /agreements/{id}/confirm` | — | W2: chờ đủ hai bên | Nhập OTP |
| Gửi lại OTP | 2 | 3 | — | `POST /agreements/{id}/otp/resend` | — | — | Nút gửi lại |
| Thỏa thuận bị từ chối / hết hạn | 2 | 3 | — | — | N9: quá `confirm_deadline` → `expired` | W2: nhánh từ chối / hết hạn | Trạng thái thỏa thuận |
| BQL xem bằng chứng xác nhận | 2 | 3 | — | `GET /zones/{id}/agreements/{id}/evidence` | — | — | Màn bằng chứng |

### M12 — BQL duyệt & KPI

| Tính năng | Mức | Tuần | DB | BE | Worker nền | Worker Agent | FE |
|-----------|-----|------|----|----|------------|--------------|----|
| Hàng chờ duyệt | 1 | 2 | `approval_request` | `GET /zones/{id}/approvals` | N9: quá `due_at` → `expired` | Tạo yêu cầu `[HITL]`: W2 vượt ngưỡng (mức 1); W3 về sớm, W5 tranh chấp (mức 2) | Màn hàng chờ |
| Duyệt / từ chối | 1 | 2 | — | `POST /approvals/{id}/decision` (W2, W3; tranh chấp đi qua `/disputes/{id}/decision`) | — | `resume_workflow` chạy tiếp graph | Nút duyệt / từ chối |
| Xem chi tiết yêu cầu duyệt | 2 | 3 | — | `GET /approvals/{id}` | — | — | Màn chi tiết |
| KPI theo khu | 2 | 3 | view `kpi_daily_v` (yêu cầu, chặn, phí quá giờ, tranh chấp) | `GET /zones/{id}/kpis` | — | — | Dashboard KPI |
| BQL xem nhật ký quyết định AI | 2 | 3 | `ai_decision_log` (chỉ hash, chỉ ghi thêm) | `GET /zones/{id}/ai-decisions` | — | — | Màn nhật ký AI (kiểm chứng BR-14) |

### M13 — Thông báo

| Tính năng | Mức | Tuần | DB | BE | Worker nền | Worker Agent | FE |
|-----------|-----|------|----|----|------------|--------------|----|
| Xem thông báo | 1 | 2 | `notification` (khóa idempotency) | `GET /me/notifications` | — | — | Màn thông báo (polling) |
| Đánh dấu đã đọc | 2 | 3 | — | `POST /me/notifications/{id}/read` | — | — | Chấm chưa đọc |

### M7 — Thanh toán

| Tính năng | Mức | Tuần | DB | BE | Worker nền | Worker Agent | FE |
|-----------|-----|------|----|----|------------|--------------|----|
| Thanh toán VietQR mock | 2 | 3 | `payment` | `GET /payments/{id}`, `POST /payments/{id}/mock-confirmation` | — | W2: khoản `share_booking`; W1: khoản `th3_visit` khi chuyển TH3 | Màn mã QR |
| Xem các khoản cần trả | 2 | 3 | — | `GET /me/payments` | — | — | Danh sách khoản |

### M8 — LPR & ra vào

| Tính năng | Mức | Tuần | DB | BE | Worker nền | Worker Agent | FE |
|-----------|-----|------|----|----|------------|--------------|----|
| Nạp log LPR | 1 | 2 | `lpr_event`; CSV mô phỏng 3 khu (trùng, OCR thấp, quá giờ) | `POST /dev/lpr-events/import` | N1: chuẩn hóa, mã hóa biển số, bỏ trùng, OCR dưới ngưỡng → `pending_review`, ghi giờ vào / ra | — | — |
| Xem log ra vào | 2 | 3 | — | `GET /zones/{id}/lpr-events` | — | — | Màn log (nếu cần) |

### M9 — Chủ về sớm & quá giờ

| Tính năng | Mức | Tuần | DB | BE | Worker nền | Worker Agent | FE |
|-----------|-----|------|----|----|------------|--------------|----|
| Chủ báo về sớm | 2 | 3 | `recovery_case` | `POST /bookings/{id}/early-return` | — | W3: tìm ô TH3 trống cùng khu kèm giá | Nút "Tôi về sớm" |
| Người thuê chấp nhận chỗ thay thế | 2 | 3 | `consent_record` (`accept_relocation`) | `POST /recovery-cases/{id}/accept` | N9: quá `deadline_at` → báo W3 | W3: đổi booking; từ chối / hết ô → `[HITL]` | Màn chấp nhận |
| Khoản TH3, hoàn tiền khi về sớm | 2 | 3 | — | — | — | W3: khoản `relocation_th3`, `early_return_refund` (D-09) | — |
| Xem trạng thái ca về sớm | 2 | 3 | — | `GET /recovery-cases/{id}` | — | — | Trạng thái ca |
| Nhắc sắp / đã hết giờ | 2 | 3 | — | — | N2: cron 5 phút, 2 lần nhắc, khóa `overstay_pre` / `overstay_due` | — | Hiện trong thông báo |
| Phí quá giờ khi xe ra | 2 | 3 | — | — | N1 ghi giờ ra | W4: miễn 10 phút, 12 500 đ / 15 phút, không LLM | Khoản phí trong lượt đỗ |

### M10 — Tranh chấp

| Tính năng | Mức | Tuần | DB | BE | Worker nền | Worker Agent | FE |
|-----------|-----|------|----|----|------------|--------------|----|
| Báo tranh chấp kèm ảnh | 2 | 3 | `dispute_case`, `dispute_evidence` (ảnh gốc + ảnh đã che biển số + SHA-256) | `POST /disputes` (multipart; demo dùng ảnh che sẵn) | — | W5: mở hồ sơ theo khu của ô, mã giả biển số, gom bằng chứng | Form báo tranh chấp |
| Xem hồ sơ tranh chấp | 2 | 3 | — | `GET /disputes/{id}` | — | — | Màn chi tiết (biển số ẩn) |
| BQL xem danh sách tranh chấp | 2 | 3 | — | `GET /zones/{id}/disputes` | — | — | Danh sách |
| BQL quyết định tranh chấp | 2 | 3 | `resolution_code`; `fee_waived` → hủy khoản `overstay_fee` | `POST /disputes/{id}/decision` (đóng luôn yêu cầu duyệt `dispute_decision`) | — | W5: `[LLM]` đọc ảnh, tóm tắt "Gợi ý" → `[HITL]` | Màn quyết định |

## 3. Việc chung

| Việc | Mức | Tuần | Người làm |
|------|-----|------|-----------|
| Migration 25 bảng + RLS theo khu / hộ (ADR-0005) | 1 | 1 | DB |
| docker compose (api, worker, postgres, redis), CI `make check` | 1 | 1 | Hạ tầng |
| Khung SPA, client sinh từ OpenAPI | 1 | 1 | Client |
| Khóa mã hóa biển số: AES-256-GCM (`plate_ciphertext`) + HMAC (`plate_hash`); khóa local khi dev, KMS trên AWS | 1 | 1 | Server core / Hạ tầng |
| Deploy EC2 + RDS, OTel → LGTM | 1 | 2 | Hạ tầng |
| Eval 15 → 30 → **≥45 case** + LLM-judge (W1 12 · W2 10 · W3 5 · W7 8 · an toàn 10) | 1 | 1–4 | AI Agent |
| Lưu ảnh tranh chấp: thư mục local khi dev, S3 khi deploy; ảnh gốc không trả về client | 2 | 3 | Hạ tầng |
| Alert cơ bản, dashboard Grafana | 2 | 3–4 | Hạ tầng |
| Test tích hợp Postgres thật, kịch bản demo, slide | 2 | 4 | Cả nhóm |

## 4. Worker nền (N1–N9)

Job chạy ngầm trên queue `bg` (arq), **không gọi LLM**, không có người chờ kết quả. Job chỉ xử lý dữ liệu và phát sự kiện
qua port `publish()`; việc ra quyết định thuộc use case hoặc workflow Agent. Code ở `<module>/delivery/jobs/`, đăng ký
trong `main_worker.py` ([ADR-0004](../07-adr/ADR-0004-fastapi-langgraph-arq-on-ec2-docker-compose.md), [ADR-0010](../07-adr/ADR-0010-backend-modules-agent-workflows-jobs.md)).

| Mã | Tên | Chạy khi nào | Làm gì | Module | Mức |
|----|-----|--------------|--------|--------|-----|
| **N1** | Xử lý log LPR | Khi nạp CSV log cổng (`POST /dev/lpr-events/import`) | Chuẩn hóa, mã hóa biển số, gắn khu, bỏ log trùng; OCR dưới `zone_policy.ocr_review_threshold` → `pending_review` (màn duyệt để mức 3); khớp booking đang hiệu lực → ghi giờ vào / ra (giờ ra dùng cho phí quá giờ W4) | `access` (M8) | 1 |
| **N2** | Kiểm tra quá giờ | Cron 5 phút | Quét booking đang đỗ, gửi 2 lần nhắc (trước giờ kết thúc 20 phút, đúng lúc hết giờ); khóa idempotency `overstay_pre` / `overstay_due` để không nhắc trùng | `access` (M9) | 2 |
| N3 | Đối soát cuối ngày | Hằng đêm | Đối chiếu booking, log LPR, thanh toán; lập báo cáo đối soát | `reporting` (M12) | 3 |
| N4 | Dự báo giờ trống | Định kỳ | Dự báo ô trống theo khu và giờ, gợi ý chủ chỗ khung giờ nên chia sẻ | `sharing` (M4) | 3 |
| N5 | Phát hiện tranh chấp lặp | Định kỳ | Tìm ô / cặp người dùng hay tranh chấp → phát sự kiện để W6 đề xuất hoán đổi | `dispute` (M10) | 3 |
| N6 | Quét tư cách sắp hết hạn | Hằng ngày | Báo trước khi tư cách L1–L4 hết hạn (demo không cần: hạn được kiểm lúc dùng) | `eligibility` (M1) | 3 |
| N7 | KPI chuỗi | Hằng đêm | Tổng hợp KPI toàn chuỗi khu, làm mới bảng / view KPI | `reporting` (M12) | 3 |
| N8 | Cân bằng cung cầu liên khu | Định kỳ | Phát hiện khu thiếu / thừa ô để gợi ý điều phối giữa các khu | `reporting` (M12) | 3 |
| **N9** | Dọn bản ghi hết hạn | Cron 1 phút | Chuyển sang `expired`: booking `held` quá `hold_expires_at` (nếu không, ràng buộc chống trùng `booking_no_overlap` khóa ô mãi), thỏa thuận quá `confirm_deadline`, yêu cầu duyệt quá `due_at`, lịch chia sẻ đã qua; ca về sớm quá `deadline_at` → phát sự kiện để W3 chuyển `[HITL]` | `booking` (M5) | 1 |

Trong 4 tuần làm **N1**, **N9** (mức 1) và **N2** (mức 2). N9 thêm sau ADR-0010 (plan 013).

## 5. Worker Agent (W0–W7)

Workflow LangGraph trong `server/src/app/agent/` (queue `agent` khi chạy nền). Mỗi bước có nhãn: `[TĐ]` tất định (rule
engine, use case), `[LLM]` LLM chỉ **gợi ý**, `[HITL]` dừng chờ BQL của khu có ô duyệt rồi chạy tiếp bằng `resume_workflow`,
`[RAG]` truy xuất nội quy có trích dẫn. Rule engine luôn là bên quyết định (BR-14).

| Mã | Tên | Kích hoạt từ | Làm gì | Module gọi | HITL | Mức |
|----|-----|--------------|--------|------------|------|-----|
| **W0** | Điều phối chat (supervisor) | Mỗi tin nhắn `POST /chat/stream` | Guardrail → mã giả PII → phân loại ý định → chuyển sang W1–W7 → khôi phục → stream trả lời; ghi `ai_decision_log` | M14 | — | 1 |
| **W1** | Xin chỗ đỗ | W0 (ý định "xin chỗ") | Tính cấp tư cách L1–L4 → rule engine kiểm quyền thuê, phạm vi mở → ghép ô, giữ chỗ tạm; không đủ quyền / hết ô → TH3 hoặc bãi công cộng (mức 2: khoản `th3_visit`); mức 2: `[LLM]` gợi ý ô khu khác (FR-27) | M1, M2, M3, M5 | — | 1 |
| **W2** | Chia sẻ chỗ & thỏa thuận | Chủ đăng lịch (`POST /share-windows`) hoặc W1 ghép được | Ghép người thuê theo phạm vi mở → sinh thỏa thuận theo mẫu khu → chờ hai bên xác nhận OTP → `[HITL]` nếu vượt ngưỡng duyệt → mức 2: thanh toán VietQR mock, nhánh từ chối / hết hạn | M4, M6, M7 | Có (vượt ngưỡng) | 1 |
| **W3** | Chủ về sớm | Nút "Tôi về sớm" (`POST /bookings/{id}/early-return`) | Tìm ô TH3 trống cùng khu kèm giá → người thuê chấp nhận thì đổi booking; từ chối / hết ô / quá hạn → `[HITL]`; tạo khoản TH3, hoàn tiền | M9, M4, M5 | Có | 2 |
| **W4** | Phí quá giờ | Xe ra (N1 ghi giờ ra) sau khi N2 đã nhắc | Miễn 10 phút, sau đó 12 500 đ / 15 phút; tạo `payment` loại `overstay_fee`; **không dùng LLM** | M9, M7, M13 | — | 2 |
| **W5** | Tranh chấp | Cư dân báo (`POST /disputes`) | Mở hồ sơ theo khu của ô, mã giả biển số, gom bằng chứng → `[LLM]` đọc ảnh đã che biển số, tóm tắt "Gợi ý" → `[HITL]` BQL quyết định (`fee_waived` hủy phí quá giờ) | M10, M8, M6 | Có | 2 |
| W6 | Hoán đổi chỗ | Người dùng hoặc N5 | Đề xuất hoán đổi cùng khu (2 bên hoặc theo vòng) → BQL duyệt | M11, M2 | Có | 3 |
| **W7** | Hỏi đáp nội quy | W0 (ý định "hỏi nội quy") | `[RAG]` tìm nội quy theo khu / tòa, trả lời có trích dẫn; không hứa giá hay quyền thuê thay rule engine | M3, M14 | — | 2 |

Mức 1 làm W0–W2; mức 2 thêm W3, W4, W5, W7; W6 để mức 3. `resume_workflow` (sau khi BQL bấm duyệt / từ chối) là cơ chế chạy tiếp
W2, W3, W5, không phải workflow riêng.

## 6. Mức 3 — nếu còn thời gian

Đã có thiết kế; bảng hoãn ở [08-deferred-tables](../03-design/08-deferred-tables.md).

| Module | Tính năng |
|--------|-----------|
| M1 | Quên mật khẩu, rút đồng ý, BQL thu hồi tư cách, refresh token, ủy quyền, eKYC |
| M2 | Xem danh sách khu / ô, sơ đồ bãi realtime, ô sạc điện |
| M3 | BQL sửa nội quy qua UI, lịch sử cấu hình, giá cao điểm, mở TH1 ra cả khu |
| M4 | Sửa lịch, thu hẹp phạm vi, lịch lặp, dự báo giờ trống (N4), thu nhập |
| M5 | Hủy yêu cầu, lịch sử yêu cầu, form đặt ngoài chat, đặt định kỳ |
| M6 | Lịch sử thỏa thuận, xuất dữ liệu, chữ ký số, chuỗi hash |
| M7 | Hoàn tiền thủ công, voucher shophouse, thanh toán thật |
| M8 | Webhook / MQTT, so khớp mờ, hàng chờ OCR thấp, LPR kích hoạt W3–W5 |
| M9 | Phát hiện về sớm từ LPR, bù chi phí, nhắc quá giờ thêm lần |
| M10 | Xem biển số gốc có ghi log, làm mờ ảnh tự động |
| M11 | Hoán đổi chỗ (W6, N5) |
| M12, M13 | Đối soát (N3), KPI chuỗi (N7, N8), Agent hỗ trợ BQL, WebSocket, push / Zalo / SMS |
| M14 | Bộ nhớ dài hạn, giọng nói, đa ngôn ngữ |
