# Wireframes — ParkSmart AI

Wireframe tương tác low-fidelity (HTML/CSS/JS thuần, không framework, không phụ thuộc ngoài) cho Agent điều phối quyền sử dụng chỗ đỗ.

> Nguồn yêu cầu: [Project Brief](../../project-brief.md) · [PRD](../../prd.md) · [Scope](../../scope.md) · [User Stories](../../user-stories.md) · [Acceptance Criteria](../../acceptance-criteria.md) · [User Flow](../user-flow.md)

## 1. Cách xem

- Mở `index.html` trực tiếp trên trình duyệt (không cần server). Có thể dùng `python3 -m http.server` trong thư mục này nếu muốn.
- **Thanh "Trạng thái UI"** (màu xám, trên mỗi khối): chuyển giữa các trạng thái mặc định / trống / đang tải / lỗi / thành công… Chỉ dùng để review wireframe, không phải UI thật.
- **Deep link trạng thái**: thêm `?state=<key>` vào URL, ví dụ `agreement.html?state=hitl`, `renter-booking.html?state=overstay`.
- Nút có nhãn **(Demo)** mô phỏng hành động của bên kia hoặc của hệ thống.
- Nhãn **TBD** (khung gạch chéo) đánh dấu chỗ tài liệu chưa xác định.
- Mỗi màn hình có hộp ghi chú nét đứt liệt kê US / FR / AC / BR liên quan.
- Responsive: dưới 720px, menu bên trái chuyển thành nút **Menu** trên thanh trên cùng; lưới nhiều cột chuyển thành một cột.

## 2. Cấu trúc

```
wireframes/
├── index.html                  # Danh mục màn hình + hành trình
├── README.md
├── assets/
│   ├── wireframe.css           # Style xám dùng chung, responsive
│   └── wireframe.js            # Nav, chuyển trạng thái, modal, tab, toast, xem biển số có log
├── register.html
├── notifications.html
├── dispute-report.html
├── owner-home.html
├── owner-share-schedule.html
├── owner-early-return.html
├── request-parking.html
├── agreement.html
├── payment.html
├── renter-booking.html
├── swap-proposal.html
├── shophouse-voucher.html
├── admin-dashboard.html
├── admin-approvals.html
├── admin-disputes.html
├── admin-dispute-detail.html
├── admin-swaps.html
├── admin-lpr-review.html
└── admin-ledger.html
```

## 3. Danh mục màn hình

| Vai trò | File | Mục đích | Trạng thái UI | Tham chiếu |
|---|---|---|---|---|
| Chung | `register.html` | Khai báo nhóm người dùng, xe (biển số, kích thước), đồng ý xử lý biển số/ảnh | mặc định, đang gửi, lỗi, thành công | A-03, PRD §2, BR-11 |
| Chung | `notifications.html` | Cập nhật trạng thái, cảnh báo, yêu cầu chờ duyệt trong app | có dữ liệu, trống, đang tải, lỗi | Scope §1 |
| Chung | `dispute-report.html` | Gửi ảnh; Agent đọc ảnh, đối chiếu, lập ticket ẩn biển số | nhập, đang xử lý, thành công, lỗi | US-12/13, FR-13–16, AC-11/12 |
| Chủ chỗ | `owner-home.html` | Chỗ TH1/TH2, lịch hôm nay (chia sẻ + dự phòng), giao dịch | có dữ liệu, trống, đang tải, lỗi | US-04/05/09/11 |
| Chủ chỗ | `owner-share-schedule.html` | Dự báo (tham khảo), khung giờ đề xuất, dự phòng, đăng lịch | dự báo: có/thiếu dữ liệu/đang tính; đăng: chưa/đang/lỗi/xong | US-04/05/18, AC-04/05/18 |
| Chủ chỗ | `owner-early-return.html` | Báo về sớm → người thuê sang TH3 | xác nhận, đang điều phối, xong, TH3 hết chỗ, lỗi | US-09/10, AC-09, BR-07 |
| Người cần chỗ | `request-parking.html` | Định tuyến, ghép theo giờ + kích thước, chặn sai đối tượng | nhập, đang xử lý, ghép TH1/TH2, chuyển TH3/bãi công cộng, không có ô phù hợp, bị chặn, lỗi | US-01–03/06/16, AC-01–03/06 |
| Hai bên | `agreement.html` | Thỏa thuận theo mẫu, hai bên xác nhận, HITL, sổ cái | chờ tôi, chờ bên kia, đang xử lý, chờ BQL, có hiệu lực, BQL từ chối, lỗi | US-07/08, AC-07/08/15 |
| Người thuê / khách | `payment.html` | VietQR mock; voucher chỉ cho lượt TH3 | loại: chia sẻ / TH3; thanh toán: chờ QR, đang, đã ghi nhận, thất bại; modal lỗi voucher | AC-16, FR-21/22 |
| Người thuê | `renter-booking.html` | Lượt đỗ hiện tại, chuyển TH3, quá giờ | đang đỗ, chuyển TH3, quá giờ, kết thúc, trống, đang tải | US-10/11, AC-09/10 |
| Cư dân | `swap-proposal.html` | Xem đề xuất hoán đổi và trạng thái duyệt | chờ BQL, đã duyệt, từ chối, trống | US-14, AC-13/14 |
| Shophouse | `shophouse-voucher.html` | Cấp voucher lượt TH3 cho khách | tạo, đang tạo, đã tạo, lỗi | FR-22, BR-06 |
| BQL | `admin-dashboard.html` | Hàng chờ HITL, KPI, đối soát cuối ngày, nguồn LPR | có dữ liệu, không có việc, đang tải, lỗi | Scope §1/§6 |
| BQL | `admin-approvals.html` | Duyệt / từ chối giao dịch vượt ngưỡng | danh sách & chi tiết: có/trống/tải/lỗi; duyệt/từ chối | AC-15, BR-12 |
| BQL | `admin-disputes.html` | Danh sách ticket (biển số ẩn) | có dữ liệu, trống, đang tải, lỗi | US-12 |
| BQL | `admin-dispute-detail.html` | Ảnh, đối chiếu sổ cái/cổng, tóm tắt Agent (gợi ý), xác minh, xem biển số gốc có log | xác minh: chờ/đang lưu/xong; modal xem biển số | AC-11/12, BR-14 |
| BQL | `admin-swaps.html` | Duyệt hoán đổi 2 bên / theo chuỗi | mỗi đề xuất: chờ/đang lưu/duyệt/từ chối; danh sách trống | US-15, AC-14 |
| BQL | `admin-lpr-review.html` | Sự kiện chuẩn hóa, bỏ qua trùng, hàng chờ OCR thấp, ứng viên so khớp mờ | có/trống/tải/lỗi; xác nhận/không đọc được | US-17, AC-10a/17, FR-16a/19 |
| BQL | `admin-ledger.html` | Sổ cái append-only, kiểm tra chuỗi hash | danh sách: có/trống/tải/lỗi; toàn vẹn: chưa/đang/hợp lệ/sai | US-08, PRD §8 |

## 4. Hành trình người dùng

| # | Hành trình | Các bước (màn hình) | Nguồn |
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

- TH3 không xuất hiện trong danh sách chỗ có thể chia sẻ của cá nhân (BR-03).
- Mỗi khung chia sẻ luôn hiển thị kèm khoảng dự phòng (AC-05).
- Dự báo hiển thị như gợi ý tham khảo, không tự đăng lịch (AC-18).
- Thỏa thuận chỉ có hiệu lực khi cả hai bên xác nhận; giao dịch vượt ngưỡng chờ BQL (AC-07, AC-15).
- Voucher chỉ áp dụng cho lượt TH3; áp dụng cho giao dịch TH1/TH2 hiện lỗi (AC-16).
- VietQR luôn ghi rõ "mô phỏng, không thu tiền thật" (AC-16, A-05).
- Biển số luôn hiển thị dạng ẩn; chỉ BQL bấm "Xem bản gốc", bắt buộc nhập lý do, lượt xem được thêm vào nhật ký (AC-12).
- Tóm tắt của Agent gắn nhãn "Gợi ý"; quyết định tranh chấp, hoán đổi và giao dịch vượt ngưỡng do BQL bấm (Scope §1–2).
- Log trùng mã hiển thị "Bỏ qua — trùng mã"; OCR thấp vào hàng chờ, so khớp mờ chỉ là ứng viên (AC-10a, AC-17).
- Sổ cái không có nút sửa/xóa (PRD §8).

## 6. Giả định của wireframe

Các điểm sau không được tài liệu quy định; wireframe chọn một cách hiển thị và đánh dấu tại màn hình tương ứng:

| # | Giả định | Màn hình |
|---|---|---|
| W-01 | Tranh chấp được báo qua form trong app (tài liệu: "kênh báo: TBD"). | `dispute-report` |
| W-02 | Chủ chỗ báo về sớm bằng nút trong app; cũng có thể phát hiện qua LPR. | `owner-early-return` |
| W-03 | Nhóm người dùng, xe, kích thước xe lấy từ hồ sơ đăng ký, không nhập lại khi yêu cầu chỗ. | `request-parking` |
| W-04 | Nội quy chia sẻ được hiển thị/đồng ý tại bước đăng ký. | `register` |
| W-05 | Thanh toán diễn ra sau khi thỏa thuận có hiệu lực. | `agreement` → `payment` |
| W-06 | Người dùng chỉ *xem* đề xuất hoán đổi; không thêm bước đồng ý của người dùng vì tài liệu chỉ yêu cầu BQL phê duyệt. | `swap-proposal` |
| W-07 | Bãi công cộng chỉ hiển thị thông tin chuyển hướng, không đặt chỗ (Scope §2). | `request-parking` |
| W-08 | Giao diện chỉ dành cho vai trò BQL ở phía quản lý; các bên quản lý khác chưa có màn hình. | `admin-*` |

## 7. Yêu cầu chưa giải quyết (TBD)

**Định tuyến & ghép**
- Ưu tiên TH1 hay TH2 khi ghép; "quyền ưu tiên đã cấu hình" gồm những gì.
- Tiêu chí xác minh "người sử dụng tòa nhà" và ai xác nhận nhóm người dùng.
- Danh mục kích thước xe / kích thước ô.
- Thông báo và đề xuất thay thế khi không có ô phù hợp (AC-06); nội dung lý do khi chặn giao dịch.

**Chia sẻ & thỏa thuận**
- Độ dài khoảng dự phòng; khung giá; toàn văn mẫu thỏa thuận.
- Chia sẻ theo từng ngày hay lặp lại hằng tuần.
- Bên có thể từ chối thỏa thuận không; thời hạn chờ xác nhận.
- Ngưỡng định mức cần BQL duyệt và tiêu chí (tiền, giờ, lượt?); bắt buộc lý do khi từ chối.
- Cư dân cho khách của mình đỗ miễn phí (BR-05): có luồng đăng ký khách không — **chưa có màn hình**.

**Ngoại lệ**
- Hướng xử lý khi pool TH3 hết chỗ (AC-09); thời hạn chuyển xe; điều chỉnh phí cho người thuê bị chuyển.
- Mức phí quá giờ và thời điểm bắt đầu tính; số lần/kênh nhắc.

**Thanh toán & voucher**
- Số tiền thực tế, thời điểm thanh toán, hoàn tiền.
- Giá trị, thời hạn, giới hạn số lượng, bên chịu chi phí và đối soát voucher.

**Tranh chấp, hoán đổi, LPR**
- Kênh báo tranh chấp; danh mục loại tranh chấp; danh sách kết quả xác minh và hệ quả; SLA.
- Định nghĩa "tranh chấp lặp lại"; hoán đổi quyền sở hữu hay quyền sử dụng; có cần các bên đồng ý.
- Ngưỡng độ tin cậy OCR; vai trò người kiểm tra (BQL / bảo vệ / đơn vị trông giữ xe); xử lý sau "không đọc được".
- Hướng xử lý khi phát hiện chuỗi hash sổ cái bị sửa.

**Vai trò & hệ thống**
- Phương thức đăng nhập/xác thực; quy trình rút đồng ý dữ liệu; thời hạn lưu ảnh/log.
- Vai trò **bảo vệ** (PRD §8) và các bên quản lý khác (chủ đầu tư, Ban quản trị, Hội nghị nhà chung cư, đơn vị trông giữ xe) chưa có user story → **chưa có màn hình**.
- Kênh thông báo ngoài app; nội dung báo cáo đối soát cuối ngày; mục tiêu KPI.
- Mức ưu tiên (MoSCoW) của từng story để quyết định màn hình nào thuộc MVP.
