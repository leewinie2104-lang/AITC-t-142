# INDEX — Bản đồ tài liệu `docs/`

Mục lục của toàn bộ tài liệu trong `docs/`, dành cho agent và người đọc. Đọc file này trước để biết cần mở file nào, thay vì quét cả thư mục.

## Cách dùng

- **Người mới** nên đọc theo thứ tự: [Bài toán](01-xac-dinh-bai-toan.md) → [Project Brief](01-product/project-brief.md) → [PRD](01-product/prd.md) → [Scope](01-product/scope.md) → [User Stories](01-product/user-stories.md) → [Acceptance Criteria](01-product/acceptance-criteria.md) → [Tech stack](02-architecture/tech-stack.md) → [ADR](#10-adr--quyết-định-kiến-trúc).
- **Khi các nguồn mâu thuẫn:**
  - Code trong `src/` đúng hơn tài liệu (xem `CLAUDE.md`).
  - Văn bản đúng hơn ảnh trong `images/`. Nhiều ảnh là bản cũ, vẽ trước khi chuyển sang mô hình chuỗi N khu.
  - ADR có Status `Accepted` đúng hơn các đề xuất kiến trúc cũ hơn.
- `guide/` là guidebook chung của template AI20K, **không phải** đặc tả của dự án ParkSmart AI.

## Cập nhật file này (cho agent)

File này **không** được sinh tự động. Khi thêm, đổi tên hoặc xóa tài liệu trong `docs/`, hoặc khi nội dung chính của một file thay đổi, hãy sửa lại dòng tương ứng ở đây:

- Mỗi tài liệu là một dòng: `[Tiêu đề](đường-dẫn-tương-đối)`, kèm 1 câu nói tài liệu đó trả lời câu hỏi gì.
- Đặt tài liệu mới vào đúng thư mục đánh số. Nếu thư mục đang ghi "chưa có tài liệu" thì xóa dòng đó đi.
- Chỉ ghi nội dung chính của tài liệu. Không chép nội dung chi tiết vào đây.

---

## Gốc `docs/`

| Tài liệu | Nội dung |
|---|---|
| [Bài toán](01-xac-dinh-bai-toan.md) | Đề bài gốc: bối cảnh, vấn đề, đối tượng, giả định pháp lý, agent làm gì, KPI. Mọi tài liệu `01-product/` đều suy ra từ file này. |
| [Architecture Diagram](architecture_diagram.md) | Sơ đồ kiến trúc hiện hành, tổng quan hệ thống, luồng một yêu cầu đặt chỗ (W1 → W2) và các thành phần. |

## `01-product/` — Đặc tả sản phẩm

| Tài liệu | Nội dung |
|---|---|
| [Project Brief](01-product/project-brief.md) | Bối cảnh chuỗi khu đô thị, vấn đề, ai cần thuê chỗ, giải pháp, giá trị, KPI. |
| [PRD](01-product/prd.md) | Mục tiêu, mô hình tổ chức, tư cách L1–L4, phân loại chỗ đỗ, quy tắc nghiệp vụ và yêu cầu chức năng. |
| [Scope](01-product/scope.md) | Phạm vi bản demo (3 khu mô phỏng), ngoài phạm vi, nguyên tắc dữ liệu và quyền riêng tư, giả định cần xác nhận. |
| [User Stories](01-product/user-stories.md) | User story (US-xx) theo epic và vai trò. |
| [Acceptance Criteria](01-product/acceptance-criteria.md) | Tiêu chí Given/When/Then (AC-xx), ánh xạ 1-1 với user story. |

### `01-product/backlog/` — Backlog 3 nhóm × 3 mức ưu tiên

| Tài liệu | Nội dung |
|---|---|
| [README](01-product/backlog/README.md) | Định nghĩa 3 mức ưu tiên (Rất cần thiết / Nên có / Tương lai) và cách chia backlog. |
| [Module (FE / BE)](01-product/backlog/modules.md) | 14 module frontend/backend, chia theo mức ưu tiên. |
| [Workflow AI Agent](01-product/backlog/agent-workflows.md) | W0 Supervisor và W1–W7 (LangGraph): các bước tất định, LLM, HITL và RAG theo mức ưu tiên. |
| [Workflow nền](01-product/backlog/background-workflows.md) | N1–N8 chạy bằng worker arq + Redis, không gọi LLM, theo mức ưu tiên. |

### `01-product/ux/` — UX

| Tài liệu | Nội dung |
|---|---|
| [User Flow](01-product/ux/user-flow.md) | Các luồng nghiệp vụ của bản demo: agent điều phối và worker nền. |
| [Wireframes README](01-product/ux/wireframes/README.md) | Giới thiệu bộ wireframe HTML low-fidelity và cách mở. |
| [Danh mục màn hình](01-product/ux/wireframes/index.html) | Trang mục lục, mở trong trình duyệt để xem mọi wireframe. |

Các wireframe trong `01-product/ux/wireframes/`:
- **Cư dân / chủ chỗ:** [Đăng ký & đồng ý dữ liệu](01-product/ux/wireframes/register.html) · [Chỗ của tôi](01-product/ux/wireframes/owner-home.html) · [Lập lịch chia sẻ](01-product/ux/wireframes/owner-share-schedule.html) · [Báo về sớm](01-product/ux/wireframes/owner-early-return.html) · [Đề xuất hoán đổi](01-product/ux/wireframes/swap-proposal.html) · [Voucher lượt TH3](01-product/ux/wireframes/shophouse-voucher.html)
- **Người thuê:** [Yêu cầu chỗ đỗ](01-product/ux/wireframes/request-parking.html) · [Thỏa thuận điện tử](01-product/ux/wireframes/agreement.html) · [Thanh toán VietQR mock](01-product/ux/wireframes/payment.html) · [Lượt đỗ của tôi](01-product/ux/wireframes/renter-booking.html) · [Báo tranh chấp](01-product/ux/wireframes/dispute-report.html) · [Thông báo](01-product/ux/wireframes/notifications.html)
- **BQL (admin):** [Bảng điều khiển](01-product/ux/wireframes/admin-dashboard.html) · [Duyệt giao dịch HITL](01-product/ux/wireframes/admin-approvals.html) · [Duyệt hoán đổi](01-product/ux/wireframes/admin-swaps.html) · [Ticket tranh chấp](01-product/ux/wireframes/admin-disputes.html) · [Chi tiết ticket](01-product/ux/wireframes/admin-dispute-detail.html) · [Sổ cái](01-product/ux/wireframes/admin-ledger.html) · [Log LPR & hàng chờ OCR](01-product/ux/wireframes/admin-lpr-review.html)

`01-product/ux/ui-design/`: chưa có tài liệu.

## `02-architecture/` — Kiến trúc

| Tài liệu | Nội dung |
|---|---|
| [Tech stack](02-architecture/tech-stack.md) | Stack theo từng lớp, các môi trường, rủi ro cần xác nhận, gợi ý chia việc cho 4 người. |

## `10-adr/` — Quyết định kiến trúc

Tất cả đều có Status **Accepted**.

| ADR | Quyết định |
|---|---|
| [0001](10-adr/ADR-0001-monorepo-client-server.md) | Monorepo, chia hai thư mục `client/` và `server/` |
| [0002](10-adr/ADR-0002-react-vite-spa-on-s3-cloudfront.md) | Client là React (Vite) SPA, host trên S3 + CloudFront |
| [0003](10-adr/ADR-0003-rest-openapi-sse-websocket-single-domain.md) | REST + OpenAPI; SSE cho chat, WebSocket cho thông báo; một domain CloudFront |
| [0004](10-adr/ADR-0004-fastapi-langgraph-arq-on-ec2-docker-compose.md) | Server FastAPI + LangGraph, worker arq + Redis, chạy docker compose trên EC2 |
| [0005](10-adr/ADR-0005-rds-postgres-asyncpg-rls-alembic-sql.md) | RDS PostgreSQL + pgvector, asyncpg, RLS theo khu/hộ, Alembic SQL thuần |
| [0006](10-adr/ADR-0006-self-issued-jwt-auth.md) | Xác thực bằng JWT tự phát hành trong FastAPI |
| [0007](10-adr/ADR-0007-claude-via-amazon-bedrock.md) | Dùng Claude qua Amazon Bedrock (region chưa chốt) |
| [0008](10-adr/ADR-0008-opentelemetry-lgtm-on-dedicated-ec2.md) | OpenTelemetry + LGTM (Loki, Grafana, Tempo, Mimir) trên một EC2 riêng |
| [0009](10-adr/ADR-0009-terraform-github-actions-ecr-ssm.md) | Hạ tầng bằng Terraform; CI/CD bằng GitHub Actions → ECR → EC2 qua SSM |

## Thư mục chưa có tài liệu

`03-design/` · `04-api/` · `05-development/` · `06-testing/` · `07-deployment/` · `08-operations/` · `09-security/` · `11-references/` · `12-ai/`

## `images/` — Ảnh sơ đồ

Nhiều ảnh là bản cũ. Khi ảnh khác văn bản, văn bản là bản đúng.

| Ảnh | Được dùng trong |
|---|---|
| [ParkSmartAI.png](images/ParkSmartAI.png) | Kiến trúc cũ (Vercel / Railway / Supabase), [Architecture Diagram](architecture_diagram.md) |
| [arch-overview](images/ParkSmartAI-arch-overview.png) · [arch-tech-stack](images/ParkSmartAI-arch-tech-stack.png) · [arch-communication](images/ParkSmartAI-arch-communication.png) · [arch-observability](images/ParkSmartAI-arch-observability.png) · [arch-cicd](images/ParkSmartAI-arch-cicd.png) | Kiến trúc AWS: tổng quan, stack, giao tiếp, observability, CI/CD |
| [modules](images/ParkSmartAI-modules.png) · [agent-workflows](images/ParkSmartAI-agent-workflows.png) · [background-workflows](images/ParkSmartAI-background-workflows.png) | Các file [backlog](01-product/backlog/README.md) |

## `guide/` — Guidebook AI20K (tài liệu chung, không phải của dự án)

Bắt đầu từ [README](guide/README.md). Gặp lỗi thì xem [Troubleshooting](guide/troubleshooting.md).

- **Các chương:** [01 Lời mở đầu](guide/chapter-01.md) · [02 Khởi tạo từ template](guide/chapter-02.md) · [03 Thiết kế kiến trúc](guide/chapter-03.md) · [04 Agent với LangGraph](guide/chapter-04.md) · [05 Đề bài → USP](guide/chapter-05.md) · [06 RAG](guide/chapter-06.md) · [07 Workflow & Reliability](guide/chapter-07.md) · [08 FastAPI](guide/chapter-08.md) · [09 Giao diện](guide/chapter-09.md) · [10 Kiểm thử & đánh giá](guide/chapter-10.md) · [11 Privacy, Security & Governance](guide/chapter-11.md) · [12 DevOps](guide/chapter-12.md) · [13 Nộp bài Demo Day](guide/chapter-13.md) · [14 Case studies](guide/chapter-14.md) · [15 Tài nguyên học](guide/chapter-15.md)
- **Chủ đề:**
  - [Agent practices](guide/agent-practices/_index.md): prompts, evals, guardrails, context, multi-tool config
  - [Anti-patterns](guide/anti-patterns/_index.md): những lỗi phải tránh
  - [Architecture](guide/architecture/_index.md)
  - [BMAD](guide/bmad/_index.md)
  - [Code style](guide/code-style/_index.md)
  - [Deliverables](guide/deliverables/_index.md): 10 deliverables Demo Day
  - [DevOps](guide/devops/_index.md)
  - [LangGraph](guide/langgraph/_index.md): state, nodes & edges, tools
  - [Patterns](guide/patterns/_index.md): RAG
  - [Resources](guide/resources/_index.md)
  - [Setup](guide/setup/_index.md)
  - [Testing](guide/testing/_index.md)
- **Khác:** [Quản lý chi phí API](guide/cost-management.md) · [Tài khoản miễn phí](guide/free-accounts.md)
