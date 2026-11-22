# ADR-0015: Người thuê: ETA từ GPS mỗi 15 phút, OTP nhận chỗ, duyệt hai lớp (BQL chỉ xem ca xấu)

- **Status**: Accepted
- **Date**: 2026-11-22
- **Liên quan**: [Pilot một tòa](../01-product/07-pilot-mot-toa.md) · [PRD BR-20 đến BR-29](../01-product/02-prd.md#5-quy-tắc-nghiệp-vụ) · chủ về sớm: [ADR-0014](ADR-0014-eta-location-and-renter-priority-on-early-return.md) · [ADR-0010](ADR-0010-backend-modules-agent-workflows-jobs.md) · plan 024

## Context

- Xếp hàng chỉ theo `queued_at` khiến người ở xa được gán trước rồi không tới, chỗ bị giữ trống.
- Giữ chỗ cố định 10 phút không hợp đường xa hay kẹt xe; người thuê phải biết có chỗ hay không trước khi bị trừ tiền.
- BQL không thể duyệt từng lượt; chỉ nên xem các ca đáng ngờ.
- Vị trí là dữ liệu cá nhân (NĐ 13/2023) và GPS có thể bị giả, nên không được dùng để xác nhận chỗ hay tính tiền.

## Decision

- **GPS và ETA người thuê:** khi đang có yêu cầu trong hàng chờ, app lấy GPS mỗi 15 phút, có đồng ý riêng (`consent_record`). ETA qua port `TravelTimeProvider` (mock ở dev, CI, demo; adapter thật sau cờ). Chỉ lưu ETA, thời điểm, nguồn; không lưu tọa độ thô, không gửi tọa độ cho LLM. Ngừng sau khi chốt gán (TH3: tới khi xe vào).
- **Đủ điều kiện gán:** lần GPS gần nhất cho ETA ≤ 30 phút (có kẹt xe), hoặc bấm "Tôi đang đến", hoặc đang thừa chỗ và không ai gần hơn đang chờ. Trong nhóm này xếp theo `queued_at`. ETA > 30 phút: chưa gán, chưa trừ tiền, vẫn thấy số chỗ còn lại.
- **GPS lỗi hoặc tắt** coi như còn xa; hai lần liên tiếp không có GPS thì nhắc, không loại khỏi hàng.
- **OTP nhận chỗ (3 phút):** được gán thì nhập OTP; có OTP mới trừ tiền và giữ chỗ. Không nhập: chỗ chuyển người kế tiếp, không mất tiền.
- **Giữ chỗ:** ETA + 10 phút, tối đa 40 (TH3: 60). Quá hạn mà camera chưa thấy xe vào: nhả chỗ, phí không tới 30% (tối thiểu 1 giờ), hoàn 70%.
- **OTP với hệ thống, không giữa hai bên:** chủ nhập lúc đăng cho thuê; người thuê nhập lúc được gán.
- **Duyệt hai lớp:** rule engine cho đạt, vi phạm rõ (tự từ chối kèm lý do) hoặc vùng xám (thiếu dữ liệu, sát ngưỡng → BQL). AI đánh giá rủi ro ca đã đạt: bình thường tự duyệt, đáng ngờ → BQL kèm lý do. AI chỉ siết, không nới. Ca chờ BQL quá 10 phút coi như từ chối.
- **Đăng ký tự đối chiếu:** chủ và người thuê khớp với dữ liệu BQL đã nạp một lần lúc triển khai (cư dân, ô và kích thước, biển số); không khớp thì BQL.
- **Ưu tiên TH3:** khi TH1, TH2 hết chỗ, người thuê liên quan khu đô thị được ưu tiên hơn khách vãng lai, kể cả khi còn xa. Bãi khách còn ≤ 2 chỗ: báo BQL và bảo vệ.
- **Báo số chỗ còn lại:** mỗi lần chỗ được gán hoặc mất, báo người đang chờ số chỗ và thứ tự của họ; không còn cơ hội thì gợi ý bãi khác.

## Consequences

- **Tích cực:** người ở xa không giữ chỗ vô ích; chỗ luân chuyển nhanh hơn; BQL chỉ xem ca xấu; có dấu vết cho tranh chấp.
- **Tiêu cực:** thêm job và trạng thái; phụ thuộc GPS và đồng ý riêng; ETA mock chưa chứng minh độ chính xác; BQL có thêm việc ở ca chờ.
- **Tiền và xác nhận:** do code và job quyết định; LLM chỉ gợi ý (BR-14).

## Observability Impact

- Span: `queue.evaluate_eligibility`, `booking.renter_otp_confirm`, `approval.rule_check`, `approval.ai_risk_review`, `approval.bql_escalation`. Thuộc tính `queue.tier`, `eta.source`, `approval.outcome`; không ghi tọa độ, biển số hay ID người dùng.
- Metric, nhãn cố định: `parking_queue_wait_seconds{tier}` (histogram), `renter_eta_updates_total{source}` (gps|manual|none), `renter_otp_timeouts_total{tier}`, `approval_decisions_total{layer,outcome}` (layer: rule|ai|bql), `bql_review_duration_seconds` (histogram).

## Alternatives considered

- Xếp hàng chỉ theo `queued_at` và ETA chủ: người ở xa thắng chỗ rồi bỏ.
- GPS liên tục: tốn pin, vượt mức cần.
- BQL duyệt từng lượt: không khả thi khi số lượt tăng.

## Cần xác nhận

- Các ngưỡng (30 phút, 10 phút, 3 phút, 30%) rà soát sau 2 tuần pilot.
- BQL đồng ý quy tắc "quá 10 phút coi như từ chối"; pháp lý khi bật adapter bản đồ thật.
