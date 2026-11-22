# ADR-0012: Hạ tầng cho bản demo: prod trên một Lightsail, deploy kéo từ ECR, runner CI riêng trên EC2

- **Status**: Accepted
- **Date**: 2026-11-21
- **Liên quan**: [ADR-0004](ADR-0004-fastapi-langgraph-arq-on-ec2-docker-compose.md) · [0005](ADR-0005-rds-postgres-asyncpg-rls-alembic-sql.md) · [0008](ADR-0008-opentelemetry-lgtm-on-dedicated-ec2.md) · [0009](ADR-0009-terraform-github-actions-ecr-ssm.md) · [infra/lightsail](../../infra/lightsail/README.md) · [infra/ci-runner](../../infra/ci-runner/README.md)

## Context

- Kiến trúc ở ADR-0004/0005/0008/0009 (EC2 app, RDS, EC2 LGTM riêng, Terraform, deploy qua SSM) tốn khoảng 200 USD/tháng.
  Đội chạy demo trên tài khoản AWS cá nhân (gói Free, ~131 USD credit), nên cần khoảng 25 USD/tháng.
- Repo thuộc org của BTC: thành viên không thêm được secret, deploy key hay GitHub App. BTC (2026-11-20) cho deploy lên AWS riêng
  qua GitHub Actions / registry; runner đăng ký qua Phoenix, giữ `runs-on: self-hosted`, không chạy runner trên laptop cá nhân.
- Runner chung của BTC phải xếp hàng. Code chưa có OTel, chưa bật `arq` và `alembic`; client chưa khởi tạo.

## Decision

**Prod:** một Lightsail `small_3_0` (2 GB, 12 USD) + static IP chạy docker compose: caddy, api, redis, postgres (pgvector);
worker sau profile `workers`, bật khi có `arq`. HTTPS bằng Caddy + Let's Encrypt cho `<ip>.sslip.io` (không cần mua domain).
Firewall chỉ mở 80/443 và 22 cho SSH trên trình duyệt của Lightsail.

**Deploy kéo (pull):** merge `main` → `deploy.yml` lấy quyền AWS bằng **OIDC** (GitHub cấp token ngắn hạn, role chỉ tin nhánh `main`
của P-142) → build image amd64 → bundle cấu hình lên S3 → push ECR `:sha-…` rồi `:main`. Trên máy, timer 2 phút chạy `deploy.py`:
thấy tag mới thì pull, migrate (nếu image có alembic), khởi động, gọi `/api/v1/health`; lỗi thì quay về tag cũ.
Không secret nào trong GitHub, GitHub không cần kết nối vào máy.

**Quyền AWS của máy prod:** SSM hybrid activation (đăng ký máy ngoài EC2 với SSM) gắn role `parksmart-lightsail`: pull ECR, đọc
bundle, ghi backup. Khóa tạm thời tự xoay, không access key lâu dài.

**Runner CI:** EC2 `t3.small` amd64 của đội, đăng ký qua Phoenix ở cấp repo P-142, label `team-142`; `ci.yml` và `deploy.yml` dùng
`runs-on: [self-hosted, team-142]`. Không mở cổng vào (dùng SSM Session Manager), role chỉ có SSM; tự bật 10:00, tắt 02:00 hôm sau.

**Dữ liệu:** Postgres trong container cùng máy (thay RDS); `pg_dump` hằng đêm lên S3, giữ 7 ngày. RLS, asyncpg, Alembic giữ nguyên.
Hạ tầng tạo bằng AWS CLI theo runbook, chưa Terraform; AWS Budget cảnh báo chi phí hằng tháng.

## Consequences

**Tích cực:** ~26 USD/tháng thay cho ~200; không secret trong GitHub; máy prod không mở cổng cho CI; tự quay về bản cũ khi deploy lỗi;
runner riêng không xếp hàng chung và build đúng kiến trúc của prod.

**Tiêu cực:** một máy là điểm hỏng duy nhất, DB cùng máy (mất máy thì về backup đêm trước); 2 GB RAM giới hạn worker và Postgres;
kết quả deploy không hiện trên Actions (xem `journalctl`); rollback không đảo ngược migration; CI ngoài 10:00–02:00 phải chờ.

**Quay lại ADR gốc khi:** có người dùng thật hoặc cần SLA (RDS, Terraform); có OTel thì gửi lên Grafana Cloud free tier trước (ADR-0008).

## Alternatives considered

- **Kiến trúc gốc (EC2 + RDS + EC2 LGTM)**: ~200 USD/tháng, vượt credit.
- **Đẩy bằng SSH từ Actions**: cần private key làm secret trong GitHub, đội không thêm được.
- **Đẩy bằng SSM Run Command**: máy ngoài EC2 cần tier advanced (~5 USD/tháng) và role OIDC phải được chạy lệnh trên prod.
- **Runner chung của BTC**: rẻ nhất, nhưng xếp hàng và không biết kiến trúc CPU. **Runner ARM** (plan 012): phải cross-build sang amd64.

## Observability Impact

- Chưa có OTel nên chưa có trace / metric; log container `json-file` (10 MB × 3), log Caddy dạng JSON; log deploy / backup trong journald.
- Khi thêm OTel: gửi thẳng lên Grafana Cloud, không thêm LGTM vào máy 2 GB. Không đưa PII, API key vào log / span.

## Cần xác nhận

- Gói Free của tài khoản có tạo được Lightsail `small_3_0` không (kiểm tra ở bước 5b của plan 015).
