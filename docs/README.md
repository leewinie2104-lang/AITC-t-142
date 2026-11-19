# ParkSmart AI — Bản đồ tài liệu `docs/`

Trang đầu của `docs/` cho người đọc và agent: đọc file này để biết mở file nào, thay vì quét cả thư mục.

ParkSmart AI là Agent điều phối quyền sử dụng chỗ đỗ trong **chuỗi khu đô thị** (≥ 2 khu) cùng chủ đầu tư. Một tài khoản cho cả chuỗi, nhiều tư cách
gắn tài sản; Agent định tuyến yêu cầu đỗ xe, đề xuất chia sẻ chỗ trống theo tư cách, phạm vi mở của pool và sự duyệt của BQL. Demo: dữ liệu mô phỏng 3 khu.
Đội 4 người, **4 tuần**: việc cần làm ở [Backlog](01-product/05-backlog.md).

## Thứ tự đọc

1. [Bài toán](01-product/00-xac-dinh-bai-toan.md) → [Project Brief](01-product/01-project-brief.md) → [PRD](01-product/02-prd.md) → [Scope](01-product/03-scope.md)
2. [Backlog 4 tuần](01-product/05-backlog.md): mỗi tính năng làm gì ở DB / BE / worker / FE, tuần nào; Mức 3 làm nếu còn thời gian
3. [User Stories & AC](01-product/04-user-stories.md) → [Traceability](01-product/06-traceability.md) (US → use case cần code)
4. [Tech stack](02-architecture/02-tech-stack.md) → [Architecture Diagram](02-architecture/01-architecture-diagram.md) → [ADR](07-adr/README.md)
5. [Data model](03-design/01-data-model.md) (schema 25 bảng) → [Cấu trúc server](04-development/01-server-structure.md)

## Quy ước

- Thư mục `NN-<khu-vực>/` đánh số liền mạch 01–08 theo thứ tự đọc (không còn thư mục giữ chỗ); file `.md` có tiền tố `NN-`; `README.md` là giới thiệu thư mục, không đánh số.
- **Mỗi file `.md` dưới 100 dòng.** Nội dung tra cứu dài tách vào thư mục con (ví dụ `03-design/erd/`, `03-design/dictionary/`).
- ADR: `07-adr/ADR-NNNN-<kebab>.md`; Accepted thì không đổi quyết định, đổi hướng bằng ADR mới (Superseded).
- `guide/` là guidebook của ban tổ chức (CODEOWNERS), **không** phải đặc tả dự án, không sửa. `images/` chứa ảnh PNG.
- **Khi mâu thuẫn:** code trong `server/src/app/` đúng hơn tài liệu · văn bản đúng hơn ảnh · ADR Accepted đúng hơn đề xuất cũ.

## Bản đồ tài liệu

### `01-product/` — Sản phẩm ([README](01-product/README.md))

| Tài liệu | Trả lời câu hỏi |
|---|---|
| [00 Bài toán](01-product/00-xac-dinh-bai-toan.md) · [01 Brief](01-product/01-project-brief.md) | Đề bài gốc; bối cảnh, vấn đề, giải pháp, KPI |
| [02 PRD](01-product/02-prd.md) | Tư cách L1–L4, loại chỗ TH1–TH3, BR, FR (kèm mức ưu tiên) |
| [03 Scope](01-product/03-scope.md) | Demo làm gì, không làm gì, nguyên tắc dữ liệu, giả định A-xx |
| [04 User Stories & AC](01-product/04-user-stories.md) · [06 Traceability](01-product/06-traceability.md) | US + AC theo epic; US → use case → màn hình |
| [Backlog](01-product/05-backlog.md) · [bản HTML có bộ lọc](01-product/05-backlog.html) | Tính năng × DB / BE / Worker nền / Worker Agent / FE; mức 1–3; tuần |
| [User Flow](01-product/ux/01-user-flow.md) · [Wireframes](01-product/ux/wireframes/README.md) · [index.html](01-product/ux/wireframes/index.html) | Luồng nghiệp vụ; 19 màn hình wireframe kèm mức ưu tiên |

### `02-architecture/` — Kiến trúc ([README](02-architecture/README.md))

| Tài liệu | Trả lời câu hỏi |
|---|---|
| [01 Architecture Diagram](02-architecture/01-architecture-diagram.md) | Tổng quan AWS, luồng W1 → W2, thành phần |
| [02 Tech stack](02-architecture/02-tech-stack.md) | Stack theo lớp, môi trường, rủi ro, chia việc 4 người |

### `03-design/` — Thiết kế CSDL, đề xuất v5, 25 bảng ([README](03-design/README.md))

| Tài liệu | Trả lời câu hỏi |
|---|---|
| [01 Data model](03-design/01-data-model.md) · [10 Giả định & truy vết](03-design/10-assumptions-traceability.md) | Tóm tắt, quyết định chính, kiểm chứng; giả định, yêu cầu → schema |
| [02 ERD](03-design/02-erd.md) · [03 Data dictionary](03-design/03-data-dictionary.md) | Quan hệ (Mermaid trong `erd/`); bảng và cột (trong `dictionary/`) |
| [04 Queries & indexes](03-design/04-queries-indexes.md) · [05 Concurrency](03-design/05-concurrency.md) · [06 Risks](03-design/06-risks-edge-cases.md) | Index theo truy vấn; đồng thời từng luồng; tình huống biên, rủi ro |
| [07 Decision log](03-design/07-db-decision-log.md) · [08 Deferred tables](03-design/08-deferred-tables.md) · [11 Deferred designs](03-design/11-deferred-designs-functions.md) | D-01…D-33; 34 bảng hoãn và cách thêm lại |
| [09 Đề xuất sửa ADR-0005](03-design/09-adr-0005-amendment-proposal.md) · [sql/](03-design/sql/schema.sql) · [diagrams/](03-design/diagrams/schema-diagram.html) | Mã hóa biển số ở ứng dụng; DDL, seed + test; sơ đồ HTML |

### Các thư mục khác

| Thư mục | Tài liệu |
|---|---|
| `04-development/` ([README](04-development/README.md)) | [01 Cấu trúc server](04-development/01-server-structure.md): module, tầng `agent/`, job nền (ADR-0010); README có tầng kiểm thử, eval, API |
| `05-deployment/` ([README](05-deployment/README.md)) | [01 Checklist CSDL trước production](05-deployment/01-db-preprod-checklist.md) |
| `06-operations/` ([README](06-operations/README.md): quan sát + tóm tắt bảo mật) | [01 Migration, backup](06-operations/01-database-operations.md) · [02 Bảo mật](06-operations/02-database-security.md) · [03 Giám sát, mở rộng](06-operations/03-database-monitoring-scaling.md) |
| `08-ai/` ([README](08-ai/README.md)) | [01 Agent setup](08-ai/01-agent-setup.md) (tiếng Anh): Claude Code, Codex, cài đặt macOS / Windows · [02 RAG kho tri thức](08-ai/02-rag-knowledge-base.md): pipeline W7, dữ liệu `server/knowledge_base/` |

### `07-adr/` — Quyết định kiến trúc (đều Accepted)

| ADR | Quyết định |
|---|---|
| [0001](07-adr/ADR-0001-monorepo-client-server.md) · [0002](07-adr/ADR-0002-react-vite-spa-on-s3-cloudfront.md) | Monorepo `client/` + `server/`; React (Vite) SPA trên S3 + CloudFront |
| [0003](07-adr/ADR-0003-rest-openapi-sse-websocket-single-domain.md) | REST + OpenAPI; SSE cho chat, WebSocket cho thông báo; một domain |
| [0004](07-adr/ADR-0004-fastapi-langgraph-arq-on-ec2-docker-compose.md) | FastAPI + LangGraph, worker arq + Redis, docker compose trên EC2 |
| [0005](07-adr/ADR-0005-rds-postgres-asyncpg-rls-alembic-sql.md) | RDS PostgreSQL + pgvector, asyncpg, RLS theo khu / hộ, Alembic SQL thuần |
| [0006](07-adr/ADR-0006-self-issued-jwt-auth.md) · [0007](07-adr/ADR-0007-claude-via-amazon-bedrock.md) | JWT tự phát hành; Claude qua Amazon Bedrock |
| [0008](07-adr/ADR-0008-opentelemetry-lgtm-on-dedicated-ec2.md) · [0009](07-adr/ADR-0009-terraform-github-actions-ecr-ssm.md) | OpenTelemetry + LGTM trên EC2 riêng; Terraform, GitHub Actions → ECR → SSM |
| [0010](07-adr/ADR-0010-backend-modules-agent-workflows-jobs.md) | Server theo module; `agent/` điều phối W0–W7; job N1–N8 là delivery adapter |
| [0011](07-adr/ADR-0011-mvp-simplifications.md) | Schema demo 23 bảng (25 sau D-33: thêm tranh chấp, phí quá giờ), thêm `ai_decision_log` (thay một phần 0004, 0005, 0006, 0010) |

### `images/` — Ảnh (văn bản đúng hơn ảnh)

Kiến trúc: [overview](images/ParkSmartAI-arch-overview.png) · [tech-stack](images/ParkSmartAI-arch-tech-stack.png) · [communication](images/ParkSmartAI-arch-communication.png) ·
[observability](images/ParkSmartAI-arch-observability.png) · [cicd](images/ParkSmartAI-arch-cicd.png) · [backend-folders](images/ParkSmartAI-arch-backend-folders.png).
Backlog 4 tuần: bản xem trên trình duyệt [01-product/05-backlog.html](01-product/05-backlog.html).

Guidebook AI20K: [guide/README.md](guide/README.md) (tài liệu chung, không phải đặc tả dự án).

## Cập nhật file này (cho agent)

Không sinh tự động. Khi thêm, đổi tên, xóa tài liệu hoặc đổi nội dung chính: sửa dòng tương ứng ở đây (link tương đối, một câu "trả lời câu hỏi gì").
File mới lấy số `NN` kế tiếp trong thư mục; ADR mới đăng ký ở bảng ADR (skill `new-adr`). Giữ mỗi file dưới 100 dòng. Không sửa `guide/`.
