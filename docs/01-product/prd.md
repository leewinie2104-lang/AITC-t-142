# PRD — Agent điều phối quyền sử dụng chỗ đỗ trong chuỗi khu đô thị

> Nguồn: [01-xac-dinh-bai-toan.md](../01-xac-dinh-bai-toan.md)
> Bối cảnh và vấn đề: [Project Brief](project-brief.md) · Phạm vi và giả định: [Scope](scope.md)

> Phạm vi bản demo và các tích hợp bị hoãn: xem [Scope §1–3](scope.md#1-trong-phạm-vi-bản-demo).

## 1. Mục tiêu sản phẩm

- Tăng mức khai thác chỗ đỗ đang bỏ trống trong hầm các tòa nhà, **trên toàn chuỗi khu đô thị**.
- Cho phép chia sẻ chỗ an toàn, đúng tư cách và đúng phạm vi, có bằng chứng.
- Phục vụ nhu cầu đỗ xe giữa các khu.
- Giảm số tranh chấp và rút ngắn thời gian xử lý cho BQL.

Chi tiết vấn đề: [Project Brief §2](project-brief.md#2-vấn-đề).

## 2. Mô hình tổ chức

```
Chuỗi (1)
 └─ Khu đô thị (N ≥ 2)          BQL khu, đơn vị trông giữ xe của khu
     └─ Phân khu
         ├─ Tòa chung cư hỗn hợp     Ban quản trị, Hội nghị nhà chung cư của tòa
         │   ├─ Căn hộ
         │   └─ Khối đế: shophouse, văn phòng, phòng khám, mầm non
         ├─ Cụm shophouse thấp tầng
         └─ Bãi công cộng
```

| Cấp | Vai trò quản lý | Thẩm quyền liên quan đến chỗ đỗ |
|-----|-----------------|----------------------------------|
| Chuỗi | Đơn vị vận hành chuỗi (chủ đầu tư) | Cấu hình chung; đồng ý mở pool TH2; bảng giá khung; báo cáo toàn chuỗi. |
| Khu | BQL khu | Khai thác TH3; xác minh tư cách của tài sản trong khu; duyệt HITL (tranh chấp, hoán đổi, giao dịch vượt ngưỡng). |
| Tòa | Ban quản trị, Hội nghị nhà chung cư | Nội quy tòa, gồm cả **phạm vi mở của TH1**. |
| Khu | Đơn vị trông giữ xe | Cung cấp dữ liệu cổng và log LPR. |

Số khu, phân khu và tòa là **dữ liệu cấu hình**, không được viết cứng trong code. Thêm khu mới không đòi hỏi thay đổi logic.

## 3. Đối tượng người dùng và tư cách

### 3.1 Tài khoản và tư cách

- Mỗi người dùng có **một tài khoản cho cả chuỗi** (xác minh danh tính một lần).
- Một tài khoản có thể giữ **nhiều tư cách**. Mỗi tư cách gồm: *(tài sản, vai trò, hạn hiệu lực)*.
  - **Tài sản**: căn hộ, shophouse, văn phòng, chỗ đỗ…
  - **Vai trò**: chủ sở hữu, người thuê, người được ủy quyền, nhân viên.
- Tư cách **gắn với tài sản**, không gắn với con người. Bán tài sản, hết hợp đồng thuê, hoặc đơn vị rút quyền nhân viên thì tư cách đó hết hiệu lực.
- BQL của khu nơi có tài sản xác minh tư cách đó.

### 3.2 Cấp tư cách tại vị trí chỗ đỗ

Khi có yêu cầu thuê chỗ ở tòa *T* thuộc khu *K*, Agent lấy **cấp cao nhất** mà người yêu cầu đạt được **tại vị trí đó**:

| Cấp | Điều kiện | Ví dụ |
|-----|-----------|-------|
| **L1 — Thành viên tòa** | Có tư cách còn hiệu lực gắn với tài sản trong tòa *T* | Cư dân căn hộ ở *T*; chủ hoặc nhân viên shophouse khối đế của *T* |
| **L2 — Thành viên khu** | Có tư cách gắn với tài sản khác trong khu *K* | Cư dân tòa khác cùng khu; chủ shophouse thấp tầng ở *K* |
| **L3 — Thành viên chuỗi** | Có tư cách ở một khu khác trong chuỗi | Cư dân khu B sang khu A |
| **L4 — Khách** | Không có tư cách nào còn hiệu lực | Khách vãng lai, khách của shophouse |

Ví dụ một người là chủ shophouse thấp tầng ở khu A và có căn hộ ở khu B:
- Tại tòa ở khu A: **L2**.
- Tại tòa căn hộ của họ ở khu B: **L1**.
- Tại khu C: **L3**.

Quyền chỉ dành cho chủ căn hộ (biểu quyết nội quy, cho khách đỗ miễn phí) **không** chuyển sang khu khác.

### 3.3 Nhóm người dùng

| Nhóm | Thành phần | Quyền liên quan đến chỗ đỗ |
|------|-----------|----------------------------|
| **Bên cung cấp chỗ** | Cư dân có chỗ TH1, TH2; văn phòng có chỗ riêng; chủ đầu tư (pool TH2) | Chia sẻ chỗ của mình trong phạm vi mở (§4) |
| **Bên cần chỗ** | Bất kỳ ai. Quyền được xác định theo cấp L1–L4 tại vị trí chỗ đỗ và theo loại tư cách | Được ghép vào TH1/TH2 nếu đạt phạm vi mở; nếu không thì dùng TH3 / bãi công cộng |
| **Bên quản lý và phê duyệt** | Đơn vị vận hành chuỗi; BQL khu; Ban quản trị; Hội nghị nhà chung cư; đơn vị trông giữ xe | Cấu hình, xác minh, phê duyệt. Trong demo, **BQL của khu có chỗ đỗ** là vai trò duyệt HITL |

## 4. Phân loại chỗ đỗ và phạm vi mở

**Phạm vi mở** là cấp tư cách thấp nhất được phép thuê một ô:
- **Tòa** = chỉ L1
- **Khu** = L1–L2
- **Chuỗi** = L1–L3
- **Công cộng** = mọi cấp

| Loại | Mô tả | Quy tắc cho thuê | Phạm vi mở mặc định | Mở rộng tối đa |
|------|-------|------------------|---------------------|----------------|
| **TH1** | Chỗ cư dân đã mua | Chủ chỗ được cho thuê | **Tòa** | **Khu**, nếu nội quy tòa cho phép *(giả định A-08)* |
| **TH2** | Chỗ thuê từ chủ đầu tư | Được cho thuê lại khi chủ đầu tư đồng ý; **đồng ý một lần cho cả pool** | **Khu** | **Chuỗi**, nếu đơn vị vận hành chuỗi cấu hình |
| **TH3** | Chỗ công cộng hoặc chỗ khách | Do **BQL khu khai thác**; **cá nhân không được cho thuê** | **Công cộng** | — (giá khác nhau theo cấp tư cách) |

Chủ chỗ có thể **thu hẹp** phạm vi khi chia sẻ (ví dụ chỉ cho người cùng tòa thuê), nhưng **không được mở rộng** quá mức mà nội quy cho phép.

## 5. Quy tắc nghiệp vụ

| ID | Quy tắc |
|----|---------|
| BR-01 | Chỗ TH1 chỉ được cho thuê cho người có cấp tư cách nằm trong phạm vi mở của ô. Mặc định là thành viên tòa (L1). |
| BR-02 | Chỗ TH2 được cho thuê lại. Chủ đầu tư đã chấp thuận chia sẻ toàn bộ pool TH2; phạm vi mở do đơn vị vận hành chuỗi cấu hình. |
| BR-03 | Chỗ TH3 do BQL khu khai thác; cá nhân không được cho thuê. |
| BR-04 | Việc chia sẻ chỉ diễn ra **trong phạm vi mở của ô**, qua **nền tảng chính thức**, có **khung giá** và **mẫu thỏa thuận** (theo nội quy của tòa và của khu). |
| BR-05 | Cư dân chỉ được cho khách của chính mình đỗ khi **không thu phí**. Quyền này chỉ áp dụng tại tòa nơi cư dân là L1. |
| BR-06 | Khách của shophouse được chuyển sang TH3 của khu có shophouse. |
| BR-07 | Chủ chỗ được **bảo đảm quyền quay về** chỗ của mình. |
| BR-08 | Phí đỗ quá giờ tính **theo nội quy** của khu có chỗ đỗ (mức phí: TBD). |
| BR-09 | Việc xử lý biển số và ảnh dựa trên sự đồng ý của người dùng khi đăng ký app. Biển số trong ticket tranh chấp phải được ẩn. |
| BR-10 | Hoán đổi chỗ chỉ diễn ra **trong cùng một khu** và phải được **BQL khu phê duyệt**. |
| BR-11 | Chỉ ghép xe vào ô có kích thước phù hợp. Việc ghép xét khung giờ, khoảng dự phòng và quyền ưu tiên đã cấu hình. |
| BR-12 | Giao dịch vượt ngưỡng định mức (cấu hình theo khu) phải chờ BQL khu duyệt trước khi có hiệu lực. |
| BR-13 | Log LPR trùng mã sự kiện không được xử lý hai lần. Sự kiện OCR có độ tin cậy thấp phải được đánh dấu để người kiểm tra. |
| BR-14 | Trước khi gửi dữ liệu tới LLM, biển số và tên phải được thay bằng mã giả. LLM không đưa ra quyết định thay rule engine hoặc người duyệt. |
| BR-15 | Cấp tư cách được xác định **tại vị trí của ô đỗ** và lấy cấp cao nhất trong các tư cách còn hiệu lực. Tư cách ở khu khác chỉ được tính là L3. |
| BR-16 | Tư cách hết hạn thì mọi giao dịch **mới** dựa trên tư cách đó bị chặn. Giao dịch đang hiệu lực được giữ tới hết kỳ hiện tại (kỳ tối đa: TBD). |
| BR-17 | Giữa các khu chỉ trao đổi **kết quả xác nhận tư cách** (cấp tư cách và hạn hiệu lực). Hồ sơ cư dân, số căn hộ và giấy tờ không rời khỏi BQL của khu sở hữu dữ liệu. |
| BR-18 | Tranh chấp do **BQL của khu có ô đỗ** xử lý, kể cả khi một bên là thành viên khu khác. |
| BR-19 | Giá thuê áp dụng theo **cấp tư cách** tại vị trí ô đỗ (xem §8). |

## 6. Yêu cầu chức năng

### 6.1 Tư cách và liên khu
| ID | Yêu cầu |
|----|---------|
| FR-23 | Quản lý một tài khoản cho cả chuỗi, có nhiều tư cách *(tài sản, vai trò, hạn hiệu lực)* do BQL khu xác minh. |
| FR-24 | Tính cấp tư cách L1–L4 của người yêu cầu tại vị trí của ô đỗ (BR-15). |
| FR-25 | Tự động vô hiệu tư cách khi hết hạn; chặn giao dịch mới; thông báo cho người dùng và cho chủ chỗ có giao dịch liên quan (BR-16). |
| FR-26 | Cho phép đơn vị vận hành chuỗi và BQL cấu hình phạm vi mở của từng pool; cho phép chủ chỗ thu hẹp phạm vi khi chia sẻ (§4). |
| FR-27 | Khi một khu hết chỗ phù hợp, gợi ý chỗ ở các khu khác trong chuỗi mà người yêu cầu đủ điều kiện (chỉ gợi ý, không tự đặt). |

### 6.2 Định tuyến
| ID | Yêu cầu |
|----|---------|
| FR-01 | Kiểm tra người yêu cầu có đủ điều kiện thuê chỗ riêng hay không, dựa trên cấp tư cách (FR-24) và phạm vi mở của pool. |
| FR-02 | Nếu đủ điều kiện → ghép vào chỗ TH1 hoặc TH2 (tuân thủ BR-01, BR-02). |
| FR-03 | Nếu không đủ điều kiện → chuyển sang TH3 hoặc bãi công cộng của khu đó, áp dụng giá theo cấp tư cách. |
| FR-04 | Chặn giao dịch sai tư cách hoặc sai phạm vi (vi phạm BR-01, BR-03, BR-04, BR-05, BR-16). |

### 6.3 Chia sẻ
| ID | Yêu cầu |
|----|---------|
| FR-05 | Đề xuất khung giờ mà chỗ có thể chia sẻ. |
| FR-06 | Giữ một khoảng dự phòng khi chia sẻ (độ dài: TBD). |
| FR-07 | Ghép cung với cầu theo khung giờ, kích thước ô/xe, khoảng dự phòng, quyền ưu tiên và phạm vi mở. |
| FR-08 | Tự sinh thỏa thuận điện tử theo mẫu của khu có ô đỗ để hai bên xác nhận. |
| FR-09 | Ghi giao dịch đã xác nhận vào sổ cái; BQL khu ghi nhận. |
| FR-09a | Nếu giao dịch vượt ngưỡng định mức của khu, chờ BQL khu duyệt trước khi có hiệu lực. |

### 6.4 Xử lý ngoại lệ
| ID | Yêu cầu |
|----|---------|
| FR-10 | Khi chủ chỗ về sớm → điều phối chỗ thay thế cho người thuê từ pool TH3 của cùng khu; nếu hết chỗ thì gợi ý theo FR-27. |
| FR-11 | Khi người thuê đỗ quá giờ → nhắc người thuê. |
| FR-12 | Khi người thuê đỗ quá giờ → tính phí theo nội quy (BR-08). |

### 6.5 Tranh chấp
| ID | Yêu cầu |
|----|---------|
| FR-13 | Đọc ảnh liên quan đến tranh chấp. |
| FR-14 | Đối chiếu với sổ cái và dữ liệu cổng của khu. |
| FR-15 | Lập ticket với biển số đã được ẩn. |
| FR-16 | Chuyển ticket cho BQL của khu có ô đỗ xác minh (BR-18). |
| FR-16a | Chuẩn hóa log LPR; chống xử lý trùng theo mã sự kiện; so khớp mờ biển số đọc sai; đánh dấu kết quả OCR có độ tin cậy thấp để kiểm tra thủ công. |

### 6.6 Hoán đổi
| ID | Yêu cầu |
|----|---------|
| FR-17 | Từ tranh chấp lặp lại hoặc nhu cầu đã đăng ký, đề xuất hoán đổi giữa 2 bên hoặc theo chuỗi, **trong cùng một khu**. |
| FR-18 | Hoán đổi chỉ có hiệu lực sau khi BQL khu phê duyệt. |

### 6.7 Tác vụ nền và tiện ích demo
| ID | Yêu cầu |
|----|---------|
| FR-19 | Nhận log LPR của từng khu qua adapter webhook, MQTT, DB hoặc CSV. Bản demo cung cấp bộ log mô phỏng theo ngày thường, cuối tuần và lễ Tết. |
| FR-20 | Dự báo khung giờ trống theo khu, từ lịch sử ra/vào theo giờ, thứ và ngày lễ. Dự báo chỉ hiển thị như gợi ý, không tự tạo lịch chia sẻ. |
| FR-21 | Tính phí chia sẻ và phí quá giờ theo cấu hình nội quy. Bản demo hỗ trợ trạng thái VietQR mock. |
| FR-22 | Tạo voucher shophouse cho lượt đỗ TH3. Voucher không làm thay đổi cấp tư cách hoặc quyền dùng TH1/TH2. |

## 7. Hình thức hợp đồng

| Giao dịch | Hình thức | Ai lập |
|-----------|-----------|--------|
| Khách theo lượt | Vé hoặc biên lai điện tử | BQL khu |
| Vé tháng | Hợp đồng ký một lần | BQL khu |
| Người dùng chia sẻ cho nhau (cùng khu hoặc liên khu) | Thỏa thuận điện tử theo mẫu của khu có ô đỗ | Agent sinh, hai bên xác nhận, BQL khu ghi nhận |

Trong bản demo, vé lượt và vé tháng do BQL quản lý không phải là luồng sản phẩm độc lập. Thanh toán chia sẻ dùng VietQR mock; voucher shophouse áp dụng cho lượt đỗ TH3. MoMo, ZaloPay và thanh toán tiền thật để giai đoạn sau. Chi tiết ranh giới: [Scope §1–2](scope.md#1-trong-phạm-vi-bản-demo).

## 8. Mô hình giá (giả định từ nguồn)

| Hạng mục | Giá trị |
|----------|---------|
| Thu nhập của chủ chỗ | ~1 triệu/tháng *(giả định)*, bù 30–70% phí gửi xe |
| Giá thuê chỗ chia sẻ cho L1–L2 | ~50k/ngày |
| Giá thuê chỗ chia sẻ cho L3 (liên khu) | TBD (dự kiến cao hơn L1–L2, thấp hơn giá khách) |
| Giá TH3 theo cấp (thành viên / khách) | TBD, do BQL khu quy định |
| Giá gửi xe bên ngoài (tham chiếu) | 20–70k/giờ |
| Khung giá chính thức theo nội quy | TBD |
| Phí dịch vụ cho BQL khu / đơn vị vận hành chuỗi | TBD |

## 9. Yêu cầu phi chức năng

- **Phân quyền:** dữ liệu được phân tách theo khu và theo hộ. BQL chỉ thấy dữ liệu khu mình. Các vai trò cư dân, người thuê, bảo vệ và BQL chỉ truy cập dữ liệu phù hợp. Đơn vị vận hành chuỗi chỉ thấy số liệu tổng hợp.
- **Riêng tư:** mã hóa biển số khi lưu. Chỉ BQL của khu liên quan được xem bản gốc và mọi lần truy cập đều được ghi log. Ticket hiển thị biển số đã ẩn. Tên và biển số được ẩn danh trước khi gọi LLM. Giữa các khu chỉ trao đổi kết quả xác nhận tư cách (BR-17).
- **Tính toàn vẹn:** sổ cái chỉ ghi thêm (append-only); mỗi bản ghi liên kết hash với bản ghi trước để phát hiện sửa đổi.
- **Độ tin cậy nghiệp vụ:** quyết định về tư cách, quyền thuê và tính phí do rule engine tất định đưa ra. Giao dịch vượt định mức, tranh chấp và hoán đổi có bước BQL duyệt.
- **Mở rộng:** thêm khu, phân khu, tòa hoặc pool chỉ bằng cấu hình và dữ liệu, không sửa code.
- **LPR:** chống trùng sự kiện. Dữ liệu OCR không chắc chắn được đưa vào hàng chờ kiểm tra, không dùng để tự kết luận tranh chấp.
- **Lưu trữ và vận hành:** thời hạn lưu log và ảnh, mục tiêu hiệu năng, độ sẵn sàng và quy trình xóa dữ liệu: TBD trước khi dùng thật.
- **Tuân thủ:** cần xác nhận yêu cầu pháp lý và quy định về chuyển dữ liệu xuyên biên giới trước khi kết nối dịch vụ AI với dữ liệu thật.

## 10. Chỉ số thành công

Xem [Project Brief §7](project-brief.md#7-chỉ-số-thành-công-kpi).
