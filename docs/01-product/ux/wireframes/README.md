# Wireframes — ParkSmart AI

> **File này trả lời:** mở wireframe thế nào, mỗi màn hình có trạng thái nào (`?state=`), màn hình nào làm trong 4 tuần.
> Nguồn: [PRD](../../02-prd.md) · [Scope](../../03-scope.md) · [User Stories & AC](../../04-user-stories.md) · [User Flow](../01-user-flow.md) · [Traceability §1](../../06-traceability.md#1-user-story--use-case) · [Backlog](../../05-backlog.md)

Wireframe low-fidelity (HTML/CSS/JS thuần, không phụ thuộc ngoài). Cột *Mức* = [Backlog §1](../../05-backlog.md#1-cách-đọc);
màn hình mức 3 giữ làm thiết kế, chỉ code nếu còn thời gian.

## 1. Cách xem

- Mở [index.html](index.html) trên trình duyệt (hoặc `python3 -m http.server` trong thư mục này).
- **Thanh "Trạng thái UI"** (xám) đổi trạng thái để review; deep link `?state=<key>`, ví dụ `agreement.html?state=hitl`.
- **(Demo)** = mô phỏng bên kia; **TBD** (khung gạch chéo) = chưa xác định; hộp nét đứt = US/FR/AC/BR của màn hình.
- Cấu trúc: `index.html`, `assets/wireframe.css`, `assets/wireframe.js` (nav, trạng thái, modal, toast) và 19 màn hình ở §2.

## 2. Danh mục màn hình

| Vai trò | Màn hình | Mục đích | Trạng thái (`?state=`) | Tham chiếu | Mức |
|---|---|---|---|---|---|
| Chung | [`register`](register.html) | Khai báo nhóm, xe, đồng ý xử lý biển số / ảnh | `default` · `loading` · `error` · `success` | A-03, BR-11 | 2 |
| Chung | [`notifications`](notifications.html) | Cập nhật, cảnh báo, nhắc quá giờ (2 lần), yêu cầu chờ duyệt | `default` · `empty` · `loading` · `error` | Scope §1 | 1 |
| Người cần chỗ | [`request-parking`](request-parking.html) | Định tuyến, ghép theo giờ + kích thước, chặn sai đối tượng | `form` · `loading` · `matched` · `redirect` · `nofit` · `blocked` · `error` | US-01–03/06/16 | 1 |
| Hai bên | [`agreement`](agreement.html) | Thỏa thuận theo mẫu, OTP hai bên, HITL, bằng chứng | `pending` · `waiting` · `loading` · `hitl` · `effective` · `rejected` · `error` | US-07/08, AC-15 | 1 |
| Người thuê | [`payment`](payment.html) | **Bỏ** (không thanh toán QR, plan 022); khoản xem trong `renter-booking` | — | AC-16 | — |
| Chủ chỗ | [`owner-home`](owner-home.html) | Chỗ TH1/TH2, lịch hôm nay, giao dịch | `default` · `empty` · `loading` · `error` | US-05/09 | 1 |
| Chủ chỗ | [`owner-share-schedule`](owner-share-schedule.html) | Đăng lịch + dự phòng (phần dự báo: mức 3) | Đăng: `default` · `loading` · `error` · `success` | US-05, AC-05 | 1 |
| Chủ chỗ | [`owner-early-return`](owner-early-return.html) | Báo về sớm → người thuê sang TH3 | `default` · `loading` · `success` · `th3full` · `error` | US-09/10, AC-09 | 2 |
| Người thuê | [`renter-booking`](renter-booking.html) | Lượt đỗ hiện tại, chuyển TH3, quá giờ + phí | `active` · `reassigned` · `overstay` · `ended` · `empty` · `loading` | US-10/11, AC-09/10 | 2 |
| BQL | [`admin-approvals`](admin-approvals.html) | Duyệt / từ chối giao dịch vượt ngưỡng | Danh sách `default` · `empty` · `loading` · `error`; chi tiết `review` · `approved` · `rejected` | AC-15, BR-12 | 1 |
| BQL | [`admin-dashboard`](admin-dashboard.html) | KPI theo khu, hàng chờ (đối soát, nguồn LPR: mức 3) | `default` · `empty` · `loading` · `error` | Scope §6 | 2 |
| BQL | [`admin-ledger`](admin-ledger.html) | Bằng chứng xác nhận (chỉ ghi thêm) | `default` · `empty` · `loading` · `error` | US-08 | 2 |
| BQL | [`admin-lpr-review`](admin-lpr-review.html) | Sự kiện LPR, bỏ trùng, hàng chờ OCR thấp | `default` · `empty` · `loading` · `error`; `todo` · `saved` · `unreadable` | US-17, AC-17 | 3 |
| Chung | [`dispute-report`](dispute-report.html) | Gửi ảnh tranh chấp; ticket ẩn biển số | `form` · `loading` · `success` · `error` | US-12/13 | 2 |
| BQL | [`admin-disputes`](admin-disputes.html) | Danh sách ticket | `default` · `empty` · `loading` · `error` | US-12 | 2 |
| BQL | [`admin-dispute-detail`](admin-dispute-detail.html) | Ảnh, đối chiếu bằng chứng xác nhận / cổng, quyết định của BQL (xem biển số gốc có log: mức 3) | `open` · `loading` · `done` | AC-11/12 | 2 |
| BQL | [`admin-swaps`](admin-swaps.html) | Duyệt hoán đổi 2 bên / nhiều bên theo vòng | `default` · `empty` · `loading`; `review` · `approved` · `rejected` | US-15 | 3 |
| Cư dân | [`swap-proposal`](swap-proposal.html) | Đề xuất hoán đổi và trạng thái | `pending` · `approved` · `rejected` · `empty` | US-14 | 3 |
| Shophouse | [`shophouse-voucher`](shophouse-voucher.html) | Voucher lượt TH3 cho khách | `form` · `loading` · `success` · `error` | FR-22 | 3 |

**Chưa có wireframe:** màn hình chat Agent (W0, W7) và đăng nhập — mức 1, cần vẽ trước tuần 1.

## 3. Hành trình trong 4 tuần

| # | Hành trình | Các bước | Mức |
|---|---|---|---|
| J1 | Thuê chỗ TH1/TH2 | `request-parking?state=matched` → `agreement` → `renter-booking` | 1 |
| J2 | Chuyển TH3 / bãi công cộng | `request-parking?state=redirect` | 1 |
| J3 | Chủ chỗ chia sẻ | `owner-home` → `owner-share-schedule` → `notifications` → `agreement` | 1 |
| J4 | Giao dịch vượt ngưỡng | `agreement?state=waiting` → `?state=hitl` → `admin-approvals` → `admin-ledger` | 1 |
| J5 | Chủ về sớm | `owner-early-return` → `renter-booking?state=reassigned` | 2 |
| J6 | Đỗ quá giờ | `notifications` (nhắc) → `renter-booking?state=overstay` | 2 |
| J7 | Tranh chấp | `dispute-report` → `admin-disputes` → `admin-dispute-detail` | 2 |

Hành trình mức 3 (hoán đổi sau tranh chấp lặp, hàng chờ OCR) vẫn xem được trong [index.html](index.html).

## 4. Quy tắc thể hiện trong wireframe

- TH3 không có trong danh sách chia sẻ cá nhân (BR-03); mỗi khung chia sẻ có dự phòng (AC-05).
- Thỏa thuận chỉ hiệu lực khi hai bên xác nhận; vượt ngưỡng chờ BQL (AC-07, AC-15).
- Không có màn thanh toán: app chỉ hiện khoản đã ghi nhận (A-05). Voucher chỉ cho TH3 (AC-16).
- Biển số luôn ẩn; tóm tắt của Agent gắn nhãn "Gợi ý"; quyết định do BQL bấm (BR-14).
- Bằng chứng xác nhận không có nút sửa / xóa (PRD §9).

## 5. Giả định và câu hỏi mở

| # | Giả định của wireframe | Màn hình |
|---|---|---|
| W-02 | Chủ chỗ báo về sớm bằng nút trong app (phát hiện qua LPR: mức 3) | `owner-early-return` |
| W-03 | Nhóm người dùng, xe, kích thước lấy từ hồ sơ, không nhập lại | `request-parking` |
| W-04 | Nội quy chia sẻ hiển thị và đồng ý ở bước đăng ký | `register` |
| W-05 | *(bỏ)* Thanh toán sau khi thỏa thuận có hiệu lực | — |
| W-07 | Bãi công cộng chỉ hiển thị chuyển hướng, không đặt chỗ (Scope §2) | `request-parking` |
| W-08 | Chỉ có giao diện BQL; vai trò `guard` và các bên quản lý khác chưa có màn hình | `admin-*` |

**Đã chốt mặc định** (cần BQL xác nhận, [01-data-model](../../../03-design/01-data-model.md)): dự phòng 15/30 phút, ngưỡng duyệt 1 000 000 đ / thỏa thuận,
giá trong `zone_policy.prices`, chủ về sớm không chịu thêm phí (D-09).
**Còn mở cho mức 1–2:** ưu tiên TH1 hay TH2 khi ghép; toàn văn mẫu thỏa thuận; thời hạn chờ xác nhận OTP; lý do bắt buộc khi BQL từ chối;
thông báo khi không có ô phù hợp (AC-06).
