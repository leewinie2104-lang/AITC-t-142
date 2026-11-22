# ADR-0012: Hạ tầng demo: prod trên một Lightsail, deploy kéo từ ECR qua OIDC, runner CI riêng trên EC2

- **Status**: Accepted (gộp ADR-0009 ngày 2026-11-22, plan 021)
- **Date**: 2026-11-21 · viết lại 2026-11-22
- **Liên quan**: [ADR-0004](ADR-0004-fastapi-langgraph-arq-on-ec2-docker-compose.md) · [ADR-0005](ADR-0005-rds-postgres-asyncpg-rls-alembic-sql.md) · [ADR-0008](ADR-0008-opentelemetry-lgtm-on-dedicated-ec2.md) · [ADR-0013](ADR-0013-dev-env-on-ci-runner-and-groq.md) · [infra/lightsail](../../infra/lightsail/README.md) · [infra/ci-runner](../../infra/ci-runner/README.md)

## Context

- Thiết kế gốc (EC2 app, RDS, EC2 LGTM, Terraform, deploy qua SSM) tốn ~200 USD/tháng; tài khoản AWS của đội chỉ có ~131 USD credit.
- Repo thuộc org của BTC: thành viên không thêm được secret, deploy key hay GitHub App. BTC cho deploy lên AWS riêng qua GitHub
  Actions, runner đăng ký qua Phoenix (`runs-on: self-hosted`), không chạy runner trên laptop.

## Decision

- **Prod:** một Lightsail `small_3_0` (2 GB) + static IP chạy docker compose (ADR-0004); HTTPS bằng Caddy + Let's Encrypt cho
  `<ip>.sslip.io`. Firewall chỉ mở 80/443 và 22 cho SSH trên trình duyệt của Lightsail.
- **Deploy kéo:** merge `main` → `deploy.yml` lấy quyền AWS bằng **OIDC** (role chỉ tin nhánh `main` của repo) → build image amd64 →
  bundle cấu hình lên S3 → push ECR `:sha-…` rồi `:main`. Timer 2 phút trên máy chạy `deploy.py`: tag mới thì pull, migrate, khởi động,
  gọi `/api/v1/health`; lỗi thì quay về tag cũ. GitHub không giữ secret, không kết nối vào máy.
- **Quyền của máy prod:** SSM hybrid activation gắn role `parksmart-lightsail` (pull ECR, đọc bundle, ghi backup); khóa tạm tự xoay.
- **Runner CI:** EC2 `t3.small` amd64, label `team-142`, không mở cổng vào (SSM Session Manager); tự bật 10:00, tắt 02:00 hôm sau.
- **Dữ liệu:** Postgres trong container cùng máy; `pg_dump` hằng đêm lên S3, giữ 7 ngày.
- **Hạ tầng bằng AWS CLI theo runbook** trong `infra/`, chưa Terraform. AWS Budgets cảnh báo chi phí hằng tháng.

## Consequences

- **Tích cực:** ~26 USD/tháng; không secret trong GitHub; máy prod không mở cổng cho CI; tự quay về bản cũ khi deploy lỗi; runner
  riêng không xếp hàng chung và build đúng kiến trúc của prod.
- **Tiêu cực:** một máy là điểm hỏng duy nhất, mất máy thì về backup đêm trước; 2 GB RAM giới hạn worker và Postgres; kết quả deploy
  không hiện trên Actions (xem `journalctl`); rollback không đảo ngược migration; CI ngoài 10:00–02:00 phải chờ.
- **Quay lại thiết kế gốc khi:** có người dùng thật hoặc cần SLA (RDS, Terraform, nhiều máy).

## Alternatives considered

- Đẩy bằng SSH từ Actions: cần private key làm secret trong GitHub. SSM Run Command: máy ngoài EC2 cần tier advanced (~5 USD/tháng).
- Runner chung của BTC: phải xếp hàng, không biết kiến trúc CPU. Runner ARM: phải cross-build sang amd64.

## Observability Impact

- Log container `json-file` (10 MB × 3), log Caddy JSON, log deploy / backup trong journald. OTel gửi lên Grafana Cloud (ADR-0008).
- Mỗi lần deploy ghi git SHA; `service.version` của span và metric = SHA của image.
