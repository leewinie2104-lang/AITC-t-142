# 02-architecture — Kiến trúc hệ thống

> **Thư mục này trả lời:** hệ thống gồm những thành phần nào, chạy ở đâu, giao tiếp ra sao, và vì sao chọn stack này.

## Tổng quan

Kiến trúc chốt ngày 2026-11-17 cho đội 4 người, 4 tuần: client React (Vite) SPA trên S3 + CloudFront; server FastAPI + LangGraph và worker arq + Redis chạy docker compose trên một EC2; RDS PostgreSQL + pgvector; Claude qua Amazon Bedrock; quan sát bằng OpenTelemetry + LGTM trên EC2 riêng. Mỗi lựa chọn có một ADR trong [07-adr/](../07-adr/README.md).

## File

| File | Trả lời câu hỏi |
|---|---|
| [01-architecture-diagram.md](01-architecture-diagram.md) | Hệ thống trông thế nào: ảnh kiến trúc, tổng quan, luồng một yêu cầu chỗ đỗ (W1 → hàng chờ → W2), các thành phần |
| [02-tech-stack.md](02-tech-stack.md) | Dùng công nghệ gì ở từng lớp, môi trường `local` / `demo`, rủi ro R1–R7, chia việc 4 người |

## Sơ đồ (HTML, thay ảnh PNG từ 2026-11-22)

| Sơ đồ | Nội dung |
|---|---|
| [overview](diagrams/overview.html) | Prod Lightsail, AWS, runner CI + DB dev, LLM, luồng chính |
| [tech-stack](diagrams/tech-stack.html) | Stack theo lớp, gắn mã ADR và trạng thái |
| [communication](diagrams/communication.html) | REST / SSE / thông báo, chủ về sớm, HITL, token |
| [cicd](diagrams/cicd.html) | Kiểm PR, migrate DB dev, deploy kéo từ ECR, backup |
| [observability](diagrams/observability.html) | Log hiện có; kế hoạch OTel → Grafana Cloud |
| [backend-folders](diagrams/backend-folders.html) | Cây thư mục server, chiều gọi, ví dụ `sharing/` |

Mục lục: [diagrams/index.html](diagrams/index.html). Kiểu dùng chung ở `diagrams/assets/diagram.css`; sửa chữ trong HTML, không cần vẽ lại.
Khi sơ đồ khác văn bản (ADR), văn bản đúng hơn.

## ADR liên quan

[0001](../07-adr/ADR-0001-monorepo-client-server.md) monorepo · [0002](../07-adr/ADR-0002-react-vite-spa-on-s3-cloudfront.md) client · [0003](../07-adr/ADR-0003-rest-openapi-sse-websocket-single-domain.md) giao tiếp · [0004](../07-adr/ADR-0004-fastapi-langgraph-arq-on-ec2-docker-compose.md) server, worker · [0005](../07-adr/ADR-0005-rds-postgres-asyncpg-rls-alembic-sql.md) dữ liệu · [0007](../07-adr/ADR-0007-claude-via-amazon-bedrock.md) LLM · [0008](../07-adr/ADR-0008-opentelemetry-lgtm-on-dedicated-ec2.md) quan sát · [0010](../07-adr/ADR-0010-backend-modules-agent-workflows-jobs.md) module, workflow, job

## Sẽ thêm vào đây

- Job, queue và lịch chạy của worker N1–N9 (theo [backlog](../01-product/05-backlog.md#2-tính-năng)).
- Sơ đồ trình tự cho HITL: `interrupt()` → hàng chờ duyệt → resume.

## Quy ước

- File mới đánh số `NN-` tiếp theo; cập nhật bảng trên và [docs/README.md](../README.md).
- Đổi một quyết định đã chốt thì viết ADR mới (skill `new-adr`), không sửa thẳng tài liệu ở đây.
