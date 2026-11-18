# 07-deployment — Triển khai

> **Thư mục này trả lời:** dựng môi trường demo trên AWS thế nào, CI/CD chạy ra sao, và gỡ xuống sau demo bằng cách nào.

## Tổng quan

**Chưa có tài liệu.** Theo [ADR-0009](../10-adr/ADR-0009-terraform-github-actions-ecr-ssm.md): hạ tầng bằng Terraform (`infra/`), CI/CD bằng GitHub Actions → ECR → EC2 qua SSM.

| Môi trường | Thành phần |
|---|---|
| `local` | docker compose: api, worker, agent-worker, redis, postgres (pgvector), caddy; client chạy `vite dev`; LLM mock mặc định |
| `demo` | CloudFront + S3 (client); EC2 app; EC2 observability; RDS. Dựng bằng Terraform, xóa bằng `terraform destroy` sau demo |

Nguồn: [Tech stack — Môi trường](../02-architecture/02-tech-stack.md#môi-trường) · ảnh [arch-cicd](../images/ParkSmartAI-arch-cicd.png).

## Luồng triển khai

PR checks → merge `main` → build image, đẩy ECR → SSM chạy migrate → `docker compose up` → health check. Client: build → S3 → invalidate CloudFront. Terraform apply cần duyệt.

## Nên có

| File gợi ý | Nội dung |
|---|---|
| `01-aws-setup.md` | Tài khoản, region (chờ chốt theo ADR-0007), SSO, quyền OIDC cho GitHub Actions |
| `02-terraform.md` | Cấu trúc `infra/`, biến, cách apply / destroy |
| `03-ci-cd.md` | Các workflow GitHub Actions, secret, cách rollback |
| `04-demo-day-checklist.md` | Việc cần làm trước / sau Demo Day, gồm `terraform destroy` |

## Lưu ý

- Secret lưu ở SSM Parameter Store, không đưa vào repo hay log.
- Một EC2 app là điểm hỏng duy nhất (rủi ro R5): giữ cách dựng lại nhanh bằng Terraform.
- Thêm file thì cập nhật bảng trên và [docs/README.md](../README.md).
