# ADR-0009: Hạ tầng bằng Terraform; CI/CD bằng GitHub Actions → ECR → EC2 qua SSM

- **Status**: Accepted
- **Date**: 2026-11-17
- **Liên quan**: [ADR-0001](ADR-0001-monorepo-client-server.md) · [ADR-0002](ADR-0002-react-vite-spa-on-s3-cloudfront.md) · [ADR-0004](ADR-0004-fastapi-langgraph-arq-on-ec2-docker-compose.md) · [ADR-0008](ADR-0008-opentelemetry-lgtm-on-dedicated-ec2.md)

## Context

- Hạ tầng: VPC, 2 EC2 (app, observability), RDS, S3, CloudFront, ECR, IAM role, SSM Parameter Store, AWS Budgets.
- Đội 4 người, 4 tuần, credit AWS: cần dựng lại được khi hỏng và **xóa sạch sau demo**. Không muốn mở SSH hay giữ private key trong GitHub.

## Decision

- **Terraform** trong `infra/`: state trên S3, khóa bằng DynamoDB; module `network`, `ecr`, `rds`, `ec2_app`, `ec2_observability`,
  `client_cdn` (S3 + CloudFront + OAC), `iam`, `budgets`. Môi trường `local` (chỉ docker compose) và `demo`; không có staging.
- **GitHub Actions** xác thực AWS bằng **OIDC** (không access key lâu dài); role chỉ có quyền push ECR, gửi lệnh SSM, sync S3, invalidate CloudFront.
  - **PR:** ruff + pytest (Postgres trong service container), lint + typecheck + test client, kiểm client sinh từ OpenAPI không lệch, `terraform plan` khi `infra/**` đổi.
  - **Merge `main`:** server build image → ECR (tag git SHA) → `ssm send-command`: `alembic upgrade head`, `docker compose pull && up -d` → health
    check `/api/v1/health`; client `vite build` → `s3 sync` → invalidate CloudFront; `terraform apply` chạy tay qua `workflow_dispatch` có bước duyệt.
- **Bí mật** trong SSM SecureString (khóa JWT, mật khẩu DB); EC2 đọc qua instance role; không commit `.env` thật.
- **Truy cập máy** chỉ qua SSM Session Manager; security group không mở cổng 22.
- **Chi phí:** AWS Budgets cảnh báo 50% / 80% / 100%; `terraform destroy` ghi trong runbook để dọn sau demo.

## Consequences

**Tích cực**
- Hạ tầng tái tạo được, review qua PR, xóa sạch được; deploy không cần SSH, mọi lần deploy có log trong Actions và SSM.

**Tiêu cực**
- ~2–3 ngày công ban đầu cho Terraform và pipeline; `docker compose up` trên một máy gián đoạn vài giây (chấp nhận cho demo).
- Migration lỗi giữa chừng phải xử lý tay; quy ước chỉ thêm mới, không xóa cột trong giai đoạn demo.

## Observability Impact

- Mỗi lần deploy gửi annotation Grafana kèm git SHA và tên service, nhìn dashboard biết thay đổi bắt đầu sau lần deploy nào.
- `service.version` trong mọi span và metric = git SHA của image (khớp ADR-0001).
- Health check trả trạng thái kết nối DB, Redis, Bedrock; pipeline fail nếu không đạt.
