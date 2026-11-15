# PRD — Agent điều phối quyền sử dụng chỗ đỗ

> Nguồn: [01-xac-dinh-bai-toan.md](../01-xac-dinh-bai-toan.md)
> Bối cảnh & vấn đề: [Project Brief](project-brief.md) · Phạm vi & giả định: [Scope](scope.md)

## 1. Mục tiêu sản phẩm

Tăng khai thác chỗ đỗ đang bỏ trống trong hầm các tòa nhà bằng cách cho phép chia sẻ an toàn, đúng đối tượng, có bằng chứng — đồng thời giảm và rút ngắn xử lý tranh chấp cho BQL. (Chi tiết vấn đề: [Project Brief §2](project-brief.md#2-vấn-đề).)

## 2. Đối tượng người dùng

| Nhóm | Thành phần | Quyền liên quan chỗ đỗ |
|------|-----------|------------------------|
| **Bên cung cấp chỗ** | Cư dân có chỗ TH1, TH2; văn phòng có chỗ riêng | Chia sẻ chỗ của mình |
| **Bên cần chỗ — được thuê chỗ riêng** | Cư dân không có chỗ; người thuê căn hộ; hộ có xe thứ hai; chủ shophouse và nhân viên; văn phòng; phòng khám; trường mầm non ở tầng đế | Được ghép vào TH1 / TH2 |
| **Bên cần chỗ — chỉ dùng TH3 / bãi công cộng** | Khách vãng lai; khách của shophouse; phụ huynh; người nhà bệnh nhân; nhân viên ở tòa văn phòng độc lập | Chỉ TH3 hoặc bãi công cộng |
| **Bên quản lý & phê duyệt** | Chủ đầu tư; BQL; Ban quản trị; Hội nghị nhà chung cư; đơn vị trông giữ xe | Phê duyệt, ghi nhận, xác minh (phân quyền chi tiết: TBD) |

## 3. Phân loại chỗ đỗ

| Loại | Mô tả | Quy tắc cho thuê |
|------|-------|------------------|
| **TH1** | Chỗ cư dân đã mua | Được cho thuê, **chỉ cho cư dân hoặc người sử dụng tòa nhà**. |
| **TH2** | Chỗ thuê từ chủ đầu tư | Được cho thuê lại khi chủ đầu tư đồng ý; **chỉ cần đồng ý một lần cho cả pool**. |
| **TH3** | Chỗ công cộng hoặc chỗ khách | Do **BQL khai thác**; **cá nhân không được cho thuê**. |

## 4. Quy tắc nghiệp vụ

| ID | Quy tắc |
|----|---------|
| BR-01 | Chỗ TH1 chỉ cho thuê cho cư dân hoặc người sử dụng tòa nhà. |
| BR-02 | Chỗ TH2 được cho thuê lại; chủ đầu tư đã chấp thuận chia sẻ toàn bộ chỗ TH2. |
| BR-03 | Chỗ TH3 do BQL khai thác; cá nhân không được cho thuê. |
| BR-04 | Chia sẻ chỉ trong **nội bộ tòa nhà**, qua **nền tảng chính thức**, có **khung giá** và **mẫu thỏa thuận** (theo nội quy Hội nghị nhà chung cư). |
| BR-05 | Cư dân chỉ được cho khách của chính mình đỗ khi **không thu phí**. |
| BR-06 | Khách của shophouse được chuyển sang TH3. |
| BR-07 | Chủ chỗ được **bảo đảm quyền quay về** chỗ của mình. |
| BR-08 | Phí đỗ quá giờ tính **theo nội quy** (mức phí: TBD). |
| BR-09 | Xử lý biển số và ảnh dựa trên sự đồng ý của cư dân khi đăng ký app; biển số trong ticket tranh chấp phải được ẩn. |
| BR-10 | Hoán đổi chỗ phải được **BQL phê duyệt**. |

## 5. Yêu cầu chức năng

### 5.1 Định tuyến
| ID | Yêu cầu |
|----|---------|
| FR-01 | Kiểm tra người yêu cầu có đủ điều kiện thuê chỗ riêng hay không (theo nhóm đối tượng §2). |
| FR-02 | Nếu đủ điều kiện → ghép vào chỗ TH1 hoặc TH2 (tuân thủ BR-01, BR-02). |
| FR-03 | Nếu không đủ điều kiện → chuyển sang TH3 hoặc bãi công cộng. |
| FR-04 | Chặn giao dịch sai đối tượng (vi phạm BR-01, BR-03, BR-04, BR-05). |

### 5.2 Chia sẻ
| ID | Yêu cầu |
|----|---------|
| FR-05 | Đề xuất khung giờ chỗ có thể chia sẻ. |
| FR-06 | Giữ một khoảng dự phòng khi chia sẻ (độ dài: TBD). |
| FR-07 | Ghép cung với cầu. |
| FR-08 | Tự sinh thỏa thuận điện tử theo mẫu để hai bên xác nhận. |
| FR-09 | Ghi giao dịch đã xác nhận vào sổ cái; BQL ghi nhận. |

### 5.3 Xử lý ngoại lệ
| ID | Yêu cầu |
|----|---------|
| FR-10 | Khi chủ chỗ về sớm → điều phối chỗ thay thế cho người thuê từ pool TH3. |
| FR-11 | Khi người thuê đỗ quá giờ → nhắc người thuê. |
| FR-12 | Khi người thuê đỗ quá giờ → tính phí theo nội quy (BR-08). |

### 5.4 Tranh chấp
| ID | Yêu cầu |
|----|---------|
| FR-13 | Đọc ảnh liên quan đến tranh chấp. |
| FR-14 | Đối chiếu với sổ cái và dữ liệu cổng. |
| FR-15 | Lập ticket với biển số đã được ẩn. |
| FR-16 | Chuyển ticket cho BQL xác minh. |

### 5.5 Hoán đổi
| ID | Yêu cầu |
|----|---------|
| FR-17 | Từ tranh chấp lặp lại hoặc nhu cầu đã đăng ký, đề xuất hoán đổi giữa 2 bên hoặc theo chuỗi. |
| FR-18 | Hoán đổi chỉ có hiệu lực sau khi BQL phê duyệt. |

## 6. Hình thức hợp đồng

| Giao dịch | Hình thức | Ai lập |
|-----------|-----------|--------|
| Khách theo lượt | Vé hoặc biên lai điện tử | BQL |
| Vé tháng | Hợp đồng ký một lần | BQL |
| Cư dân chia sẻ cho nhau | Thỏa thuận điện tử theo mẫu | Agent sinh, hai bên xác nhận, BQL ghi nhận |

> Vai trò của Agent trong giao dịch "khách theo lượt" và "vé tháng": TBD.

## 7. Mô hình giá (giả định từ nguồn)

| Hạng mục | Giá trị |
|----------|---------|
| Thu nhập chủ chỗ | ~1 triệu/tháng *(giả định)*, bù 60–70% phí gửi xe |
| Giá thuê chỗ chia sẻ | ~50k/ngày |
| Giá gửi xe bên ngoài (tham chiếu) | 20–70k/giờ |
| Khung giá chính thức theo nội quy | TBD |
| Phí dịch vụ cho BQL/chủ đầu tư | TBD |

## 8. Yêu cầu phi chức năng

TBD — tài liệu nguồn chưa nêu (hiệu năng, độ sẵn sàng, bảo mật, lưu trữ dữ liệu ảnh/biển số, kênh truy cập ngoài "app").

## 9. Chỉ số thành công

Xem [Project Brief §6](project-brief.md#6-chỉ-số-thành-công-kpi).
