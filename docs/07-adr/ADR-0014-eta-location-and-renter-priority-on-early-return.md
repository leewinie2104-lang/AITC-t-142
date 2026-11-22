# ADR-0014: Chủ về sớm: ETA từ vị trí qua port riêng (mock khi demo), người thuê được ưu tiên

- **Status**: Accepted
- **Date**: 2026-11-22
- **Liên quan**: [Pilot một tòa](../01-product/07-pilot-mot-toa.md) · [PRD BR-07, BR-24](../01-product/02-prd.md#5-quy-tắc-nghiệp-vụ) · [ADR-0010](ADR-0010-backend-modules-agent-workflows-jobs.md) · plan 022 · SCRUM-116, SCRUM-129, SCRUM-194, SCRUM-196

## Context

- BR-07 cũ: chủ về sớm luôn lấy lại ô, người thuê bị chuyển sang TH3. Người thuê bị báo đột ngột dù đã trả cho khung giờ đó.
- Mentor chỉ ra: ca về sớm chưa có cách vận hành khi hết chỗ thay thế hoặc người thuê không chịu dời.
- Biết trước chủ về lúc nào thì người thuê có thời gian chọn, bảo vệ chuẩn bị ô dự phòng. Vị trí là dữ liệu cá nhân (NĐ 13/2023).

## Decision

- **Ưu tiên người thuê:** người thuê được ở lại tới hết giờ đã đặt; dời sang ô khác là tự nguyện. Chủ được bảo đảm **một chỗ đỗ**
  (ô dự phòng / bãi khách trong tòa, miễn phí), không bảo đảm đúng ô của mình. Hết ô dự phòng → BQL xử lý (HITL) và tòa tạm ngừng
  nhận lượt thuê mới (BR-24).
- **ETA:** port `TravelTimeProvider` ở domain của module `booking`; adapter `mock` (kịch bản kẹt xe cố định) cho dev, CI và demo;
  adapter thật (Google Routes API hoặc nhà cung cấp trong nước như Goong, Vietmap) sau cờ cấu hình, chưa bật.
- **Vị trí:** chỉ lấy **một lần** khi chủ bấm "Tôi về sớm", có đồng ý riêng (`consent_record`). Không lưu tọa độ; chỉ lưu
  `owner_eta_at` và nguồn (`location` / `manual`). Không cho phép vị trí thì chủ tự chọn 15 / 30 / 60 phút.
- ETA là dữ liệu tất định đưa vào rule engine, **không đi qua LLM**. Gửi cho nhà cung cấp bản đồ chỉ tọa độ, không tên, biển số.
- Chưa dùng ETA của người thuê để xếp hàng chờ (thứ tự theo `queued_at`), tránh người ở gần luôn thắng.

## Consequences

- **Tích cực:** người thuê không bị đẩy đi đột ngột; ca về sớm luôn có lối ra (dời, ô dự phòng, BQL); demo không phụ thuộc API trả phí.
- **Tiêu cực:** chủ chỗ có thể ngại chia sẻ hơn vì không chắc về đúng ô (bù bằng ô dự phòng miễn phí, cần đo khi pilot);
  phải giữ ô dự phòng trống; ETA mock không chứng minh độ chính xác thật; gửi tọa độ ra nhà cung cấp nước ngoài cần pháp lý.

## Alternatives considered

- Giữ BR-07 cũ (chủ luôn lấy lại ô): người thuê chịu thiệt dù không có lỗi.
- Theo dõi vị trí liên tục: chính xác hơn nhưng tốn pin, xâm phạm riêng tư hơn mức cần.
- Gọi API bản đồ thật ngay: tốn phí theo lượt gọi, thêm khóa API cho mỗi môi trường.

## Observability Impact

- Span `booking.estimate_eta` với thuộc tính `eta.source`, `eta.provider`; **không** ghi tọa độ.
- Metric (nhãn cố định): `early_return_cases_total{outcome="moved|stayed|escalated"}`, `eta_provider_errors_total{provider}`.

## Cần xác nhận

- BQL pilot đồng ý ưu tiên người thuê và số ô dự phòng tối thiểu; pháp lý khi bật adapter bản đồ thật.
