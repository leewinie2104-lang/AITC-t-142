# 02-architecture — Kiến trúc hệ thống

> **Thư mục này trả lời:** hệ thống gồm những thành phần nào, chạy ở đâu, giao tiếp ra sao, và vì sao chọn stack này.

## Tổng quan

Kiến trúc chốt ngày 2026-11-17 cho đội 4 người, 4 tuần: client React (Vite) SPA trên S3 + CloudFront; server FastAPI + LangGraph và worker arq + Redis chạy docker compose trên một EC2; RDS PostgreSQL + pgvector; Claude qua Amazon Bedrock; quan sát bằng OpenTelemetry + LGTM trên EC2 riêng. Mỗi lựa chọn có một ADR trong [07-adr/](../07-adr/README.md).

## File

| File | Trả lời câu hỏi |
|---|---|
| [01-architecture-diagram.md](01-architecture-diagram.md) | Hệ thống trông thế nào: ảnh kiến trúc, tổng quan, luồng một yêu cầu đặt chỗ (W1 → W2), các thành phần |
| [02-tech-stack.md](02-tech-stack.md) | Dùng công nghệ gì ở từng lớp, môi trường `local` / `demo`, rủi ro R1–R7, chia việc 4 người |

## Ảnh

| Ảnh | Nội dung |
|---|---|
| [arch-overview](../images/ParkSmartAI-arch-overview.png) | Tổng quan trên AWS |
| [arch-tech-stack](../images/ParkSmartAI-arch-tech-stack.png) | Stack theo lớp, gắn mã ADR |
| [arch-communication](../images/ParkSmartAI-arch-communication.png) | REST / SSE / WebSocket, JWT, RLS |
| [arch-cicd](../images/ParkSmartAI-arch-cicd.png) | CI/CD và Terraform |
| [arch-observability](../images/ParkSmartAI-arch-observability.png) | OTel → Tempo / Mimir / Loki → Grafana |
| [arch-backend-folders](../images/ParkSmartAI-arch-backend-folders.png) | Cây thư mục server |

Ảnh `arch-overview` chưa có container `agent-worker` (ghi chú từ plan 006). Khi ảnh khác văn bản, văn bản đúng hơn.

## ADR liên quan

[0001](../07-adr/ADR-0001-monorepo-client-server.md) monorepo · [0002](../07-adr/ADR-0002-react-vite-spa-on-s3-cloudfront.md) client · [0003](../07-adr/ADR-0003-rest-openapi-sse-websocket-single-domain.md) giao tiếp · [0004](../07-adr/ADR-0004-fastapi-langgraph-arq-on-ec2-docker-compose.md) server, worker · [0005](../07-adr/ADR-0005-rds-postgres-asyncpg-rls-alembic-sql.md) dữ liệu · [0007](../07-adr/ADR-0007-claude-via-amazon-bedrock.md) LLM · [0008](../07-adr/ADR-0008-opentelemetry-lgtm-on-dedicated-ec2.md) quan sát · [0010](../07-adr/ADR-0010-backend-modules-agent-workflows-jobs.md) module, workflow, job

## Sẽ thêm vào đây

- Job, queue và lịch chạy của worker N1–N8 (theo [backlog](../01-product/backlog/03-background-workflows.md)).
- Sơ đồ trình tự cho HITL: `interrupt()` → hàng chờ duyệt → resume.

## Quy ước

- File mới đánh số `NN-` tiếp theo; cập nhật bảng trên và [docs/README.md](../README.md).
- Đổi một quyết định đã chốt thì viết ADR mới (skill `new-adr`), không sửa thẳng tài liệu ở đây.
