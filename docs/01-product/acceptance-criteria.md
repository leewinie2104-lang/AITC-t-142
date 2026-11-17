# Acceptance Criteria — Agent điều phối quyền sử dụng chỗ đỗ trong chuỗi khu đô thị

> Nguồn: [01-xac-dinh-bai-toan.md](../01-xac-dinh-bai-toan.md)
> Liên quan: [User Stories](user-stories.md) · [PRD §5 Quy tắc nghiệp vụ](prd.md#5-quy-tắc-nghiệp-vụ)

Định dạng Given / When / Then. Các ngưỡng số chưa có trong nguồn được đánh dấu **TBD**. Cấp tư cách: L1 = thành viên tòa, L2 = thành viên khu, L3 = thành viên chuỗi, L4 = khách ([PRD §3.2](prd.md#32-cấp-tư-cách-tại-vị-trí-chỗ-đỗ)).

## Epic 0 — Tư cách và liên khu

**AC-19 (US-19)** — Chủ shophouse liên khu
- **Given** người dùng có tư cách *chủ shophouse thấp tầng ở khu A* và *chủ căn hộ ở khu B*
- **When** yêu cầu chỗ ở một tòa thuộc khu A, khung giờ 7h–19h
- **Then** Agent xác định cấp tư cách là **L2** tại khu A
- **And** chỉ ghép vào các ô có phạm vi mở là Khu hoặc Chuỗi.
- **And** người dùng không có quyền BR-05 (cho khách đỗ miễn phí) tại khu A.
- Nếu shophouse nằm ở khối đế của chính tòa đó thì cấp tư cách là **L1** (A-10).

**AC-20 (US-20)** — Thành viên chuỗi thuê theo khung giờ
- **Given** cư dân khu B (L3 tại khu C), pool TH2 của khu C có phạm vi mở là Chuỗi
- **When** yêu cầu chỗ ở khu C cho các khung 7h–8h và 16h30–17h30
- **Then** Agent ghép vào TH2 của khu C với giá cấp L3.
- **And** nếu pool TH2 của khu C chỉ mở trong khu, Agent chuyển yêu cầu sang TH3 của khu C (AC-02).

**AC-21 (US-21)** — Một tài khoản, nhiều tư cách
- **Given** tài khoản có nhiều tư cách còn hiệu lực ở các khu khác nhau
- **When** yêu cầu chỗ ở bất kỳ tòa *T* nào
- **Then** Agent chọn cấp **cao nhất** đạt được tại *T*; tư cách ở khu khác chỉ được tính là L3 (BR-15).
- **And** người dùng không phải đăng ký lại tài khoản ở từng khu.

**AC-22 (US-22)** — Tư cách hết hạn
- **Given** tư cách người thuê căn hộ có hạn hiệu lực là ngày *D*
- **When** qua ngày *D*
- **Then** mọi yêu cầu thuê **mới** dựa trên tư cách đó bị chặn và được tính vào KPI "giao dịch sai tư cách bị chặn".
- **And** giao dịch đang hiệu lực được giữ tới hết kỳ hiện tại; người dùng và chủ chỗ liên quan nhận được thông báo.
- Kỳ tối đa được giữ lại: TBD.

**AC-23 (US-23)** — Chủ chỗ thu hẹp phạm vi
- **Given** nội quy tòa cho phép TH1 mở cho cả khu
- **When** chủ chỗ chọn phạm vi chia sẻ là "chỉ trong tòa"
- **Then** chỉ người dùng L1 của tòa đó được ghép vào chỗ này.
- **And** hệ thống không cho phép chủ chỗ chọn phạm vi rộng hơn mức nội quy cho phép.

**AC-24 (US-24)** — Dữ liệu tối thiểu giữa các khu
- **When** khu A cần kiểm tra tư cách của một người dùng có tài sản ở khu B
- **Then** khu A chỉ nhận được cấp tư cách và hạn hiệu lực.
- **And** số căn hộ, giấy tờ và hồ sơ cư dân không hiển thị với BQL khu A.

**AC-25 (US-25)** — Gợi ý khu lân cận
- **Given** khu có ô đỗ không còn ô phù hợp trong khung giờ yêu cầu
- **Then** Agent gợi ý các ô ở khu khác trong chuỗi mà người dùng đủ điều kiện thuê.
- **And** Agent không tự đặt chỗ khi người dùng chưa xác nhận.
- Tiêu chí "lân cận" (khoảng cách / thời gian di chuyển): TBD.

## Epic 1 — Định tuyến

**AC-01 (US-01)** — Ghép chỗ riêng
- **Given** cấp tư cách của người yêu cầu tại vị trí ô đỗ nằm trong phạm vi mở của pool
- **When** gửi yêu cầu chỗ đỗ
- **Then** Agent ghép vào chỗ TH1 hoặc TH2 còn trống thỏa phạm vi mở.
- Tiêu chí ưu tiên giữa TH1 và TH2: TBD.

**AC-02 (US-02)** — Chuyển sang TH3 / bãi công cộng
- **Given** cấp tư cách của người yêu cầu không đạt phạm vi mở của bất kỳ pool TH1/TH2 nào còn trống (kể cả khách shophouse)
- **When** gửi yêu cầu chỗ đỗ
- **Then** Agent không ghép vào TH1/TH2 mà chuyển sang TH3 hoặc bãi công cộng của khu đó, áp dụng giá theo cấp.

**AC-03 (US-03)** — Chặn giao dịch sai tư cách / sai phạm vi
- **Then** Agent từ chối và ghi nhận (tính vào KPI "giao dịch sai tư cách hoặc sai phạm vi bị chặn") khi:
  - chỗ TH1 được cho thuê cho người có cấp tư cách nằm ngoài phạm vi mở của ô (BR-01);
  - cá nhân cố cho thuê chỗ TH3 (BR-03);
  - giao dịch diễn ra ngoài phạm vi mở hoặc ngoài nền tảng chính thức (BR-04);
  - cư dân thu phí khi cho khách của mình đỗ, hoặc dùng quyền này tại tòa mà họ không phải L1 (BR-05);
  - giao dịch dựa trên tư cách đã hết hạn (BR-16).

## Epic 2 — Chia sẻ

**AC-04 (US-04)** — Đề xuất khung giờ
- **Given** chủ chỗ TH1/TH2 hoặc văn phòng có chỗ riêng
- **Then** Agent đề xuất các khung giờ có thể chia sẻ. Cơ sở dữ liệu để đề xuất: TBD.

**AC-05 (US-05)** — Khoảng dự phòng
- **Then** mỗi khung giờ chia sẻ có kèm một khoảng dự phòng. Độ dài khoảng dự phòng: TBD.

**AC-06 (US-06)** — Ghép cung–cầu
- **Then** người cần chỗ chỉ được ghép với chỗ chia sẻ hợp lệ theo AC-01, AC-03 và phạm vi chủ chỗ đã chọn (AC-23).
- **And** ô đỗ phù hợp với kích thước xe; việc ghép xét khung giờ, khoảng dự phòng và quyền ưu tiên đã cấu hình.
- Nếu không có ô phù hợp thì Agent không tạo ghép và chuyển sang gợi ý theo AC-25.

**AC-07 (US-07)** — Thỏa thuận điện tử
- **When** ghép thành công
- **Then** Agent sinh thỏa thuận điện tử theo mẫu và khung giá nội quy của **khu có ô đỗ**
- **And** thỏa thuận chỉ có hiệu lực khi **cả hai bên** xác nhận.

**AC-08 (US-08)** — Sổ cái
- **When** hai bên đã xác nhận
- **Then** giao dịch được ghi vào sổ cái và BQL của khu có ô đỗ ghi nhận.

## Epic 3 — Xử lý ngoại lệ

**AC-09 (US-09, US-10)** — Chủ về sớm
- **Given** chỗ đang được người thuê sử dụng theo thỏa thuận
- **When** chủ chỗ về sớm
- **Then** chủ được quay về chỗ của mình
- **And** Agent điều phối chỗ thay thế cho người thuê từ pool TH3 cùng khu.
- **And** nếu pool TH3 cùng khu hết chỗ, Agent gợi ý chỗ theo AC-25. Ai chịu chi phí chênh lệch: TBD.

**AC-10 (US-11)** — Đỗ quá giờ
- **When** người thuê vẫn đỗ sau khi hết khung giờ thỏa thuận
- **Then** Agent gửi nhắc nhở cho người thuê
- **And** tính phí theo nội quy của khu có ô đỗ. Mức phí và thời điểm bắt đầu tính: TBD.

**AC-10a** — Xử lý log LPR
- **Given** hệ thống nhận log LPR có mã sự kiện
- **When** mã sự kiện đó đã được xử lý trước đó
- **Then** log không tạo thêm giao dịch hoặc cảnh báo trùng.
- **And** log có độ tin cậy OCR thấp được đưa vào hàng chờ kiểm tra, không dùng để kết luận tự động.

## Epic 4 — Tranh chấp

**AC-11 (US-12)** — Lập ticket
- **When** có tranh chấp phát sinh
- **Then** Agent đọc ảnh, đối chiếu sổ cái và dữ liệu cổng của khu, lập ticket và chuyển cho **BQL của khu có ô đỗ** xác minh, kể cả khi một bên là thành viên khu khác (BR-18).
- Thời gian lập hồ sơ mục tiêu: TBD.

**AC-12 (US-13)** — Ẩn biển số
- **Then** mọi biển số trong ticket hiển thị ở dạng đã ẩn; chỉ BQL của khu liên quan được xem bản gốc.
- **And** biển số và tên được thay bằng mã giả trước khi nội dung được gửi tới LLM.
- **And** mọi lượt xem biển số gốc đều được ghi log.

## Epic 5 — Hoán đổi

**AC-13 (US-14)** — Đề xuất hoán đổi
- **Given** có tranh chấp lặp lại hoặc nhu cầu đã đăng ký
- **Then** Agent đề xuất hoán đổi giữa 2 bên hoặc theo chuỗi; mọi ô trong đề xuất phải thuộc **cùng một khu**.
- Định nghĩa "lặp lại" (số lần / khoảng thời gian): TBD.

**AC-14 (US-15)** — Phê duyệt
- **Then** hoán đổi chỉ có hiệu lực sau khi BQL khu phê duyệt; đề xuất bị từ chối không làm thay đổi phân bổ chỗ.

## Epic 6 — HITL và thanh toán demo

**AC-15** — Duyệt giao dịch vượt ngưỡng
- **Given** giao dịch vượt ngưỡng định mức đã cấu hình cho khu có ô đỗ
- **When** Agent tạo đề xuất giao dịch
- **Then** giao dịch ở trạng thái chờ BQL khu duyệt và chưa có hiệu lực trước khi được duyệt.

**AC-16** — VietQR mock và voucher
- **Given** người dùng thanh toán giao dịch trong bản demo
- **When** chọn VietQR mock
- **Then** hệ thống chỉ ghi nhận trạng thái mô phỏng, không xác nhận thu tiền thật.
- **And** voucher shophouse chỉ áp dụng cho lượt đỗ TH3; voucher không nâng cấp tư cách và không cho phép khách shophouse thuê TH1/TH2.

**AC-17 (US-17)** — Log LPR
- **Given** hệ thống nhận log của một khu qua adapter được hỗ trợ hoặc từ bộ dữ liệu mô phỏng
- **When** worker xử lý log
- **Then** sự kiện được chuẩn hóa, gắn với khu nguồn và chống trùng theo mã sự kiện; sự kiện có OCR thấp được đưa vào hàng chờ kiểm tra.

**AC-18 (US-18)** — Dự báo khung giờ trống
- **Given** có dữ liệu lịch sử ra/vào của khu
- **When** hệ thống tạo dự báo
- **Then** dự báo theo giờ, thứ và ngày lễ được cung cấp như thông tin tham khảo; hệ thống không tự đăng lịch chia sẻ.
- Độ chính xác mục tiêu và lượng dữ liệu tối thiểu: TBD.
