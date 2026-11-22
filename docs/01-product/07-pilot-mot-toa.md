# 07 — Pilot một tòa: use case ưu tiên

> **File này trả lời:** bản thử nghiệm chạy thế nào trong một tòa, quy tắc nào quyết định, AI làm gì, và làm theo thứ tự nào.
> Quy tắc gốc: [PRD §5](02-prd.md#5-quy-tắc-nghiệp-vụ) (BR-07, BR-20…BR-24) · Việc cần làm: [Backlog §0](05-backlog.md#0-ưu-tiên-use-case-pilot) · [ADR-0014](../07-adr/ADR-0014-eta-location-and-renter-priority-on-early-return.md)

**Bản thử nghiệm chỉ chạy trong một tòa.** Cư dân trong tòa thuê lại chỗ của nhau; chỉ ô chủ đã đồng ý chia sẻ mới được cho thuê.
Thiết kế chuỗi nhiều khu (L2, L3, TH2 liên khu) vẫn giữ trong PRD nhưng không phải trọng tâm demo.

## 1. Luồng use case

| # | Bước | Ai | Quy tắc |
|---|------|----|---------|
| 1 | Chị A bấm "Chỗ của tôi rảnh đến 16h" | Chủ chỗ | Lịch chia sẻ có dự phòng (FR-06) |
| 2 | Chỗ chỉ **trống** khi chị A đã đăng **và** camera cổng thấy xe chị A ra. Đăng mà xe chưa ra thì chưa trống | Hệ thống (N1) | BR-20 |
| 3 | Anh B khai giờ ra (15h) và xe, rồi vào **hàng chờ** của tòa; anh chờ chỗ phù hợp đầu tiên, không chờ riêng chỗ chị A | Người thuê | BR-21 |
| 4 | Agent đối chiếu khung giờ, kích thước xe – ô, lịch sử hai bên (hay về sớm, hay quá giờ), đề xuất cách ghép; rule engine kiểm lại rồi mới chốt | W2 | BR-11, BR-14 |
| 5 | Chị A chưa đi, nhưng anh C (tầng khác) đã đăng và xe đã ra → ghép ngay chỗ anh C cho anh B | W2 | BR-21: chỗ trống trước ghép trước |
| 6 | Chỗ được **giữ vài phút**; anh B không xác nhận kịp → trả chỗ cho người kế tiếp trong hàng | N9 → W2 | BR-22 |
| 7 | Hai bên xác nhận OTP. Hủy thì hoàn theo quy định trong thỏa thuận (chỉ ghi nhận khoản, không thu tiền qua app) | M6, M5 | BR-23 |
| 8 | Gần giờ ra thì nhắc anh B; quá giờ mà xe chưa ra thì báo bảo vệ, tính phí khi xe ra | N2, W4 | BR-08, FR-32 |
| 9 | Anh C về sớm: xem §2 | W3 | BR-07, BR-24 |

## 2. Chủ về sớm: ETA và ưu tiên người thuê

1. Anh C bấm **"Tôi về sớm"**. App lấy vị trí **một lần** (có đồng ý, A-11); không cho phép thì anh C chọn 15 / 30 / 60 phút.
2. Hệ thống ước tính giờ về có tính kẹt xe (port ETA, demo dùng mock, ADR-0014). Không lưu tọa độ, chỉ lưu giờ về dự kiến.
3. Báo anh B: "Chủ chỗ về khoảng 15:10", kèm ô khác còn trống (nếu có) và hạn trả lời (trước giờ về dự kiến 5 phút).
4. Anh B đồng ý **dời** → đổi lượt đỗ sang ô mới, anh C về đúng ô của mình. Xong.
5. Anh B **ở lại** hoặc không trả lời → anh B được giữ ô tới hết giờ đã đặt (**ưu tiên người thuê**, BR-07). Bảo vệ chỉ anh C đỗ
   **ô dự phòng / bãi khách** trong tòa, anh C không mất phí.
6. Hết ô dự phòng → BQL xử lý (HITL) và tòa **tạm ngừng nhận lượt thuê mới** cho tới khi có lại ô dự phòng (BR-24).

## 3. Ai làm gì

| Vai trò | Việc |
|---------|------|
| Chủ chỗ | Đăng giờ rảnh, báo về sớm, xác nhận OTP |
| Người thuê | Vào hàng chờ, xác nhận trong thời gian giữ chỗ, chọn dời / ở lại khi chủ về sớm, ra đúng giờ |
| Bảo vệ | Nhận báo quá giờ; chỉ chủ về sớm vào ô dự phòng |
| BQL tòa | Duyệt lượt vượt ngưỡng, xử lý khi hết ô dự phòng, quyết định tranh chấp |
| Agent | Đề xuất ghép, phân loại duyệt, dựng dòng thời gian tranh chấp; **không chốt** |
| Rule engine | Chốt ghép, giữ chỗ, hoàn tiền, phí, tạm ngừng nhận lượt |

## 4. AI dùng vào đâu

| Việc | AI làm | Quy tắc cố định còn quyết định | Đo bằng |
|------|--------|--------------------------------|---------|
| Ghép chỗ (FR-30) | Xếp hạng ứng viên theo giờ, kích thước, lịch sử, kèm lý do | Quyền thuê, kích thước, giờ, thứ tự hàng chờ; sai quy tắc thì lấy phương án tất định | Tỉ lệ đề xuất bị bác, thời gian chờ ghép |
| Duyệt cao điểm (FR-33) | Chia "duyệt nhanh" / "cần xem kỹ" kèm lý do | Trường hợp bắt buộc xem kỹ; BQL vẫn bấm duyệt | Thời gian duyệt mỗi lượt |
| Tranh chấp (FR-34) | Dựng dòng thời gian từ thỏa thuận, giờ ra vào cổng, ảnh; mỗi câu ghi nguồn | BQL quyết định | Thời gian lập hồ sơ |

Log cổng, ảnh là **bằng chứng cần xác minh**, không phải kết luận. Tên, biển số thay bằng mã giả trước khi gửi LLM (BR-14).

## 5. Hai điểm lưu ý (phản hồi mentor)

- "Xe ra cổng chưa chắc ô đã trống": vẫn đúng ý mentor vì có thêm bước chủ tự đăng. Ô là của chị A, chị A đăng và xe chị A ra
  thì gần như chắc chắn ô đã trống (BR-20).
- Bản trước ghép hoàn toàn bằng code. Bản này để Agent đề xuất ghép, quy tắc cố định vẫn chốt cuối cùng (BR-14).

## 6. Dữ liệu cần thêm (ticket SCRUM-183)

`parking_request`: trạng thái chờ, `queued_at` · `share_window.owner_exited_at` · `recovery_case`: `owner_eta_at`, `eta_source`,
`renter_decision`, ô dự phòng cấp cho chủ · cờ tạm ngừng nhận lượt theo tòa · `payment` thành sổ khoản phí (không có trạng thái QR).
Thiết kế chi tiết làm trong migration, cập nhật [schema.sql](../03-design/sql/schema.sql) cùng lúc.

## 7. Kịch bản demo (ticket SCRUM-191)

Chị A đăng, chưa ra · anh B vào hàng chờ · anh C đăng và ra → anh B được ghép, xác nhận OTP · anh B gần hết giờ được nhắc ·
anh C bấm về sớm (kẹt xe, ETA 25 phút) → anh B chọn ở lại → anh C đỗ ô dự phòng · lần hai hết ô dự phòng → BQL nhận ca, tòa
tạm ngừng nhận lượt · anh B quá giờ → bảo vệ được báo, phí tính khi xe ra.
