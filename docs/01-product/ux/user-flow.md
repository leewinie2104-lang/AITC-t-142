# User Flow — Agent điều phối quyền sử dụng chỗ đỗ

> Nguồn: [01-xac-dinh-bai-toan.md](../../01-xac-dinh-bai-toan.md)
> Liên quan: [User Stories](../user-stories.md) · [Acceptance Criteria](../acceptance-criteria.md) · [PRD](../prd.md)
> Wireframes: [wireframes/](wireframes/) (chưa có) · UI design: [ui-design/](ui-design/) (chưa có)

Các luồng dưới đây chỉ thể hiện những bước có trong tài liệu nguồn. Màn hình, kênh thông báo và thao tác UI cụ thể: TBD.

## Flow 1 — Định tuyến yêu cầu chỗ đỗ (US-01 → US-03)

```mermaid
flowchart TD
    A[Người cần chỗ gửi yêu cầu] --> B{Agent: đủ điều kiện<br/>thuê chỗ riêng?}
    B -- Có --> C[Ghép vào TH1 hoặc TH2]
    B -- Không --> D[Chuyển sang TH3<br/>hoặc bãi công cộng]
    C --> E{Giao dịch đúng đối tượng<br/>theo nội quy?}
    E -- Không --> F[Chặn giao dịch]
    E -- Có --> G[Tiếp tục Flow 2]
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
    Ag->>Ag: Ghi vào sổ cái
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
