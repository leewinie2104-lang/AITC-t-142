# 07 — Pilot một tòa: use case ưu tiên

> **File này trả lời:** bản thử nghiệm chạy thế nào trong một tòa, quy tắc nào quyết định, AI làm gì, và làm theo thứ tự nào.
> Quy tắc gốc: [PRD §5](02-prd.md#5-quy-tắc-nghiệp-vụ) (BR-07, BR-14, BR-20…BR-29) · FR: [PRD §6](02-prd.md#6-yêu-cầu-chức-năng) (FR-28…FR-38) · Việc cần làm: [Backlog §0](05-backlog.md#0-ưu-tiên-use-case-pilot) · [ADR-0014](../07-adr/ADR-0014-eta-location-and-renter-priority-on-early-return.md) · [ADR-0015](../07-adr/ADR-0015-renter-gps-eta-otp-and-two-layer-approval.md)

**Bản thử nghiệm chỉ chạy trong một tòa.** Cư dân trong tòa thuê lại chỗ của nhau; chỉ ô chủ đã đồng ý chia sẻ mới được cho thuê.
Thiết kế chuỗi nhiều khu (L2, L3, TH2 liên khu) vẫn giữ trong PRD nhưng không phải trọng tâm demo.

## 1. Bối cảnh và đăng ký

- **Vấn đề:** chị A rảnh đến 16h nhưng ô chỉ thật sự trống khi xe chị đã ra; anh B cần chỗ từ 15h nhưng không cần đúng ô của chị A.
- **Phản hồi mentor:** "xe ra cổng chưa chắc ô đã trống" → vẫn đúng, nên có thêm bước chủ tự đăng: ô là của chị A, chị A đăng và xe chị ra thì ô gần như chắc chắn trống (BR-20). Agent chỉ đề xuất ghép; quy tắc cố định vẫn chốt cuối (BR-14).
- **Đăng ký tự đối chiếu (FR-38):** chủ và người thuê đăng ký; hệ thống đối chiếu với dữ liệu BQL có sẵn (danh sách cư dân, chủ shophouse, ô và kích thước của từng hộ, biển số) nạp một lần lúc triển khai. Khớp → tự kích hoạt; không khớp → BQL duyệt (BR-26).

## 2. Luồng chính (10 bước)

| # | Bước | Ai | Quy tắc |
|---|------|----|---------|
| 1 | Chị A bấm "Chỗ của tôi rảnh đến 16h" và nhập OTP cho thuê với hệ thống | Chủ chỗ | FR-05, FR-06, BR-25 |
| 2 | Chỗ **trống** khi chị A đã đăng, đã nhập OTP **và** camera cổng thấy xe chị ra. Đăng quá 30 phút mà xe chưa ra → tin hết hạn, app báo chị đăng lại | Hệ thống (N1) | BR-20 |
| 3 | Anh B khai giờ ra (15h) và xe, vào **hàng chờ** của tòa; chờ chỗ phù hợp đầu tiên, không chờ riêng chỗ chị A | Người thuê | BR-21 |
| 4 | Khi đang chờ, app lấy GPS mỗi 15 phút → ETA có kẹt xe. Đủ điều kiện gán khi ETA ≤ 30 phút (hoặc anh bấm "Tôi đang đến") | Hệ thống | BR-27, BR-21 |
| 5 | Agent đối chiếu khung giờ, kích thước xe – ô, lịch sử hai bên (hay về sớm, hay quá giờ), đề xuất ghép; rule engine kiểm lại rồi mới chốt | W2 | BR-11, BR-14 |
| 6 | Chị A chưa đi, nhưng anh C (tầng khác) đã đăng và xe đã ra → ghép ngay chỗ anh C cho anh B (chỗ trống trước ghép trước) | W2 | BR-21 |
| 7 | Anh B được gán → nhập **OTP nhận chỗ trong 3 phút** (đồng ý nhận chỗ, bị trừ tiền). Không nhập → chỗ chuyển người kế tiếp, anh về hàng chờ, không mất tiền | N9 → W2 | BR-22, BR-25 |
| 8 | Giữ chỗ tới **ETA + 10 phút** (tối đa 40). Hủy → hoàn theo thỏa thuận, chỉ ghi nhận khoản, không thu qua app. Hết giữ mà camera chưa thấy xe vào → nhả chỗ, phí không tới 30% (tối thiểu 1 giờ), hoàn 70% | M6, M5 | BR-22, BR-23 |
| 9 | Gần giờ ra thì nhắc anh B; quá giờ mà xe chưa ra thì báo bảo vệ, phí tính khi xe ra | N2, W4 | BR-08, FR-11, FR-32 |
| 10 | Anh C về sớm: xem §3 | W3 | BR-07, BR-24 |

## 3. Chủ về sớm, bãi khách (TH3) và báo chỗ

- **Chủ về sớm:** anh C bấm "Tôi về sớm". App lấy vị trí **một lần** (có đồng ý); không cho phép thì anh chọn 15 / 30 / 60 phút. Hệ thống ước tính giờ về có kẹt xe qua port ETA (demo dùng mock); không lưu tọa độ (ADR-0014).
- Báo anh B "Chủ chỗ về khoảng 15:10", kèm ô khác còn trống (nếu có) và hạn trả lời (trước giờ về 5 phút). Anh B **dời** → đổi lượt sang ô mới, anh C về đúng ô của mình. Anh B **ở lại** hoặc không trả lời → anh B giữ ô tới hết giờ đã đặt (ưu tiên người thuê, BR-07); anh C đỗ **ô dự phòng / bãi khách** trong tòa, không mất phí.
- Hết ô dự phòng → BQL xử lý, tòa **tạm ngừng nhận lượt thuê mới** tới khi có lại ô dự phòng (BR-24).
- **Ưu tiên TH3 (BR-28):** TH1, TH2 hết chỗ → người thuê liên quan khu đô thị (cư dân tòa khác trong khu, chủ shophouse…) đã đặt và OTP được ưu tiên hơn khách vãng lai, kể cả khi còn xa; gán ngay lúc đặt; giữ ETA + 10, tối đa 60 phút. Bãi khách còn **≤ 2 chỗ** hoặc ≤ số người ưu tiên đang tới → báo BQL và bảo vệ "không nhận khách vãng lai". Không tới → nhả, tính phí không tới, báo bảo vệ mở lại. Khách vãng lai không dùng app: hệ thống chỉ báo, bảo vệ chặn.
- **Báo số chỗ còn lại (BR-29):** mỗi khi chỗ bị gán hoặc mất đi, báo người đang chờ "Còn N chỗ phù hợp xe bạn, bạn đứng thứ k"; khi không còn cơ hội → gợi ý bãi khác.

## 4. Duyệt 2 lớp và vai trò Agent

- **Lớp 1 — rule engine:** đạt / vi phạm rõ ràng (tự từ chối, báo lý do) / **vùng xám** (thiếu dữ liệu, sát ngưỡng → BQL).
- **Lớp 2 — AI đánh giá rủi ro** ca đã đạt (lịch sử quá giờ, về sớm, tranh chấp, giá bất thường): bình thường → **tự duyệt**; đáng ngờ → BQL kèm lý do và dẫn chứng. AI chỉ siết, không nới: không cho qua ca rule đã chặn.
- Ca chờ BQL quá **10 phút** → coi như từ chối, không tự duyệt; người thuê được báo và gợi ý bãi khác.
- **Mục tiêu Agent:** đưa người chờ vào chỗ nhanh nhất mà không vi phạm quy tắc. Chỉ đề xuất và đánh giá rủi ro, **không chốt**. Công cụ: tra hàng chờ, tra lịch chia sẻ, đọc sự kiện cổng, tính ETA, kiểm tra quy tắc, đánh giá rủi ro, đề xuất gán, gửi OTP nhận chỗ, thông báo, báo bảo vệ, chuyển ca BQL. Lịch sử chỉ dùng khi nhiều chỗ trống cùng lúc hoặc để đẩy ca lên BQL, không để bắt người thuê chờ thêm.

| Việc | Agent làm | Quy tắc cố định còn quyết định |
|------|-----------|-------------------------------|
| Ghép chỗ (FR-30) | Xếp hạng ứng viên theo giờ, kích thước, lịch sử, kèm lý do | Quyền thuê, kích thước, giờ, ETA ≤ 30, thứ tự hàng chờ |
| Duyệt 2 lớp (FR-33) | Đánh giá rủi ro ca đã đạt: tự duyệt / đáng ngờ kèm lý do | Rule đã chặn thì chặn; BQL quyết ca xấu |
| Tranh chấp (FR-34) | Dựng dòng thời gian từ thỏa thuận, log cổng, ảnh; mỗi câu ghi nguồn | BQL quyết định |

| Vai trò | Việc |
|---------|------|
| Chủ chỗ | Đăng giờ rảnh, nhập OTP cho thuê, báo về sớm |
| Người thuê | Vào hàng chờ, nhập OTP nhận chỗ, chọn dời / ở lại khi chủ về sớm, ra đúng giờ |
| Bảo vệ | Nhận báo quá giờ; chỉ chủ về sớm vào ô dự phòng; chặn khách vãng lai khi bãi khách hết chỗ |
| BQL tòa | Duyệt ca xấu, xử lý khi hết ô dự phòng, quyết định tranh chấp |
| Rule engine | Chốt ghép, giữ chỗ, trừ tiền, hoàn, phí, tạm ngừng nhận lượt |

## 5. Thông số, đo hiệu quả, nguyên tắc

- **Thông số** (config, xem lại sau 2 tuần pilot): GPS 15 phút · ngưỡng chốt ETA ≤ 30 phút · giữ ETA + 10, tối đa 40 (TH3: 60) · OTP nhận chỗ 3 phút · phí không tới 30% (tối thiểu 1 giờ), hoàn 70% · tin đăng hết hạn 30 phút · ca chờ BQL 10 phút · báo bãi khách khi ≤ 2 chỗ.
- **Đo hiệu quả:** thời gian chờ có chỗ · tỷ lệ ghép thành công lần đầu · tỷ lệ không nhập OTP / không tới · độ lệch ETA (lúc chốt vs giờ camera thấy xe vào) · tỷ lệ được báo hết chỗ trước khi tới · tỷ lệ tự xử lý (tự duyệt + tự từ chối) ≥ 95% · tỷ lệ ca chuyển BQL mà BQL đồng ý là xấu · tỷ lệ chỗ TH3 giữ mà không tới · thời gian BQL xử lý ca xấu · thời gian lập hồ sơ tranh chấp.
- **Nguyên tắc:** log cổng và ảnh là **bằng chứng cần xác minh**, không phải kết luận. Tên, biển số thành mã giả trước khi gửi LLM (BR-14). GPS chỉ dùng xếp ưu tiên và chốt thời điểm gán, không dùng xác nhận chỗ trống hay tính tiền; LLM chỉ nhận ETA, không nhận tọa độ (BR-27). Tiền, phí, nhắc giờ, tạm ngừng nhận lượt do code / job.

## 6. Dữ liệu cần thêm (ticket SCRUM-183)

- `share_window`: `owner_otp_confirmed_at`, `owner_exited_at`, `expires_at` (đăng + 30 phút).
- `parking_request`: `queued_at`, `last_eta_minutes`, `last_eta_at`, `eta_source` (gps \| manual \| none), `gps_consent_id`, `is_urban_related` (ưu tiên TH3), `queue_status` (queued … escalated).
- `booking` / hold: `assigned_at`, `renter_otp_confirmed_at`, `hold_expires_at`, `no_show_fee_vnd`.
- `approval_request`: `rule_result`, `ai_risk`, `reasons`, `escalated_at`, `bql_deadline_at`, `bql_decision`; `bql_registry_import`; `recovery_case` (`new_return_at`, `renter_decision`); chỗ TH3 còn lại tính bằng `app.th3_free_slots()` + `zone_policy.th3_guest_alert_slots` (không bảng đếm); cờ tạm ngừng theo tòa; `payment` thành sổ khoản phí (không có trạng thái QR).
- Thiết kế chi tiết: [schema.sql](../03-design/sql/schema.sql) · từ điển bảng: [tables.html](../03-design/diagrams/tables.html).

## 7. Kịch bản demo (ticket SCRUM-191)

Chị A đăng, chưa ra · anh B vào hàng chờ, thấy "Còn N chỗ" · anh C đăng và ra → anh B được ghép, nhập OTP nhận chỗ trong 3 phút · anh B gần hết giờ được nhắc · anh C bấm về sớm (kẹt xe, ETA 25 phút) → anh B chọn ở lại → anh C đỗ ô dự phòng · lần hai hết ô dự phòng → BQL nhận ca, tòa tạm ngừng nhận lượt · anh B quá giờ → bảo vệ được báo, phí tính khi xe ra.
