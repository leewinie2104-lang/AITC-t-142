# Traceability — User Story → Use case

> **File này trả lời:** một US nối tới FR/BR, workflow, use case và màn hình nào; use case nào cần code trong 4 tuần.
> Nguồn: [User Stories & AC](04-user-stories.md) · [PRD](02-prd.md) · [Backlog](05-backlog.md) · [ADR-0010](../07-adr/ADR-0010-backend-modules-agent-workflows-jobs.md) · [Cấu trúc server](../04-development/01-server-structure.md)

<blockquote style="border-left: 4px solid #22c55e; background: #f0fdf4; padding: 0.75em 1em; margin-left: 0; border-radius: 4px;">
  <strong style="color: #000;">CHƯA RÃNH ĐỂ ĐỌC, CHƯA ĐÁNH GIÁ ĐƯỢC</strong>
</blockquote>

**Cách dùng:** chọn US ở §1, lấy use case, tra §2. Module (M) dùng skill `new-usecase`; workflow (W) dùng `new-agent-workflow`;
job (N) dùng `new-background-job`. Tên use case là **đề xuất** theo ADR-0010, chưa có file. Cột *Mức* = [Backlog §1](05-backlog.md#1-cách-đọc).

## 1. User story → use case

| US · AC | FR / BR | Workflow / Job | Use case chính | Màn hình | Mức |
|---|---|---|---|---|---|
| US-19 · AC-19 | FR-01, FR-23, FR-24 · BR-15 | W1 bước 2 | `eligibility.resolve_level`, `policy.check_rental_right` | [request-parking](ux/wireframes/request-parking.html) | 1 |
| US-20 · AC-20 | FR-07, FR-24, FR-26 · BR-02 | W1 bước 2–5 | `booking.request_parking`, `eligibility.resolve_level`, `policy.quote_price` | [request-parking](ux/wireframes/request-parking.html) | 1 |
| US-21 · AC-21 | FR-23, FR-24 · BR-15 | W1 bước 2 | `eligibility.resolve_level` | — | 1 |
| US-22 · AC-22 | FR-25 · BR-16 | W1 (kiểm tra hạn) | `policy.check_rental_right` | — | 1 (chặn) |
| US-24 · AC-24 | BR-17 | W1 bước 2 | `eligibility.attest_cross_zone` | — | 2 |
| US-25 · AC-25 | FR-27 | W1 (Ưu tiên 2) | `booking.suggest_other_zone` | [request-parking](ux/wireframes/request-parking.html) | 2 |
| US-01 · AC-01 | FR-01, FR-02 · BR-01, BR-15 | W0 → W1 | `agent.chat_turn`, `booking.request_parking`, `sharing.match_share_slot` | [request-parking](ux/wireframes/request-parking.html) (chat: chưa có wireframe) | 1 |
| US-02 · AC-02 | FR-03 · BR-19 | W1 bước 7 | `booking.assign_th3_slot`, `policy.quote_price` | [request-parking](ux/wireframes/request-parking.html) | 1 |
| US-03 · AC-03 | FR-04 · BR-01, BR-03–05, BR-16 | W1 bước 3–4 | `policy.check_rental_right` | [request-parking](ux/wireframes/request-parking.html) | 1 |
| US-16 · AC-06 | FR-07 · BR-11 | W1 bước 5 | `facility.check_slot_fits` | [request-parking](ux/wireframes/request-parking.html) | 1 |
| US-05 · AC-05 | FR-06 · BR-07 | W2 bước 3 | `sharing.create_share_slot` | [owner-share-schedule](ux/wireframes/owner-share-schedule.html) | 1 |
| US-06 · AC-06 | FR-07 · BR-11 | W2 bước 4 | `sharing.match_share_slot` | [request-parking](ux/wireframes/request-parking.html) | 1 |
| US-07 · AC-07 | FR-08 · BR-04 | W2 bước 5–6 | `ledger.generate_agreement`, `ledger.confirm_agreement` | [agreement](ux/wireframes/agreement.html) | 1 |
| US-08 · AC-08 | FR-09 | W2 bước 8 | `ledger.record_confirmation` | [admin-ledger](ux/wireframes/admin-ledger.html) | 1 · 2 (xem) |
| — · AC-15 | FR-09a · BR-12 | W2 bước 7 (HITL) | `approval.enqueue_pending`, `approval.decide_pending`, `agent.resume_workflow` | [admin-approvals](ux/wireframes/admin-approvals.html) | 1 |
| — · AC-16 | FR-21 | W2 bước 9 | `payment.create_vietqr_mock` | [payment](ux/wireframes/payment.html) | 2 |
| US-09, US-10 · AC-09 | FR-10 · BR-07 | W3 | `agent.start_workflow`, `booking.get_active_booking`, `booking.relocate_to_th3` | [owner-early-return](ux/wireframes/owner-early-return.html) | 2 |
| US-11 · AC-10 | FR-11, FR-12 · BR-08 | N2, N1 | `access.detect_overstay`, `payment.charge_overstay_fee` | [renter-booking](ux/wireframes/renter-booking.html) (`?state=overstay`), [notifications](ux/wireframes/notifications.html) | 2 |
| US-12 · AC-11 | FR-13, FR-14, FR-16 · BR-14, BR-18 | W5 | `dispute.open_case`, `dispute.collect_evidence`, `dispute.decide_case` | [dispute-report](ux/wireframes/dispute-report.html), [admin-disputes](ux/wireframes/admin-disputes.html), [admin-dispute-detail](ux/wireframes/admin-dispute-detail.html) | 2 |
| US-13 · AC-12 | FR-15 · BR-09, BR-14 | W5 | `dispute.open_case` (ẩn biển số) | [admin-dispute-detail](ux/wireframes/admin-dispute-detail.html) | 2 |
| US-17 · AC-17, AC-10a | FR-16a, FR-19 · BR-13 | N1 | `access.ingest_lpr_log` | — | 1 |

US Ưu tiên 3 (US-04, US-14, US-15, US-18, US-23) không có use case cần code; thiết kế cũ xem git history của file này.

## 2. Use case cần code

| Use case | Mô tả | Quy tắc | Mức |
|---|---|---|---|
| `identity.login`, `identity.register` | Đăng nhập (access JWT 8 giờ); đăng ký kèm `consent_record` | ADR-0006, ADR-0011, A-03 | 1 · 2 (đăng ký) |
| `eligibility.resolve_level` | Cấp L1–L4 tại tòa / khu của ô, kèm hạn | FR-24, BR-15, A-10 | 1 |
| `eligibility.attest_cross_zone` | Trả khu khác chỉ cấp và hạn, không trả hồ sơ | BR-17 | 2 |
| `policy.check_rental_right` | Rule engine: cấp × phạm vi mở; chặn kèm lý do | FR-04, BR-01, BR-03–05, BR-16 | 1 |
| `policy.quote_price` | Giá theo cấp tại ô (`zone_policy.prices`) | BR-19, PRD §8 | 1 |
| `facility.check_slot_fits` | Kích thước ô hợp kích thước xe | BR-11 | 1 |
| `facility.manage_vehicle` | Thêm / sửa / xóa xe, biển số mã hóa | — | 2 |
| `sharing.create_share_slot`, `sharing.cancel_share_slot` | Tạo / hủy lịch + dự phòng; chặn TH3 | FR-06, BR-03, BR-04 | 1 |
| `sharing.match_share_slot` | Ghép theo giờ, kích thước, dự phòng, phạm vi | FR-07 | 1 |
| `booking.request_parking` | Nhận yêu cầu, định tuyến theo cấp, giữ chỗ tạm | FR-01 → FR-03 | 1 |
| `booking.assign_th3_slot` | Ô TH3 cùng khu theo giá cấp | FR-03, BR-06 | 1 |
| `booking.suggest_other_zone` | Gợi ý ô khu khác; không tự đặt | FR-27 | 2 |
| `booking.get_active_booking`, `booking.relocate_to_th3` | Lượt đỗ hiện tại; mở `recovery_case`, chuyển sang TH3 | FR-10, D-09 | 2 |
| `ledger.generate_agreement`, `ledger.confirm_agreement` | Thỏa thuận theo mẫu khu có ô; OTP từng bên (Redis) | FR-08, BR-04 | 1 |
| `ledger.record_confirmation` | Bằng chứng xác nhận chỉ ghi thêm (`consent_record`) | FR-09 | 1 |
| `payment.create_vietqr_mock` | Khoản phí và trạng thái VietQR mô phỏng | FR-21, A-05 | 2 |
| `access.ingest_lpr_log` | N1: chuẩn hóa, gắn khu, chống trùng; OCR dưới ngưỡng → `pending_review`; ghi giờ vào / ra | FR-16a, BR-13 | 1 |
| `booking.expire_stale` | N9: booking `held`, thỏa thuận, yêu cầu duyệt, lịch chia sẻ quá hạn → `expired`; ca về sớm quá hạn → sự kiện W3 | FR-06, BR-12 | 1 |
| `access.detect_overstay` | N2: quét booking đang đỗ, gửi nhắc trước 20 phút và đúng lúc hết giờ (idempotent theo `notification.idempotency_key`); không có bảng ca quá giờ | FR-11, BR-08 | 2 |
| `payment.charge_overstay_fee` | Khi xe ra: tính phí theo `zone_policy` (miễn 10 phút, bước 15 phút, 50 000 đ/giờ), tạo `payment` loại `overstay_fee`; người thuê trả, về chủ chỗ / khu (TH3) | FR-12, BR-08, A-07 | 2 |
| `dispute.open_case`, `dispute.collect_evidence`, `dispute.decide_case` | W5: mở hồ sơ theo khu của ô (ảnh, mô tả ẩn biển số); gom bằng chứng chỉ ghi thêm; BQL quyết định qua HITL (giữ nguyên, bác, miễn phí quá giờ, khác); tóm tắt LLM chỉ là gợi ý | FR-13 → FR-16, BR-09, BR-14, BR-18 | 2 |
| `approval.enqueue_pending`, `approval.decide_pending` | Hàng chờ HITL theo khu có ô; duyệt → resume | BR-12, BR-18 | 1 |
| `notification.notify_user` | Thông báo trong app, cùng transaction | — | 1 |
| `reporting.zone_kpi` | Đọc `kpi_daily_v` theo khu | Scope §6 | 2 |
| `agent.list_ai_decisions` | BQL xem `ai_decision_log` của khu (chỉ hash, kết quả, trace id) | BR-14 | 2 |
| `knowledge.answer_policy_question` | W7: RAG nội quy theo khu / tòa, có trích dẫn | BR-14 | 2 |
| `agent.chat_turn` | W0: guardrail, mã giả, ý định, stream; ghi `ai_decision_log` | BR-14 | 1 |
| `agent.start_workflow`, `agent.resume_workflow` | Điểm vào W1–W3, W7; tiếp tục sau HITL | ADR-0010 | 1 |

**Ưu tiên 3, không code:** `eligibility.verify_credential` (demo dùng seed), `eligibility.expire_credentials` (N6),
`policy.validate_share_scope`, `sharing.forecast_free_windows`, `sharing.suggest_share_windows`, `swap.*`, xem biển số gốc có ghi log.

## 3. Khoảng trống cần xử lý

| Vấn đề | Đề xuất |
|---|---|
| Duyệt vượt ngưỡng (AC-15) và VietQR (AC-16) chưa có US | Viết US cho BQL khu (trước tuần 2) và người thuê (trước tuần 3) |
| Đăng nhập, đăng ký, xe, thông báo, hỏi đáp nội quy (W7), KPI chưa có US | Viết US ngắn hoặc ghi rõ là tính năng nền |
| Màn hình cho US-21, US-22, US-24, US-17 chưa có wireframe | Không cần màn hình riêng: hiển thị qua kết quả định tuyến / log |
