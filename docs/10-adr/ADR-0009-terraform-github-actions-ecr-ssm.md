# ADR-0009: Hạ tầng bằng Terraform; CI/CD bằng GitHub Actions → ECR → EC2 qua SSM

- **Status**: Accepted
- **Date**: 2026-11-17
- **Liên quan**: [ADR-0001](ADR-0001-monorepo-client-server.md) · [ADR-0002](ADR-0002-react-vite-spa-on-s3-cloudfront.md) · [ADR-0004](ADR-0004-fastapi-langgraph-arq-on-ec2-docker-compose.md) · [ADR-0008](ADR-0008-opentelemetry-lgtm-on-dedicated-ec2.md)

## Context

- **Hạ tầng gồm:** VPC, 2 EC2 (app, observability), RDS, S3, CloudFront, ECR, IAM role, SSM Parameter Store, AWS Budgets.
- **Yêu cầu:** đội 4 người, 4 tuần, dùng credit AWS. Cần dựng lại được nếu hỏng, và **xóa sạch sau demo** để không tiếp tục tốn credit.
- **An toàn khi deploy:** không muốn mở cổng SSH hay giữ private key trong GitHub.

## Decision

**Terraform** trong thư mục `infra/`
- State lưu trên S3, khóa bằng DynamoDB.
- Module gồm: `network`, `ecr`, `rds`, `ec2_app`, `ec2_observability`, `client_cdn` (S3 + CloudFront + OAC), `iam`, `budgets`.
- Hai môi trường: `local` (chỉ docker compose, không cần Terraform) và `demo`. Không có staging.

**GitHub Actions**
- **Xác thực vào AWS** bằng **OIDC** (không có access key lâu dài). Role của GitHub chỉ có quyền: push ECR, gửi lệnh SSM, sync S3, invalidate CloudFront.
- **Khi mở PR:** ruff + pytest (server; test tích hợp chạy với Postgres trong service container), lint + typecheck + test (client), kiểm tra client sinh từ OpenAPI không lệch, `terraform plan` nếu `infra/**` thay đổi.
- **Khi merge vào `main`:**
  - **Server:** build image → push ECR (tag theo git SHA) → `aws ssm send-command` cho EC2 app chạy `alembic upgrade head`, rồi `docker compose pull && up -d` → health check `/api/v1/health`.
  - **Client:** `vite build` → `aws s3 sync` → invalidate CloudFront.
  - **Hạ tầng:** `terraform apply` chạy tay qua `workflow_dispatch`, có bước duyệt (environment protection).

**Bí mật**
- Lưu trong SSM Parameter Store (SecureString): khóa JWT, mật khẩu DB.
- EC2 đọc qua instance role khi khởi động container. Không commit file `.env` thật.

**Truy cập máy**
- Chỉ qua **SSM Session Manager**. Security group không mở cổng 22.

**Kiểm soát chi phí**
- AWS Budgets cảnh báo ở 50% / 80% / 100% ngân sách.
- Lệnh `terraform destroy` được ghi trong runbook để dọn sau demo.

## Consequences

**Tích cực**
- Hạ tầng tái tạo được, review được qua PR, xóa sạch được.
- Deploy không cần SSH; mọi lần deploy để lại log trong GitHub Actions và SSM.

**Tiêu cực**
- Tốn khoảng 2–3 ngày công lúc đầu cho Terraform và pipeline.
- Deploy bằng `docker compose up` trên một máy gây gián đoạn vài giây. Chấp nhận được cho demo.
- Nếu migration lỗi giữa chừng thì phải xử lý tay. Quy ước: chỉ viết migration thêm mới, không xóa cột trong giai đoạn demo.

## Observability Impact

- **Annotation trên Grafana:** mỗi lần deploy, pipeline gửi annotation kèm git SHA và tên service. Nhìn dashboard là biết thay đổi độ trễ hay lỗi bắt đầu sau lần deploy nào.
- **Tag version:** thuộc tính `service.version` trong mọi span và metric bằng git SHA của image (khớp ADR-0001).
- **Health check:** endpoint health trả về trạng thái kết nối DB, Redis và Bedrock. Pipeline fail nếu health check không đạt.
