# User Flow — Agent điều phối quyền sử dụng chỗ đỗ

> Nguồn: [01-xac-dinh-bai-toan.md](../../01-xac-dinh-bai-toan.md)
> Liên quan: [User Stories](../user-stories.md) · [Acceptance Criteria](../acceptance-criteria.md) · [PRD](../prd.md)
> Wireframes: [wireframes/](wireframes/) (chưa có) · UI design: [ui-design/](ui-design/) (chưa có)

Các luồng thể hiện nghiệp vụ bản demo. Agent điều phối các nhánh nghiệp vụ; ingest LPR, nhắc quá giờ, đối soát cuối ngày và dự báo chạy qua worker nền. Màn hình và thao tác UI cụ thể: TBD.

## Flow 1 — Định tuyến yêu cầu chỗ đỗ (US-01 → US-03)

```mermaid
flowchart TD
    A[Người cần chỗ gửi yêu cầu] --> B{Agent: đủ điều kiện<br/>thuê chỗ riêng?}
    B -- Có --> C[Ghép vào TH1 hoặc TH2]
    B -- Không --> D[Chuyển sang TH3<br/>hoặc bãi công cộng]
    C --> E{Giao dịch đúng đối tượng<br/>và ô vừa kích thước xe?}
    E -- Không --> F[Chặn giao dịch]
    E -- Có --> G[Tiếp tục Flow 2]
    E -- Không có ô phù hợp --> X[Thông báo không có chỗ phù hợp]
```

## Flow 2 — Chia sẻ chỗ (US-04 → US-08)

```mermaid
sequenceDiagram
    actor Chu as Chủ chỗ
    participant Ag as Agent
    actor Thue as Người thuê
    participant BQL
    Ag->>Chu: Đề xuất khung giờ chia sẻ (kèm khoảng dự phòng)
    Chu->>Ag: Chọn khung giờ chia sẻ (thao tác cụ thể: TBD)
    Ag->>Ag: Ghép cung với cầu
    Ag->>Chu: Gửi thỏa thuận điện tử theo mẫu
    Ag->>Thue: Gửi thỏa thuận điện tử theo mẫu
    Chu->>Ag: Xác nhận
    Thue->>Ag: Xác nhận
    Ag->>Ag: Kiểm tra có vượt ngưỡng cần duyệt không
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
    B --> C[Agent điều phối chỗ thay thế<br/>cho người thuê từ pool TH3]
    C -. Pool TH3 hết chỗ .-> X[TBD]
    A -- Người thuê đỗ quá giờ --> D[Agent nhắc người thuê]
    D --> E[Tính phí theo nội quy]
```

## Flow 4 — Tranh chấp (US-12, US-13)

```mermaid
flowchart LR
    A[Phát sinh tranh chấp<br/>kênh báo: TBD] --> B[Agent đọc ảnh]
    B --> C[Đối chiếu sổ cái<br/>và dữ liệu cổng]
    C --> D[Lập ticket<br/>biển số đã ẩn]
    D --> E[Chuyển BQL xác minh]
    E --> F[Kết quả xử lý: TBD]
```

## Flow 5 — Hoán đổi (US-14, US-15)

```mermaid
flowchart LR
    A[Tranh chấp lặp lại<br/>hoặc nhu cầu đã đăng ký] --> B[Agent đề xuất hoán đổi<br/>2 bên hoặc theo chuỗi]
    B --> C{BQL phê duyệt?}
    C -- Có --> D[Hoán đổi có hiệu lực]
    C -- Không --> E[Giữ nguyên phân bổ]
```

## Flow 6 — Nạp và xử lý log LPR

```mermaid
flowchart TD
    A[Webhook / MQTT / DB / CSV<br/>hoặc log demo] --> B[Worker chuẩn hóa sự kiện]
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
