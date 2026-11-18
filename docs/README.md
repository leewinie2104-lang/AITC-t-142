# ParkSmart AI — Bản đồ tài liệu `docs/`

Trang đầu của thư mục `docs/`, dành cho người đọc và agent. Đọc file này trước để biết cần mở file nào, thay vì quét cả thư mục.

## Giới thiệu

ParkSmart AI là một Agent điều phối quyền sử dụng chỗ đỗ trong **chuỗi khu đô thị** (từ 2 khu trở lên) do cùng một chủ đầu tư vận hành. Cư dân dùng một tài khoản cho cả chuỗi, có nhiều tư cách gắn với tài sản của mình. Agent định tuyến yêu cầu đỗ xe và đề xuất chia sẻ chỗ đang trống trong khu, dựa trên tư cách, phạm vi mở của từng pool và sự duyệt của Ban quản lý (BQL); khi khu hết chỗ, Agent gợi ý chỗ ở khu lân cận trong chuỗi. Bản demo dùng dữ liệu mô phỏng cho 3 khu. Chi tiết: [Project Brief](01-product/01-project-brief.md).

## Thứ tự đọc

Dành cho người mới:

1. [Bài toán](01-product/00-xac-dinh-bai-toan.md): đề bài gốc
2. [Project Brief](01-product/01-project-brief.md): bối cảnh, vấn đề, giải pháp
3. [PRD](01-product/02-prd.md): mô hình tổ chức, tư cách, quy tắc nghiệp vụ
4. [Scope](01-product/03-scope.md): phạm vi demo, ngoài phạm vi, giả định
5. [User Stories & Acceptance Criteria](01-product/04-user-stories.md)
6. [Traceability](01-product/06-traceability.md): nối user story với module, workflow và màn hình
7. [Tech stack](02-architecture/02-tech-stack.md) và [Architecture Diagram](02-architecture/01-architecture-diagram.md)
8. [ADR](10-adr/): các quyết định kiến trúc đã chốt

## Quy ước

- **Thư mục** có dạng `NN-<khu-vực>/`, số `NN` tăng dần theo thứ tự đọc. Các số còn thiếu là thư mục giữ chỗ, chưa có tài liệu.
- **File `.md`** trong mỗi thư mục con có tiền tố `NN-` theo thứ tự đọc trong thư mục đó. `00` là đề bài gốc (chỉ có ở `01-product/`).
- **`README.md`** trong một thư mục là phần giới thiệu của thư mục đó, không đánh số. **Mỗi thư mục đánh số đều có `README.md`** (khoảng 50 dòng): tổng quan, danh sách file, và gợi ý file nên có nếu thư mục còn trống.
- **ADR** giữ tên `ADR-NNNN-<tên-kebab-case>.md` trong `10-adr/`. Quyết định đã Accepted không sửa; đổi hướng bằng ADR mới đánh dấu bản cũ là Superseded.
- **`guide/`** là guidebook của ban tổ chức (template AI20K), do CODEOWNERS bảo vệ. Đây **không phải** đặc tả của dự án ParkSmart AI và không sửa trong repo này.
- **`images/`** chứa ảnh PNG minh họa, xem mục ảnh bên dưới.
- Wireframe HTML trong `01-product/ux/wireframes/` giữ tên gốc vì không phải file `.md`.

**Thứ tự ưu tiên khi các nguồn mâu thuẫn:**

1. **Code** trong `server/src/app/` đúng hơn mọi tài liệu. Khi tài liệu lệch code, sửa tài liệu hoặc báo lỗi code.
2. **Văn bản đúng hơn ảnh** trong `images/`.
3. **ADR có Status Accepted đúng hơn** các đề xuất kiến trúc cũ hơn.

---

## Bản đồ tài liệu

### `01-product/` — Đặc tả sản phẩm

Tổng quan thư mục: [01-product/README.md](01-product/README.md).

| Tài liệu | Nội dung |
|---|---|
| [00 Bài toán](01-product/00-xac-dinh-bai-toan.md) | Đề bài gốc: bối cảnh, vấn đề, đối tượng, giả định pháp lý, agent làm gì, KPI. Mọi tài liệu trong `01-product/` suy ra từ file này. |
| [01 Project Brief](01-product/01-project-brief.md) | Bối cảnh chuỗi khu đô thị, vấn đề, ai cần thuê chỗ, giải pháp, giá trị, KPI. |
| [02 PRD](01-product/02-prd.md) | Mục tiêu, mô hình tổ chức, tư cách L1–L4, phân loại chỗ đỗ, quy tắc nghiệp vụ và yêu cầu chức năng. |
| [03 Scope](01-product/03-scope.md) | Phạm vi bản demo (3 khu mô phỏng), ngoài phạm vi, nguyên tắc dữ liệu và quyền riêng tư, giả định cần xác nhận. |
| [04 User Stories & AC](01-product/04-user-stories.md) | User story (US-xx) và tiêu chí nghiệm thu Given/When/Then (AC-xx), theo epic. |
| [06 Traceability](01-product/06-traceability.md) | Ma trận User Story → AC → Module → Workflow → use case → màn hình. |

### `01-product/backlog/` — Backlog 3 nhóm × 3 mức ưu tiên

| Tài liệu | Nội dung |
|---|---|
| [README](01-product/backlog/README.md) | Giới thiệu backlog, định nghĩa 3 mức ưu tiên (Ưu tiên 1 / 2 / 3) cho 4 người trong 4 tuần, lịch 4 tuần. |
| [01 Module (FE / BE)](01-product/backlog/01-modules.md) | 14 module frontend/backend, chia theo mức ưu tiên. |
| [02 Workflow AI Agent](01-product/backlog/02-agent-workflows.md) | W0 Supervisor và W1–W7 (LangGraph): bước tất định, LLM, HITL và RAG theo mức ưu tiên. |
| [03 Workflow nền](01-product/backlog/03-background-workflows.md) | N1–N8 chạy bằng worker arq + Redis, không gọi LLM, theo mức ưu tiên. |

### `01-product/ux/` — UX

| Tài liệu | Nội dung |
|---|---|
| [01 User Flow](01-product/ux/01-user-flow.md) | Các luồng nghiệp vụ của bản demo: agent điều phối và worker nền. |
| [Wireframes README](01-product/ux/wireframes/README.md) | Giới thiệu bộ wireframe HTML low-fidelity và cách mở. |
| [Danh mục màn hình](01-product/ux/wireframes/index.html) | Trang mục lục HTML, mở trong trình duyệt để xem mọi wireframe. |

Các wireframe trong `01-product/ux/wireframes/`:
- **Cư dân / chủ chỗ:** [Đăng ký & đồng ý dữ liệu](01-product/ux/wireframes/register.html) · [Chỗ của tôi](01-product/ux/wireframes/owner-home.html) · [Lập lịch chia sẻ](01-product/ux/wireframes/owner-share-schedule.html) · [Báo về sớm](01-product/ux/wireframes/owner-early-return.html) · [Đề xuất hoán đổi](01-product/ux/wireframes/swap-proposal.html) · [Voucher lượt TH3](01-product/ux/wireframes/shophouse-voucher.html)
- **Người thuê:** [Yêu cầu chỗ đỗ](01-product/ux/wireframes/request-parking.html) · [Thỏa thuận điện tử](01-product/ux/wireframes/agreement.html) · [Thanh toán VietQR mock](01-product/ux/wireframes/payment.html) · [Lượt đỗ của tôi](01-product/ux/wireframes/renter-booking.html) · [Báo tranh chấp](01-product/ux/wireframes/dispute-report.html) · [Thông báo](01-product/ux/wireframes/notifications.html)
- **BQL (admin):** [Bảng điều khiển](01-product/ux/wireframes/admin-dashboard.html) · [Duyệt giao dịch HITL](01-product/ux/wireframes/admin-approvals.html) · [Duyệt hoán đổi](01-product/ux/wireframes/admin-swaps.html) · [Ticket tranh chấp](01-product/ux/wireframes/admin-disputes.html) · [Chi tiết ticket](01-product/ux/wireframes/admin-dispute-detail.html) · [Sổ cái](01-product/ux/wireframes/admin-ledger.html) · [Log LPR & hàng chờ OCR](01-product/ux/wireframes/admin-lpr-review.html)

### `02-architecture/` — Kiến trúc

Tổng quan thư mục: [02-architecture/README.md](02-architecture/README.md).

| Tài liệu | Nội dung |
|---|---|
| [01 Architecture Diagram](02-architecture/01-architecture-diagram.md) | Sơ đồ kiến trúc hiện hành, tổng quan hệ thống, luồng một yêu cầu đặt chỗ (W1 → W2) và các thành phần. |
| [02 Tech stack](02-architecture/02-tech-stack.md) | Stack theo từng lớp, các môi trường, rủi ro cần xác nhận, gợi ý chia việc. |

### `05-development/` — Phát triển

Tổng quan thư mục: [05-development/README.md](05-development/README.md).

| Tài liệu | Nội dung |
|---|---|
| [01 Cấu trúc server](05-development/01-server-structure.md) | Cấu trúc thư mục `server/`: module, tầng `agent/`, job nền (theo ADR-0010). |

### `10-adr/` — Quyết định kiến trúc

Tổng quan thư mục: [10-adr/README.md](10-adr/README.md).

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
| [0010](10-adr/ADR-0010-backend-modules-agent-workflows-jobs.md) | Server tổ chức theo module; tầng `agent/` điều phối W0–W7; job N1–N8 là delivery adapter |

### `12-ai/` — Cấu hình AI agent

Tổng quan thư mục: [12-ai/README.md](12-ai/README.md).

| Tài liệu | Nội dung |
|---|---|
| [01 Agent setup](12-ai/01-agent-setup.md) (tiếng Anh) | Cấu hình riêng của Claude Code (`.claude/`, `CLAUDE.md`) và Codex (`.codex/`, `AGENTS.md`, `.agents/skills/`); cài đặt trên macOS / Windows. |

### Thư mục chưa có tài liệu

Các thư mục dưới đây mới có `README.md` mô tả mục đích và gợi ý file nên viết:

[03-design](03-design/README.md) · [04-api](04-api/README.md) · [06-testing](06-testing/README.md) · [07-deployment](07-deployment/README.md) · [08-operations](08-operations/README.md) · [09-security](09-security/README.md) · [11-references](11-references/README.md) · `01-product/ux/ui-design/` (chưa có README)

### `images/` — Ảnh sơ đồ

Ảnh được vẽ lại từ văn bản. Khi ảnh khác văn bản, **văn bản là bản đúng**.

| Ảnh | Được dùng trong |
|---|---|
| [arch-overview](images/ParkSmartAI-arch-overview.png) · [arch-tech-stack](images/ParkSmartAI-arch-tech-stack.png) · [arch-communication](images/ParkSmartAI-arch-communication.png) · [arch-observability](images/ParkSmartAI-arch-observability.png) · [arch-cicd](images/ParkSmartAI-arch-cicd.png) · [arch-backend-folders](images/ParkSmartAI-arch-backend-folders.png) | Kiến trúc AWS: tổng quan, stack, giao tiếp, observability, CI/CD, cây thư mục server |
| [modules](images/ParkSmartAI-modules.png) · [agent-workflows](images/ParkSmartAI-agent-workflows.png) · [background-workflows](images/ParkSmartAI-background-workflows.png) | Các file [backlog](01-product/backlog/README.md) (14 module; W0–W7; N1–N8 theo mô hình chuỗi N khu) |

### `guide/` — Guidebook AI20K (không phải đặc tả dự án)

Bắt đầu từ [README của guidebook](guide/README.md). Tài liệu chung của ban tổ chức, không phải đặc tả của ParkSmart AI.

---

## Cập nhật file này (cho agent)

File này **không** được sinh tự động. Khi thêm, đổi tên hoặc xóa tài liệu trong `docs/`, hoặc khi nội dung chính của một file thay đổi, hãy sửa dòng tương ứng ở đây:

- Mỗi tài liệu là một dòng gồm tiêu đề có link tới file (đường dẫn tương đối), kèm một câu nói tài liệu trả lời câu hỏi gì.
- File mới đặt vào đúng thư mục đánh số, lấy số `NN` kế tiếp trong thư mục đó. Nếu thư mục đang ghi "chưa có tài liệu" thì xóa tên thư mục khỏi dòng đó.
- ADR mới: đăng ký trong bảng ADR ở trên (xem skill `new-adr`).
- Chỉ ghi nội dung chính của tài liệu. Không chép nội dung chi tiết vào đây.
- Mọi link là đường dẫn tương đối. Không sửa `guide/`.
