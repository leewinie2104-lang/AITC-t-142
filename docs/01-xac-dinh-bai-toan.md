# ParkSmart AI: Xác định bài toán

> Tài liệu này làm **trước** khi viết use case. Mục tiêu: thống nhất cả nhóm về bài toán thật sự cần giải, phạm vi, giả định và tiêu chí thành công.
> Các điểm đánh dấu **[GĐ]** là giả định do nhóm tự đặt (đề không cho sẵn), cần chốt và ghi lại. Các điểm đánh dấu **[CHỐT]** là câu hỏi nhóm phải quyết định.

---

## 1. Bài toán trọng tâm

**Một khu dân cư, một hầm gửi xe ôtô, hệ thống tự chỉ định vị trí đỗ cho từng xe, và vận hành gần như không cần người trực.**

Nói gọn: cư dân và khách chat với một AI Agent để đăng ký xe, đặt chỗ và biết mình phải đỗ ở đâu. Hệ thống tự phân biệt xe cư dân với xe lạ khi xe vào hầm. Con người (Ban Quản lý) chỉ xử lý các **ngoại lệ**.

### Phạm vi đã chốt

| Hạng mục | Quyết định |
|---|---|
| Loại phương tiện | **Chỉ ôtô** (không xét xe máy, xe đạp) |
| Quy mô | **Một khu dân cư**, một hầm gửi xe (nhiều tầng/khu) |
| Cách quản lý chỗ | **Chỉ định vị trí đỗ cụ thể** cho từng xe (không để xe tự chọn) |
| Người trực | **Không có bảo vệ ở cửa vào hầm** |
| Nhận diện xe | Dùng **log từ camera nhận diện biển số** (ALPR), không tự làm computer vision |
| Vai trò người dùng | Cư dân, khách, Ban Quản lý (BQL) |

### Ngoài phạm vi (không làm)

- Xe máy, xe đạp, xe điện có sạc riêng (chỉ nhắc như hướng mở rộng).
- Tự xây mô hình nhận diện biển số.
- Phản ánh sự cố toàn khu đô thị, tính tiền điện nước bậc thang, đặt tiện ích khác.
- Thanh toán trực tuyến thật, tích hợp phần cứng barie thật (chỉ mô phỏng).

---

## 2. Vì sao đây là bài toán thật (pain point)

Hầm gửi xe của khu dân cư thường gặp các vấn đề sau:

1. **Giờ cao điểm quá tải.** Cư dân về cùng lúc, hầm đầy, xe loay hoay tìm chỗ, kẹt ở lối dốc.
2. **Không ai biết chỗ trống ở đâu.** Cư dân và khách phải chạy vòng từng tầng để tìm.
3. **Đăng ký thẻ xe rườm rà.** Làm thẻ, thêm xe, đổi xe đều phải lên văn phòng, nộp giấy tờ, chờ duyệt.
4. **Vượt định mức không kiểm soát.** Một căn hộ có nhiều xe hơn quy định, chiếm chỗ của hộ khác.
5. **Xe lạ vào hầm không ai biết.** Khi không có người trực cửa, bất kỳ xe nào theo đuôi xe cư dân đều có thể vào.
6. **BQL quá tải việc lặt vặt.** Đa số yêu cầu là việc lặp lại, có luật rõ ràng, nhưng vẫn phải người xử lý.

**Giá trị cốt lõi hệ thống mang lại:** tự động hóa các việc có luật rõ ràng (bằng code), dùng AI để giao tiếp tự nhiên, và chỉ gọi BQL khi thật sự cần quyết định của con người.

---

## 3. Nguyên tắc thiết kế xuyên suốt

Hệ thống có **ba bên** cùng làm việc. Việc chia ranh giới giữa ba bên là điểm cốt lõi của đề.

| Bên | Làm gì | Không được làm gì |
|---|---|---|
| **AI Agent (LLM)** | Hiểu ngôn ngữ tự do và ảnh, hỏi lại khi thiếu thông tin, gọi tool, diễn đạt kết quả | Tự quyết chỗ trống, tự duyệt ngoại lệ, tự tính toán số liệu |
| **Code xác định** | Kiểm tra định mức, phân bổ vị trí, phát hiện xe lạ, tính toán, ghi dữ liệu | Hiểu câu nói tự do |
| **Con người (BQL)** | Duyệt ngoại lệ, đặt luật, xử lý tranh chấp | Làm các việc lặp lại có luật rõ ràng |

**Quy tắc kiểm tra nhanh cho mỗi tính năng:**
1. Làm sai có hậu quả (quyền lợi, an ninh, tiền)? → để **code** quyết định.
2. Cần hiểu ngôn ngữ hoặc ảnh tự do? → để **agent** làm.
3. Là quyết định ngoại lệ hoặc cần chịu trách nhiệm? → để **con người** làm.

---

## 4. Các bên liên quan

| Bên | Nhu cầu chính |
|---|---|
| **Cư dân** | Đăng ký xe nhanh, biết chỗ đỗ của mình, không phải lên văn phòng |
| **Khách của cư dân** | Vào hầm và biết đỗ ở đâu mà không cần làm thủ tục phức tạp |
| **Ban Quản lý** | Giảm việc lặp lại, kiểm soát định mức, thấy bức tranh sử dụng hầm, được cảnh báo khi có bất thường |
| **Camera ALPR (hệ thống ngoài)** | Cung cấp log biển số vào/ra |

*Lưu ý:* vì không có bảo vệ ở cửa vào, mọi việc trước đây giao cho bảo vệ (xác minh, xử lý xe lạ) giờ phải được **tự động hóa** hoặc **chuyển cho BQL**.

---

## 5. Dữ liệu đầu vào và giả định nền

### 5.1. Nguồn sự kiện xe vào/ra

Nhóm không tự làm nhận diện biển số. Hệ thống **nhận log** từ camera ALPR theo định dạng chuẩn:

```
timestamp, plate, gate_id, direction (IN/OUT), confidence
2026-11-14 18:10:05, 51K-99999, G1, IN, 0.97
```

- Cột `confidence` được giữ lại vì camera thật có thể đọc sai; hệ thống phải xử lý trường hợp độ tin cậy thấp.
- Với đề tài, log là **file mô phỏng** được phát lại (replay) để demo realtime.
- Kiến trúc cần cho phép **thay log bằng camera thật** mà không đổi phần còn lại.

### 5.2. Mức chi tiết của chỗ đỗ

Vì hệ thống **chỉ định vị trí cụ thể**, ta biết mỗi ô đang ở trạng thái nào qua vòng đời:

`Trống → Đã chỉ định/giữ chỗ → Đang có xe (khi log báo xe vào) → Trống (khi log báo xe ra)`

- **[GĐ]** Xe tuân thủ vị trí được chỉ định. Hệ thống **không có cảm biến từng ô** nên không biết xe có đỗ sai ô hay không.
- Hệ quả: độ chính xác của "chỗ trống" dựa trên **chỉ định + log vào/ra**, không phải đo trực tiếp. Cần nêu rõ khi thuyết trình.
- **[CHỐT]** Có tầng/khu nào có camera riêng để xác nhận xe đỗ đúng khu không, hay chỉ có camera ở cổng hầm?

### 5.3. Dữ liệu mô phỏng cần sinh

- Danh sách hộ dân, xe đã đăng ký, định mức.
- Sơ đồ hầm: số tầng, số khu, số ô mỗi khu, tên gọi.
- Log vào/ra theo mẫu giờ cao điểm (sáng đi làm, chiều tối về).
- Các **ca bất thường cài sẵn đáp án** (xe lạ, khách quá hạn, vượt định mức, xe đọc sai biển) để đo chất lượng.

---

## 6. Bốn bài toán thành phần

Quan hệ giữa các bài toán:

```
Bài toán 1 (xe cư dân) ─┐
                        ├─▶ Bài toán 3 (còn chỗ ở đâu) ─▶ chỉ định vị trí
Bài toán 2 (khách) ─────┘                                      │
                                                               ▼
                                             Bài toán 4 (xe vào hầm: nhận diện, phân bổ, cảnh báo)
```

---

### Bài toán 1: Đăng ký và quản lý chỗ đậu xe của cư dân

**Vấn đề cần giải:** cư dân muốn đăng ký xe, thêm xe, đổi xe mà không phải lên văn phòng; BQL muốn kiểm soát định mức mà không phải xử lý từng hồ sơ.

**Cách tiếp cận:**
- Cư dân **chat với chatbot**, agent hỏi thông tin còn thiếu và gọi tool để đăng ký.
- **OCR nhẹ** đọc giấy đăng ký xe (cà vẹt) để trích biển số, chủ xe, loại xe. Chỉ một loại giấy tờ, không mở rộng.
- **Luật định mức:** mỗi hộ được **2 xe đầu** đăng ký tự động. **Từ xe thứ ba** là vượt định mức và **phải do BQL duyệt** (human-in-the-loop).

**Đầu vào → đầu ra:**

| Đầu vào | Đầu ra |
|---|---|
| Tin nhắn cư dân, ảnh giấy tờ xe | Thẻ/biển số được đăng ký, hoặc yêu cầu *Chờ duyệt* gửi BQL |

**Phân vai:**
- Agent: hội thoại, đọc ảnh giấy tờ, giải thích, tóm tắt hồ sơ cho BQL.
- Code: kiểm tra biển số hợp lệ và chưa trùng hộ khác, đếm định mức, tạo yêu cầu duyệt, ghi dữ liệu.
- BQL: duyệt hoặc từ chối xe vượt định mức.

**Ràng buộc từ đề:** HITL cho xe vượt định mức; dữ liệu biển số được bảo mật; chống gian lận đăng ký (trùng biển, giấy tờ giả); cách ly dữ liệu giữa các hộ.

**Tiêu chí thành công:**
- Đăng ký trong định mức hoàn tất không cần người.
- 100% ca vượt định mức đều dừng lại chờ BQL, agent không tự duyệt được.
- Biển số trùng hộ khác bị phát hiện.

**Cần chốt:**
- **[CHỐT]** Định mức 2 xe là cho mỗi căn hộ; có căn lớn được nhiều hơn không?
- **[CHỐT]** Đổi xe (bán xe cũ, mua xe mới) xử lý thế nào? **[GĐ]** Đổi xe không tính thêm định mức.
- **[CHỐT]** Xe cư dân có **chỗ cố định** theo hộ, hay chỗ được hệ thống cấp linh hoạt mỗi lần? (Xem bài toán 4.)
- Mất thẻ/hủy thẻ: **[GĐ]** khóa ngay khi báo mất.

---

### Bài toán 2: Tra cứu và đặt chỗ cho khách

**Vấn đề cần giải:** khách của cư dân không rõ hầm còn chỗ không, đỗ ở đâu; thủ tục cho khách thường phức tạp hoặc không có.

**Cách tiếp cận:**
- Cư dân (hoặc khách) **chat với chatbot** để đăng ký xe khách và **đặt chỗ**.
- Agent gọi tool kiểm tra còn chỗ khu khách, giữ chỗ, và trả lời vị trí được chỉ định.

**Đầu vào → đầu ra:**

| Đầu vào | Đầu ra |
|---|---|
| Biển số khách, thời gian đến và ở lại | Đặt chỗ được xác nhận kèm vị trí và hạn hiệu lực, hoặc bị từ chối kèm lý do |

**Phân vai:**
- Agent: thu thập biển số, giờ đến, thời gian ở; hỏi lại khi thiếu; diễn đạt kết quả.
- Code: kiểm tra giới hạn khách và hạn mức đặt, giữ chỗ, hết hạn tự nhả chỗ.
- Con người: không cần cho ca thông thường.

**Luật nghiệp vụ cần chốt (đề yêu cầu hạn mức đặt phải kiểm tra bằng code):**
- **[GĐ]** Mỗi hộ giữ tối đa **2 xe khách đồng thời**, mỗi lần tối đa **24 giờ**.
- **[GĐ]** Khách đến trễ quá **15 phút** so với giờ đặt thì chỗ được nhả.
- **[CHỐT]** Khách có đăng ký trước mới được vào hầm không? (Liên quan trực tiếp bài toán 4.)
- **[CHỐT]** Ai là người đặt: cư dân đặt cho khách, hay khách tự đặt? **[GĐ]** Chỉ cư dân đặt cho khách, để tránh người lạ tự đăng ký.

**Tiêu chí thành công:**
- Đặt chỗ không bao giờ vượt hạn mức hoặc vượt số chỗ khu khách.
- Chỗ không bị giữ "ảo" quá hạn.

**Lưu ý thiết kế:** bài toán này dễ trở thành "chatbot tra bảng". Giá trị thật của agent là xử lý yêu cầu **tự do có điều kiện** (giờ đến, thời gian ở, loại xe) và đứng giữa cư dân với hệ thống.

---

### Bài toán 3: Hướng dẫn tầng/khu còn trống theo thời gian thực

**Vấn đề cần giải:** không ai biết chỗ trống ở đâu; xe loay hoay tìm chỗ, đặc biệt giờ cao điểm.

**Cách tiếp cận:**
- Agent **gọi tool vào database** để tìm tầng/khu còn chỗ và trả lời cho người dùng.
- Giao diện có **sơ đồ hầm** cập nhật theo thời gian thực.
- Vì hệ thống chỉ định vị trí cụ thể, câu trả lời cuối cùng là "**đỗ ở ô X, tầng Y, khu Z**" chứ không chỉ "còn chỗ".

**Đầu vào → đầu ra:**

| Đầu vào | Đầu ra |
|---|---|
| Câu hỏi hoặc điều kiện (khu gần thang máy, loại xe) | Danh sách tầng/khu còn chỗ, hoặc vị trí được chỉ định |

**Phân vai:**
- Agent: hiểu điều kiện, gọi tool, trình bày kết quả dễ hiểu.
- Code: truy vấn trạng thái ô, cập nhật số chỗ trống khi có sự kiện vào/ra hoặc giữ chỗ/nhả chỗ.

**Phần tùy chọn (optional), làm sau nếu còn thời gian:**
- **Chỉ đường tới ô được chỉ định.** Cần sơ đồ hầm dạng đồ thị; khuyến nghị chỉ làm mức **mô tả bằng chữ** ("xuống B1, rẽ trái, ô thứ 5 dãy C") thay vì thuật toán tìm đường đầy đủ.
- **Dự đoán giờ cao điểm.** Làm bằng thống kê đơn giản (trung bình theo giờ/thứ), kèm một chỉ số sai số (MAE). Không cần mô hình phức tạp.

**Ràng buộc từ đề:** chính xác về tình trạng chỗ trống; hiệu năng thời gian thực.

**Tiêu chí thành công:**
- Số chỗ trống hiển thị khớp với trạng thái thật của hệ thống ở mọi thời điểm.
- Hai xe không bao giờ được chỉ định cùng một ô.
- Sơ đồ cập nhật trong vài giây sau mỗi sự kiện.

**Cần chốt:** xem mục 5.2 về độ chính xác khi không có cảm biến từng ô.

---

### Bài toán 4: Phân biệt xe lạ với xe cư dân, rồi phân bổ vị trí đậu xe

**Đây là bài toán khó nhất và là nơi thể hiện rõ nhất sự kết hợp agent + thuật toán + con người.**

**Vấn đề cần giải:** **không có bảo vệ ở cửa vào**, nên hệ thống phải tự trả lời hai câu hỏi mỗi khi một xe tới cổng:
1. **Xe này là ai?** Cư dân, khách đã đặt chỗ, hay xe lạ?
2. **Nếu hợp lệ, xe đỗ ở đâu?** Và nếu hầm gần đầy, ai được ưu tiên?

**Phần 4a: Phân biệt xe**

Với mỗi sự kiện xe tới, **code** đối chiếu biển số với danh sách xe cư dân và khách còn hạn:

| Kết quả | Hành động đề xuất |
|---|---|
| Xe cư dân hợp lệ | Cho vào, chuyển sang bước phân bổ |
| Khách có đặt chỗ còn hạn | Cho vào, dùng vị trí đã giữ |
| **Xe lạ** (không có trong danh sách) | Không cho vào tự động, ghi nhận, thông báo BQL |
| Độ tin cậy biển thấp | Gắn cờ cần xác nhận, không kết luận ngay |
| Xe đã bị khóa thẻ (mất thẻ) | Không cho vào, cảnh báo |

**Các loại bất thường cần phát hiện:**
- **A. Xe không đăng ký** (xe lạ).
- **B. Khách ở quá hạn** đã đặt.
- **C. Xe lạ ở trong hầm quá lâu**, nhất là qua đêm.
- **D. Hộ vượt định mức** mà chưa được duyệt.
- **E. Xe vào theo đuôi xe khác** (log ghi nhận số xe vào nhiều hơn số lượt mở barie) **[tùy chọn]**.

**Khi không có bảo vệ, ai xử lý xe lạ?**
- Quyết định mở hay không mở barie là việc của **code theo luật**, không phải của agent.
- Cảnh báo xe lạ **gửi BQL** (hoặc nhân viên trực ca của BQL). Agent soạn thông báo dễ hiểu kèm bối cảnh.
- **[CHỐT]** Xe lạ bị chặn hẳn, hay được vào khu tạm với điều kiện (ví dụ yêu cầu cư dân xác nhận)? **[GĐ]** Chặn và thông báo BQL.
- **[CHỐT]** Ai nhận cảnh báo ngoài giờ hành chính, và nếu không ai nhận thì sao?

**Phần 4b: Phân bổ vị trí đậu xe**

Với xe hợp lệ, hệ thống **chỉ định một ô cụ thể**. Khi nhiều xe cùng cần và chỗ không đủ (giờ cao điểm), cần **thuật toán phân bổ công bằng**:

- **[GĐ]** Thứ tự ưu tiên: nhóm ưu tiên đặc biệt (khuyết tật, cao tuổi) → hộ chưa có chỗ cố định → thời điểm yêu cầu.
- Kết quả phải **giải thích được** ("vì sao xe A được chỗ này còn xe B thì chưa") và **lặp lại được** (cùng đầu vào cho cùng kết quả).
- **[CHỐT]** Chỗ cố định theo hộ hay chỗ linh hoạt? Nếu cố định, thuật toán chỉ áp dụng cho khách và hộ chưa có chỗ. Nếu linh hoạt, thuật toán áp dụng cho tất cả.
- **[GĐ]** Chọn ô theo tiêu chí đơn giản: gần thang máy/lối ra của tòa hộ đó nhất còn trống.

**Phân vai:**
- Agent: giải thích cho cư dân vì sao được/không được chỗ nào, soạn thông báo cho BQL.
- Code: đối chiếu biển số, phát hiện bất thường, chạy thuật toán phân bổ, quyết định mở/không mở barie.
- BQL: đặt luật ưu tiên từ trước, xử lý cảnh báo xe lạ, xử lý ca ngoại lệ.

**Ràng buộc từ đề:** bảo mật biển số và dữ liệu ra vào; chống gian lận; phát hiện xe lạ và vượt định mức; cách ly dữ liệu giữa các hộ.

**Tiêu chí thành công:**
- Phát hiện xe lạ đúng trên bộ dữ liệu mô phỏng có đáp án, đo tỷ lệ bỏ sót và tỷ lệ báo nhầm.
- Không xe nào được chỉ định ô đã có người.
- Cảnh báo không bị lặp (một xe chỉ có một cảnh báo đang mở).
- Cư dân chỉ thấy dữ liệu hộ mình.

---

## 7. Ràng buộc chung từ đề bài

| Ràng buộc | Ý nghĩa với hệ thống |
|---|---|
| **HITL** cho đăng ký vượt định mức | Quy trình phải **dừng lại chờ BQL**, agent không tự duyệt |
| **Bảo mật biển số và dữ liệu ra vào** | Chỉ BQL xem được dữ liệu ra vào toàn bộ; cư dân chỉ xem dữ liệu của mình |
| **Tenant isolation** (cách ly giữa các hộ) | Danh tính lấy từ token đăng nhập, **không** lấy từ nội dung chat; chặn ở tầng database |
| **Chính xác tình trạng chỗ trống** | Mọi số liệu đến từ tool/database, agent không tự suy ra |
| **Thời gian thực** | Sơ đồ và số chỗ cập nhật ngay khi có sự kiện |
| **Chống gian lận đăng ký** | Phát hiện trùng biển, giấy tờ không khớp |
| **Tính toán bằng code xác định** | Định mức, hạn mức đặt, phân bổ chỗ đều do code, kiểm thử được |

---

## 8. Cách đánh giá thành công của cả hệ thống

| Chỉ số | Cách đo |
|---|---|
| Agent hiểu đúng ý người dùng | Bộ câu hỏi mẫu có đáp án, đo % trả lời/hành động đúng |
| Không rò rỉ dữ liệu giữa các hộ | Bộ test cố tình hỏi dữ liệu hộ khác; kết quả phải bằng 0 lần lộ |
| Agent không tự duyệt ngoại lệ | Test thuyết phục agent duyệt xe thứ 3; kết quả phải luôn bị chặn |
| Phát hiện xe lạ | Tỷ lệ phát hiện đúng và báo nhầm trên log mô phỏng có đáp án |
| Phân bổ chỗ đúng | Không trùng ô; kết quả lặp lại được; giải thích được |
| Giảm tải cho BQL | Tỷ lệ yêu cầu được xử lý tự động hoàn toàn so với tổng yêu cầu |
| Dự báo cao điểm (nếu làm) | Sai số MAE so với dữ liệu mô phỏng |

---

## 9. Thứ tự ưu tiên khi làm

**Tầng 1 (lõi, bắt buộc):**
- Đăng nhập, phân quyền, cách ly dữ liệu giữa các hộ.
- Bài toán 1: đăng ký xe trong định mức.
- Bài toán 3: sơ đồ hầm và chỉ định vị trí cơ bản.
- Bài toán 2: đặt chỗ cho khách.
- Triển khai được lên môi trường chạy thật.

**Tầng 2 (điểm nhấn nâng cao):**
- HITL cho xe vượt định mức (bài toán 1).
- Phân biệt xe lạ và cảnh báo BQL (bài toán 4a).
- Thuật toán phân bổ công bằng giờ cao điểm (bài toán 4b).
- Dashboard sử dụng hầm cho BQL.

**Tầng 3 (nếu còn thời gian, làm nông):**
- Dự báo giờ cao điểm bằng thống kê.
- Chỉ đường bằng văn bản tới ô được chỉ định.
- Phát hiện xe đi theo đuôi (E).

---

## 10. Rủi ro và điểm cần lưu ý

- **Không có cảm biến từng ô:** độ chính xác "chỗ trống" dựa vào chỉ định và log vào/ra; xe đỗ sai ô sẽ không bị phát hiện. Cần nêu rõ là giả định.
- **Camera đọc sai biển số:** phải có đường xử lý cho độ tin cậy thấp, tránh chặn nhầm cư dân.
- **Không có bảo vệ:** mọi ca mơ hồ dồn về BQL; cần tránh để BQL bị "spam" cảnh báo giả. Chống lặp và ngưỡng độ tin cậy là bắt buộc.
- **Bài toán 2 dễ mỏng:** nếu không có luật đặt chỗ rõ, dễ bị đánh giá là chatbot tra cứu. Cần viết luật hạn mức đặt cụ thể.
- **Phạm vi rộng so với thời gian:** bám tầng ưu tiên ở mục 9, không làm sâu mọi thứ.

---

## 11. Danh sách câu hỏi cần nhóm chốt

1. Xe cư dân có **chỗ cố định** theo hộ hay **chỗ linh hoạt**?
2. Xe lạ bị **chặn hẳn** hay được vào khu tạm có điều kiện?
3. Cảnh báo xe lạ gửi **ai** và **qua kênh nào** (app, thông báo, email)? Ngoài giờ hành chính thì sao?
4. Khách có **bắt buộc đăng ký trước** mới được vào không? Ai được đặt cho khách?
5. Định mức 2 xe tính cho **mỗi căn hộ**; có ngoại lệ căn lớn không?
6. Có camera ở **từng tầng/khu** hay chỉ ở cổng hầm? (Quyết định độ chính xác trạng thái chỗ trống.)
7. Các **ngưỡng thời gian**: giữ chỗ khách (15 phút?), khách ở tối đa (24 giờ?), xe lạ ở bao lâu thì cảnh báo mức cao, hạn BQL duyệt (48 giờ?).
8. **Nhóm ưu tiên** gồm những ai?
9. Quy mô mô phỏng: bao nhiêu hộ, bao nhiêu tầng, bao nhiêu ô?

---

## 12. Bước tiếp theo

Sau khi chốt các câu hỏi ở mục 11, viết **use case chi tiết** cho từng bài toán. Lưu ý use case đã soạn trước đó cần **cập nhật** theo các thay đổi sau:
- Bỏ vai trò **bảo vệ**; chuyển việc xử lý cảnh báo sang **BQL**.
- Bổ sung vai trò **barie tự động** (quyết định mở/không mở theo kết quả đối chiếu biển số).
- Làm rõ chỉ định **ô cụ thể** thay vì chỉ trạng thái theo khu/tầng.
- Bỏ phần xe máy; chỉ giữ ôtô có thể xe máy.