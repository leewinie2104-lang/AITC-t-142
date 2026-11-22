# 05-deployment — Triển khai

> **Thư mục này trả lời:** dựng môi trường demo trên AWS thế nào, CI/CD chạy ra sao, và gỡ xuống sau demo bằng cách nào.

## Tổng quan

Theo [ADR-0012](../07-adr/ADR-0012-lean-lightsail-prod-and-team-ci-runner.md) (đã gộp ADR-0009): hạ tầng tạo bằng AWS CLI theo runbook trong `infra/`, chưa Terraform;
CI chạy trên runner riêng `team-142`; máy prod tự kéo image từ ECR. Dev theo [ADR-0013](../07-adr/ADR-0013-dev-env-on-ci-runner-and-groq.md).

| Môi trường | Thành phần |
|---|---|
| `dev` | api / worker trên máy dev; Postgres + Redis dùng chung trên máy runner CI qua Tailscale ([infra/dev-db](../../infra/dev-db/README.md)); LLM qua Groq |
| `local` | docker compose ở gốc repo (mẫu cho demo/prod): api, worker, agent-worker, redis, postgres (pgvector) |
| `demo` | Một Lightsail: caddy, api, redis, postgres ([infra/lightsail](../../infra/lightsail/README.md)); `pg_dump` hằng đêm lên S3 |

Nguồn: [Tech stack — Môi trường](../02-architecture/02-tech-stack.md#môi-trường) · sơ đồ [CI/CD](../02-architecture/diagrams/cicd.html).

## Luồng triển khai

PR checks trên runner `team-142` → merge `dev` → job `migrate-dev-db` migrate DB dev. Merge `main` → OIDC → build image → ECR `:main`
→ trên Lightsail, timer 2 phút thấy tag mới thì pull, migrate, `up --wait`, gọi `/api/v1/health`; lỗi thì quay về tag cũ
(chi tiết: [infra/lightsail](../../infra/lightsail/README.md)).

## Tài liệu

| File | Nội dung |
|---|---|
| [01-db-preprod-checklist.md](01-db-preprod-checklist.md) | Checklist CSDL trước production: schema, bảo mật/riêng tư, vận hành (thiết kế ở [03-design](../03-design/README.md)) |

## Nên có thêm

| File gợi ý | Nội dung |
|---|---|
| `02-aws-setup.md` | Tài khoản, region, quyền OIDC cho GitHub Actions (hiện ở runbook `infra/*/README.md`) |
| `04-ci-cd.md` | Các workflow GitHub Actions, secret, cách rollback |
| `05-demo-day-checklist.md` | Việc cần làm trước / sau Demo Day, gồm gỡ Lightsail và runner |

## Lưu ý

- Secret không đưa vào repo hay log: prod trong `/opt/parksmart/.env` (chmod 600), CI trong GitHub secrets, dev qua Bitwarden.
- Một Lightsail là điểm hỏng duy nhất (rủi ro R5): giữ runbook dựng lại và backup `pg_dump` trên S3.
- Thêm file thì cập nhật bảng trên và [docs/README.md](../README.md).
