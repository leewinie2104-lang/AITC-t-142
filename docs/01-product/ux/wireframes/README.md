# Wireframes — ParkSmart AI

> File này trả lời: mở wireframe thế nào, mỗi màn hình có trạng thái nào (key `?state=`), và người dùng đi qua những màn hình nào.
> Nguồn yêu cầu: [Project Brief](../../01-project-brief.md) · [PRD](../../02-prd.md) · [Scope](../../03-scope.md) · [User Stories & AC](../../04-user-stories.md) · [User Flow](../01-user-flow.md)

Wireframe low-fidelity (HTML/CSS/JS thuần, không framework, không phụ thuộc ngoài). Ánh xạ US → màn hình đầy đủ ở [06-traceability §1](../../06-traceability.md#1-bảng-tổng).

## 1. Cách xem

- Mở [index.html](index.html) trực tiếp trên trình duyệt, không cần server (hoặc `python3 -m http.server` trong thư mục này).
- **Thanh "Trạng thái UI"** (xám, trên mỗi khối) đổi trạng thái để review. Không phải UI thật.
- **Deep link:** `?state=<key>`, ví dụ `agreement.html?state=hitl`, `renter-booking.html?state=overstay`. Key lấy từ `data-states` của từng file (mục 3).
- **(Demo)** mô phỏng bên kia hoặc hệ thống. **TBD** (khung gạch chéo) = chỗ chưa xác định. Hộp nét đứt liệt kê US/FR/AC/BR của màn hình.
- Dưới 720px: menu trái thành nút **Menu**; lưới nhiều cột thành một cột.

## 2. Cấu trúc

`wireframes/`: `index.html` (danh mục, hành trình), `README.md`, `assets/wireframe.css` (style xám dùng chung), `assets/wireframe.js` (nav, chuyển trạng thái, modal, tab, toast, xem biển số có log), và 19 file màn hình ở mục 3.

## 3. Danh mục màn hình

Trạng thái: `key` nhãn. Nhiều nhóm trên một màn hình ngăn bằng ";".

| Vai trò | Màn hình | Mục đích | Trạng thái (`?state=`) | Tham chiếu |
|---|---|---|---|---|
| Chung | [`register.html`](register.html) | Khai báo nhóm, xe, đồng ý xử lý biển số/ảnh | `default` mặc định · `loading` đang gửi · `error` lỗi · `success` thành công | A-03, PRD §3.1, BR-11 |
| Chung | [`notifications.html`](notifications.html) | Cập nhật, cảnh báo, yêu cầu chờ duyệt | `default` có dữ liệu · `empty` trống · `loading` đang tải · `error` lỗi | Scope §1 |
| Chung | [`dispute-report.html`](dispute-report.html) | Gửi ảnh; Agent đọc ảnh, đối chiếu, lập ticket ẩn biển số | `form` nhập · `loading` đang xử lý · `success` thành công · `error` lỗi | US-12/13, FR-13–16, AC-11/12 |
| Chủ chỗ | [`owner-home.html`](owner-home.html) | Chỗ TH1/TH2, lịch hôm nay (chia sẻ + dự phòng), giao dịch | `default` có dữ liệu · `empty` chưa có chỗ · `loading` đang tải · `error` lỗi | US-04/05/09/11 |
| Chủ chỗ | [`owner-share-schedule.html`](owner-share-schedule.html) | Dự báo (tham khảo), khung giờ đề xuất, dự phòng, đăng lịch | Dự báo: `default` có · `empty` thiếu dữ liệu · `loading` đang tính. Đăng: `default` chưa · `loading` đang · `error` lỗi · `success` xong | US-04/05/18, AC-04/05/18 |
| Chủ chỗ | [`owner-early-return.html`](owner-early-return.html) | Báo về sớm → người thuê sang TH3 | `default` xác nhận · `loading` đang điều phối · `success` đã điều phối · `th3full` TH3 hết chỗ · `error` lỗi | US-09/10, AC-09, BR-07 |
| Người cần chỗ | [`request-parking.html`](request-parking.html) | Định tuyến, ghép theo giờ + kích thước, chặn sai đối tượng | `form` nhập · `loading` đang xử lý · `matched` ghép TH1/TH2 · `redirect` chuyển TH3/bãi công cộng · `nofit` không có ô phù hợp · `blocked` bị chặn · `error` lỗi | US-01–03/06/16, AC-01–03/06 |
| Hai bên | [`agreement.html`](agreement.html) | Thỏa thuận theo mẫu, hai bên xác nhận, HITL, bằng chứng xác nhận | `pending` chờ tôi · `waiting` chờ bên kia · `loading` đang xử lý · `hitl` chờ BQL duyệt · `effective` có hiệu lực · `rejected` BQL từ chối · `error` lỗi | US-07/08, AC-07/08/15 |
| Người thuê / khách | [`payment.html`](payment.html) | VietQR mock; voucher chỉ cho lượt TH3 | Loại: `share` chia sẻ TH1/TH2 · `th3` lượt đỗ TH3. Thanh toán: `qr` chờ quét · `loading` đang mô phỏng · `paid` đã ghi nhận · `failed` thất bại. Modal lỗi voucher | AC-16, FR-21/22 |
| Người thuê | [`renter-booking.html`](renter-booking.html) | Lượt đỗ hiện tại, chuyển TH3, quá giờ | `active` đang đỗ · `reassigned` chủ về sớm → TH3 · `overstay` quá giờ · `ended` kết thúc · `empty` không có lượt · `loading` đang tải | US-10/11, AC-09/10 |
| Cư dân | [`swap-proposal.html`](swap-proposal.html) | Đề xuất hoán đổi và trạng thái duyệt | `pending` chờ BQL · `approved` đã duyệt · `rejected` từ chối · `empty` trống | US-14, AC-13/14 |
| Shophouse | [`shophouse-voucher.html`](shophouse-voucher.html) | Cấp voucher lượt TH3 cho khách | `form` tạo · `loading` đang tạo · `success` đã tạo · `error` lỗi | FR-22, BR-06 |
| BQL | [`admin-dashboard.html`](admin-dashboard.html) | Hàng chờ HITL, KPI, đối soát cuối ngày, nguồn LPR | `default` có dữ liệu · `empty` không có việc chờ · `loading` đang tải · `error` lỗi | Scope §1/§6 |
| BQL | [`admin-approvals.html`](admin-approvals.html) | Duyệt / từ chối giao dịch vượt ngưỡng | Danh sách: `default` có · `empty` trống · `loading` · `error`. Chi tiết: `review` đang xem · `loading` đang lưu · `approved` · `rejected` | AC-15, BR-12 |
| BQL | [`admin-disputes.html`](admin-disputes.html) | Danh sách ticket (biển số ẩn) | `default` có ticket · `empty` trống · `loading` đang tải · `error` lỗi | US-12 |
| BQL | [`admin-dispute-detail.html`](admin-dispute-detail.html) | Ảnh, đối chiếu bằng chứng xác nhận/cổng, tóm tắt Agent (gợi ý), xác minh, xem biển số gốc có log | Xác minh: `open` chờ · `loading` đang lưu · `done` xong. Modal xem biển số | AC-11/12, BR-14 |
| BQL | [`admin-swaps.html`](admin-swaps.html) | Duyệt hoán đổi 2 bên / theo chuỗi | Danh sách: `default` có · `empty` trống · `loading`. Mỗi đề xuất: `review` chờ · `loading` đang lưu · `approved` · `rejected` | US-15, AC-14 |
| BQL | [`admin-lpr-review.html`](admin-lpr-review.html) | Sự kiện chuẩn hóa, bỏ trùng, hàng chờ OCR thấp, ứng viên so khớp mờ | Hàng chờ: `default` có · `empty` trống · `loading` · `error`. Kết quả: `todo` chưa xử lý · `saved` đã xác nhận · `unreadable` không đọc được | US-17, AC-10a/17, FR-16a/19 |
| BQL | [`admin-ledger.html`](admin-ledger.html) | Bằng chứng xác nhận (chỉ ghi thêm) | Danh sách: `default` có bản ghi · `empty` trống · `loading` · `error` | US-08, PRD §9 |

## 4. Hành trình người dùng

| # | Hành trình | Các bước (màn hình, `?state=`) | Nguồn |
|---|---|---|---|
| J1 | Thuê chỗ riêng TH1/TH2 | `request-parking` → `?state=matched` → `agreement` → `payment` → `renter-booking` | Flow 1–2 |
| J2 | Khách chỉ dùng TH3 / bãi công cộng | `request-parking?state=redirect` → `payment?state=th3` (voucher từ `shophouse-voucher`) | Flow 1, AC-02/16 |
| J3 | Chủ chỗ chia sẻ | `owner-home` → `owner-share-schedule` → `notifications` → `agreement` | Flow 2 |
| J4 | Giao dịch vượt ngưỡng | `agreement?state=waiting` → `?state=hitl` → `admin-approvals` → `admin-ledger` | Flow 2, AC-15 |
| J5 | Chủ về sớm | `owner-early-return` → `renter-booking?state=reassigned` | Flow 3 |
| J6 | Đỗ quá giờ | `admin-lpr-review` (sự kiện) → `notifications` → `renter-booking?state=overstay` | Flow 3, 6 |
| J7 | Tranh chấp → hoán đổi | `dispute-report` → `admin-disputes` → `admin-dispute-detail` → `admin-swaps` → `swap-proposal` | Flow 4–5 |
| J8 | Xử lý log LPR | `admin-lpr-review` (hàng chờ OCR thấp) → `admin-dispute-detail` khi có dấu hiệu tranh chấp | Flow 6 |

## 5. Quy tắc đã thể hiện trong wireframe

Nguồn quy tắc: [User Stories & AC](../../04-user-stories.md), [PRD](../../02-prd.md).

- TH3 không có trong danh sách chỗ chia sẻ cá nhân (BR-03); mỗi khung chia sẻ có khoảng dự phòng (AC-05).
- Dự báo chỉ là gợi ý, không tự đăng lịch (AC-18).
- Thỏa thuận chỉ có hiệu lực khi hai bên xác nhận; giao dịch vượt ngưỡng chờ BQL (AC-07, AC-15).
- Voucher chỉ cho TH3, lỗi với TH1/TH2 (AC-16). VietQR ghi "mô phỏng, không thu tiền thật" (AC-16, A-05).
- Biển số luôn ẩn; chỉ BQL bấm "Xem bản gốc", nhập lý do, lượt xem được ghi nhật ký (AC-12).
- Tóm tắt Agent gắn nhãn "Gợi ý"; tranh chấp, hoán đổi, giao dịch vượt ngưỡng do BQL bấm (Scope §1–2).
- Log trùng hiển thị "Bỏ qua — trùng mã"; OCR thấp vào hàng chờ, so khớp mờ chỉ là ứng viên (AC-10a, AC-17).
- Bằng chứng xác nhận không có nút sửa/xóa (PRD §9, tính toàn vẹn).

## 6. Giả định của wireframe

Tài liệu không quy định; wireframe chọn một cách hiển thị và đánh dấu tại màn hình tương ứng.

| # | Giả định | Màn hình |
|---|---|---|
| W-01 | Tranh chấp báo qua form trong app (tài liệu: "kênh báo: TBD"). | `dispute-report` |
| W-02 | Chủ chỗ báo về sớm bằng nút trong app; cũng có thể phát hiện qua LPR. | `owner-early-return` |
| W-03 | Nhóm người dùng, xe, kích thước lấy từ hồ sơ đăng ký, không nhập lại. | `request-parking` |
| W-04 | Nội quy chia sẻ hiển thị và đồng ý tại bước đăng ký. | `register` |
| W-05 | Thanh toán diễn ra sau khi thỏa thuận có hiệu lực. | `agreement` → `payment` |
| W-06 | Người dùng chỉ *xem* đề xuất hoán đổi; không thêm bước đồng ý (tài liệu chỉ yêu cầu BQL duyệt). | `swap-proposal` |
| W-07 | Bãi công cộng chỉ hiển thị chuyển hướng, không đặt chỗ (Scope §2). | `request-parking` |
| W-08 | Giao diện chỉ cho vai trò BQL; các bên quản lý khác chưa có màn hình. | `admin-*` |

## 7. Yêu cầu chưa giải quyết (TBD)

**Định tuyến & ghép**
- Ưu tiên TH1 hay TH2 khi ghép; "quyền ưu tiên đã cấu hình" gồm gì.
- Tiêu chí "người sử dụng tòa nhà"; ai xác nhận nhóm người dùng.
- Danh mục kích thước xe / ô; thông báo và đề xuất thay thế khi không có ô (AC-06); lý do khi chặn.

**Chia sẻ & thỏa thuận**
- Độ dài dự phòng; khung giá; toàn văn mẫu thỏa thuận; chia sẻ theo ngày hay hằng tuần.
- Bên có từ chối thỏa thuận không; thời hạn chờ xác nhận.
- Ngưỡng cần BQL duyệt và tiêu chí (tiền, giờ, lượt?); bắt buộc lý do khi từ chối.
- Khách của cư dân đỗ miễn phí (BR-05): có luồng đăng ký khách không. **Chưa có màn hình.**

**Ngoại lệ**
- Xử lý khi pool TH3 hết chỗ (AC-09); thời hạn chuyển xe; điều chỉnh phí người thuê bị chuyển.
- Mức phí quá giờ, thời điểm bắt đầu tính; số lần và kênh nhắc.

**Thanh toán & voucher**
- Số tiền thực tế, thời điểm thanh toán, hoàn tiền.
- Giá trị, thời hạn, giới hạn số lượng, bên chịu chi phí, đối soát voucher.

**Tranh chấp, hoán đổi, LPR**
- Kênh báo tranh chấp; danh mục loại; kết quả xác minh và hệ quả; SLA.
- "Tranh chấp lặp lại" là gì; hoán đổi quyền sở hữu hay quyền sử dụng; có cần đồng ý các bên không.
- Ngưỡng OCR; vai trò người kiểm tra (BQL / bảo vệ / đơn vị trông giữ xe); xử lý sau "không đọc được".
- Xuất dữ liệu bằng chứng xác nhận.

**Vai trò & hệ thống**
- Phương thức đăng nhập; quy trình rút đồng ý dữ liệu; thời hạn lưu ảnh và log.
- Vai trò **bảo vệ** (PRD §9, phân quyền) và các bên quản lý khác (chủ đầu tư, Ban quản trị, Hội nghị nhà chung cư, đơn vị trông giữ xe) chưa có user story → **chưa có màn hình**.
- Kênh thông báo ngoài app; nội dung đối soát cuối ngày; mục tiêu KPI.
- MoSCoW của từng story để quyết định màn hình nào thuộc MVP.
