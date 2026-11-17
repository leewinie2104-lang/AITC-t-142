# User Flow — Agent điều phối quyền sử dụng chỗ đỗ trong chuỗi khu đô thị

> Nguồn: [01-xac-dinh-bai-toan.md](../../01-xac-dinh-bai-toan.md)
> Liên quan: [User Stories](../user-stories.md) · [Acceptance Criteria](../acceptance-criteria.md) · [PRD](../prd.md)
> Wireframes: [wireframes/index.html](wireframes/index.html) (chưa cập nhật cho bối cảnh nhiều khu) · UI design: [ui-design/](ui-design/) (chưa có)

Các luồng dưới đây thể hiện nghiệp vụ của bản demo (1 chuỗi, N khu). Agent điều phối các nhánh nghiệp vụ. Worker nền xử lý: nạp log LPR, nhắc quá giờ, đối soát cuối ngày, dự báo và quét tư cách hết hạn. Màn hình và thao tác UI cụ thể: TBD.

## Flow 0 — Xác định tư cách tại vị trí chỗ đỗ (US-19 → US-22)

```mermaid
flowchart TD
    A[Yêu cầu chỗ đỗ tại tòa T, khu K] --> B[Lấy các tư cách còn hiệu lực<br/>của tài khoản trong chuỗi]
    B --> C{Có tư cách gắn<br/>với tài sản trong T?}
    C -- Có --> L1[L1 — Thành viên tòa]
    C -- Không --> D{Có tư cách gắn với<br/>tài sản khác trong K?}
    D -- Có --> L2[L2 — Thành viên khu]
    D -- Không --> E{Có tư cách ở<br/>khu khác trong chuỗi?}
    E -- Có --> L3[L3 — Thành viên chuỗi<br/>chỉ nhận kết quả xác nhận từ khu kia]
    E -- Không --> L4[L4 — Khách]
    L1 --> F[Tiếp tục Flow 1]
    L2 --> F
    L3 --> F
    L4 --> F
```

## Flow 1 — Định tuyến yêu cầu chỗ đỗ (US-01 → US-03, US-25)

```mermaid
flowchart TD
    A[Cấp tư cách từ Flow 0] --> B{Có pool TH1/TH2 trong K<br/>có phạm vi mở chứa cấp này?}
    B -- Có --> C[Ghép vào TH1 hoặc TH2]
    B -- Không --> D[Chuyển sang TH3 / bãi công cộng của K<br/>với giá theo cấp]
    C --> E{Đúng tư cách, đúng phạm vi<br/>và ô vừa kích thước xe?}
    E -- Sai tư cách / phạm vi --> F[Chặn giao dịch]
    E -- Có --> G[Tiếp tục Flow 2]
    E -- Không có ô phù hợp --> X[Gợi ý chỗ ở khu khác trong chuỗi<br/>người dùng tự chọn]
```

## Flow 2 — Chia sẻ chỗ (US-04 → US-08, US-23)

```mermaid
sequenceDiagram
    actor Chu as Chủ chỗ
    participant Ag as Agent
    actor Thue as Người thuê
    participant BQL as BQL khu có ô đỗ
    Ag->>Chu: Đề xuất khung giờ chia sẻ (kèm khoảng dự phòng)
    Chu->>Ag: Chọn khung giờ và phạm vi (≤ mức nội quy cho phép)
    Ag->>Ag: Ghép cung với cầu (khung giờ, kích thước, phạm vi)
    Ag->>Chu: Gửi thỏa thuận điện tử theo mẫu của khu
    Ag->>Thue: Gửi thỏa thuận điện tử theo mẫu của khu
    Chu->>Ag: Xác nhận
    Thue->>Ag: Xác nhận
    Ag->>Ag: Kiểm tra có vượt ngưỡng cần duyệt của khu không
    alt Vượt ngưỡng
        Ag->>BQL: Gửi yêu cầu HITL
        BQL->>Ag: Duyệt / từ chối
    end
    Ag->>Ag: Ghi giao dịch có hiệu lực vào sổ cái
    Ag->>BQL: Ghi nhận giao dịch
```

## Flow 3 — Xử lý ngoại lệ (US-09 → US-11)

```mermaid
flowchart TD
    A{Ngoại lệ} -- Chủ về sớm --> B[Chủ quay về chỗ của mình]
    B --> C{Pool TH3 cùng khu<br/>còn chỗ?}
    C -- Có --> C1[Điều phối người thuê sang TH3 cùng khu]
    C -- Không --> C2[Gợi ý chỗ ở khu lân cận trong chuỗi]
    A -- Người thuê đỗ quá giờ --> D[Agent nhắc người thuê]
    D --> E[Tính phí theo nội quy của khu]
```

## Flow 4 — Tranh chấp (US-12, US-13)

```mermaid
flowchart LR
    A[Phát sinh tranh chấp<br/>kênh báo: TBD] --> B[Agent đọc ảnh]
    B --> C[Đối chiếu sổ cái<br/>và dữ liệu cổng của khu]
    C --> D[Lập ticket<br/>biển số đã ẩn]
    D --> E[Chuyển BQL khu có ô đỗ xác minh]
    E --> F[Kết quả xử lý: TBD]
```

## Flow 5 — Hoán đổi (US-14, US-15)

```mermaid
flowchart LR
    A[Tranh chấp lặp lại<br/>hoặc nhu cầu đã đăng ký] --> B[Agent đề xuất hoán đổi<br/>2 bên hoặc theo chuỗi, cùng khu]
    B --> C{BQL khu phê duyệt?}
    C -- Có --> D[Hoán đổi có hiệu lực]
    C -- Không --> E[Giữ nguyên phân bổ]
```

## Flow 6 — Nạp và xử lý log LPR

```mermaid
flowchart TD
    A[Webhook / MQTT / DB / CSV của từng khu<br/>hoặc log demo] --> B[Worker chuẩn hóa sự kiện, gắn khu nguồn]
    B --> C{Mã sự kiện đã xử lý?}
    C -- Có --> D[Bỏ qua sự kiện trùng]
    C -- Không --> E{Độ tin cậy OCR đạt ngưỡng?}
    E -- Không --> F[Đưa vào hàng chờ người kiểm tra]
    E -- Có --> G[Đối chiếu lịch chia sẻ và sổ cái]
    G --> H{Quá giờ hoặc có dấu hiệu tranh chấp?}
    H -- Quá giờ --> I[Worker nhắc người thuê và tính phí theo nội quy]
    H -- Tranh chấp --> J[Agent lập ticket ẩn danh]
    H -- Không --> K[Cập nhật trạng thái chỗ]
```

Thông tin nhận dạng được ẩn danh trước khi gửi ngữ cảnh tới LLM. Log OCR không chắc chắn cần người kiểm tra; Agent không tự đưa ra phán quyết tranh chấp.
