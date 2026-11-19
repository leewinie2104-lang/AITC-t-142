# Architecture Diagram — ParkSmart AI

> Stack và lý do lựa chọn: [docs/02-architecture/02-tech-stack.md](02-tech-stack.md) · ADR: [docs/07-adr/](../07-adr/)

![Kiến trúc tổng quan trên AWS](../images/ParkSmartAI-arch-overview.png)

Ảnh khác: [stack theo lớp](../images/ParkSmartAI-arch-tech-stack.png) · [giao tiếp REST / SSE / WebSocket, JWT, RLS](../images/ParkSmartAI-arch-communication.png) ·
[CI/CD](../images/ParkSmartAI-arch-cicd.png) · [observability](../images/ParkSmartAI-arch-observability.png) · [cây thư mục server](../images/ParkSmartAI-arch-backend-folders.png) (ADR-0010).

## Tổng quan hệ thống

```mermaid
flowchart TB
    U([Cư dân · Người thuê · Bảo vệ · BQL khu · Vận hành chuỗi])
    LPR([Hệ thống LPR từng khu<br/>hoặc log mô phỏng])

    subgraph AWS["AWS"]
        CF[CloudFront<br/>một domain]
        S3[(S3<br/>React SPA)]

        subgraph APP["EC2 app · docker compose"]
            CADDY[Caddy<br/>HTTPS origin]
            API[FastAPI<br/>REST · SSE · WebSocket]
            AG[LangGraph Agent<br/>W0–W7 · HITL]
            WK[Worker arq<br/>N1–N8]
            RD[(Redis<br/>queue · pub/sub)]
            OC[OTel Collector]
        end

        RDS[(RDS PostgreSQL<br/>RLS · pgvector · checkpoint)]
        BR[Amazon Bedrock<br/>Claude Haiku / Sonnet / Opus 5.5]
        SSM[SSM Parameter Store]

        subgraph OBS["EC2 observability"]
            LGTM[Grafana · Loki · Tempo · Mimir]
        end
    end

    U -->|HTTPS| CF
    CF -->|"/*"| S3
    CF -->|"/api/*, /ws"| CADDY
    CADDY --> API
    API --> AG
    AG -->|prompt đã ẩn danh| BR
    API -->|asyncpg + SET LOCAL| RDS
    AG -->|psycopg 3 checkpointer| RDS
    API -->|enqueue / publish| RD
    WK -->|consume / publish| RD
    WK --> RDS
    LPR -->|webhook / MQTT / CSV| API
    SSM -.->|bí mật khi khởi động| API
    API -.-> OC
    WK -.-> OC
    OC -.->|OTLP| LGTM
```

## Luồng một yêu cầu đặt chỗ (W1 → W2)

```mermaid
sequenceDiagram
    autonumber
    actor C as Cư dân (SPA)
    participant API as FastAPI
    participant AG as LangGraph
    participant RE as Rule engine
    participant DB as Postgres (RLS)
    participant BR as Bedrock
    participant WS as WebSocket

    C->>API: POST /api/v1/chat/stream (JWT, traceparent)
    API->>DB: SET LOCAL app.user_id, app.zone_ids
    API->>AG: W0: guardrail → ẩn danh
    AG->>BR: phân loại ý định (Haiku)
    BR-->>AG: intent = xin chỗ
    AG->>RE: W1: tính cấp tư cách L1–L4 + phạm vi mở
    RE->>DB: truy vấn tư cách, pool, ô trống
    RE-->>AG: được ghép ô X / chuyển TH3 / bị chặn
    AG-->>API: stream câu trả lời (SSE)
    API-->>C: token…
    AG->>DB: giữ chỗ tạm, sinh thỏa thuận (W2)
    alt vượt ngưỡng của khu
        AG->>DB: checkpoint, dừng chờ duyệt
        API-->>WS: zone:{id}:bql có việc chờ duyệt
    end
    API-->>WS: user:{id} có thỏa thuận cần xác nhận OTP (OTP lưu ở Redis, ADR-0011)
```

## Thành phần

| Thành phần | Công nghệ | Vai trò |
|------------|-----------|---------|
| Client | React + Vite, Tailwind + shadcn/ui, TanStack Query | Chat, đặt chỗ, chia sẻ, dashboard BQL |
| CDN | CloudFront + S3 | Phục vụ client; định tuyến `/api/*` và `/ws` về EC2 |
| API | FastAPI | REST, SSE (chat), WebSocket (thông báo; 4 tuần đầu client polling danh sách `notification`), JWT |
| Agent | LangGraph + Claude trên Bedrock | W0–W7 (4 tuần: W0–W3, W7); LLM chỉ gợi ý, rule engine quyết định |
| Worker | arq + Redis | N1–N8; trong 4 tuần chỉ N1 nạp log LPR mô phỏng ([backlog](../01-product/backlog/03-background-workflows.md)) |
| DB | RDS PostgreSQL + pgvector | Dữ liệu nghiệp vụ, RLS theo khu / hộ, bằng chứng xác nhận (`consent_record`), nhật ký quyết định AI, RAG, checkpoint; 25 bảng ([ADR-0011](../07-adr/ADR-0011-mvp-simplifications.md)) |
| Observability | OpenTelemetry → LGTM | Liên kết metric → trace → log |
| Hạ tầng | Terraform, GitHub Actions, SSM | Dựng / xóa hạ tầng, deploy không cần SSH |
