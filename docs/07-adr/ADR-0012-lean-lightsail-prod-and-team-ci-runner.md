# ADR-0012: Hạ tầng cho bản demo: prod trên một Lightsail, deploy kéo từ ECR, runner CI riêng trên EC2

- **Status**: Accepted
- **Date**: 2026-11-21
- **Liên quan**: [ADR-0004](ADR-0004-fastapi-langgraph-arq-on-ec2-docker-compose.md) · [0005](ADR-0005-rds-postgres-asyncpg-rls-alembic-sql.md) · [0008](ADR-0008-opentelemetry-lgtm-on-dedicated-ec2.md) · [0009](ADR-0009-terraform-github-actions-ecr-ssm.md) · [infra/lightsail](../../infra/lightsail/README.md) · [infra/ci-runner](../../infra/ci-runner/README.md)

## Context

- Kiến trúc ở ADR-0004/0005/0008/0009 (EC2 app, RDS, EC2 LGTM riêng, Terraform, deploy qua SSM) tốn khoảng 190–210 USD/tháng.
  Đội chạy demo trên tài khoản AWS cá nhân (gói Free, ~131 USD credit), nên cần khoảng 25 USD/tháng.
- Repo thuộc org của BTC: thành viên không thêm được secret, deploy key hay GitHub App. BTC (2026-11-20) cho phép deploy lên AWS riêng
  qua GitHub Actions / registry; runner đăng ký qua Phoenix, giữ `runs-on: self-hosted`, không chạy runner trên laptop cá nhân.
- Runner chung của BTC xếp hàng FIFO; `ubuntu-latest` bị chặn vì org chạm hạn mức chi tiêu.
- Code chưa có OTel, chưa bật `arq` và `alembic`; client chưa khởi tạo.

## Decision

**Prod:** một Lightsail `small_3_0` (2 GB, 12 USD) + static IP chạy docker compose: caddy, api, redis, postgres (`pgvector/pgvector:pg16`);
worker và agent-worker nằm sau profile `workers`, bật khi có `arq`. HTTPS bằng Caddy + Let's Encrypt cho `<ip>.sslip.io`. Firewall chỉ mở
80/443 và 22 cho SSH trên trình duyệt của Lightsail; không mở 5432 / 6379.

**Deploy kéo (pull), không đẩy:** merge `main` → `deploy.yml` lấy quyền AWS bằng **OIDC** (role chỉ tin `ref:refs/heads/main` của P-142) →
build image amd64 → tải bundle cấu hình (`infra/lightsail/`) lên S3 `releases/sha-….tgz` → push ECR `:sha-…` rồi `:main`. Trên máy, systemd timer
2 phút chạy `deploy.py`: thấy `:main` trỏ sang tag mới thì pull, chạy `alembic upgrade head` nếu image có, `up --wait`, gọi
`/api/v1/health` qua HTTPS; lỗi thì đánh dấu tag failed và chạy lại tag cũ. Không có secret trong GitHub, không cần GitHub với tới máy.

**Quyền AWS của máy prod:** SSM hybrid activation gắn role `parksmart-lightsail` (pull ECR, đọc `releases/`, ghi `backups/`); SSM agent tự
xoay khóa tạm thời. Không có access key lâu dài.

**Runner CI:** EC2 `t3.small` amd64 riêng của đội, đăng ký qua Phoenix với label `p142`; `ci.yml` và `deploy.yml` dùng
`runs-on: [self-hosted, p142]`. Không inbound, vào bằng SSM Session Manager; role của máy chỉ có SSM. EventBridge Scheduler bật 08:00, tắt 22:00.

**Dữ liệu:** Postgres chạy trong container trên cùng máy (thay RDS); `pg_dump -Fc` hằng đêm lên S3, giữ 7 ngày. RLS, asyncpg, Alembic
SQL thuần của ADR-0005 giữ nguyên.

**Hạ tầng dưới dạng code:** tạm thời là AWS CLI ghi trong runbook, chưa dùng Terraform (SCRUM-38 làm sau nếu cần). AWS Budget 25 USD.

## Consequences

**Tích cực:** ~26 USD/tháng thay cho ~200; không secret nào trong GitHub; máy prod không mở cổng cho CI; rollback tự động về tag trước;
runner riêng không phải xếp hàng chung và build đúng kiến trúc của prod.

**Tiêu cực:** một máy là điểm hỏng duy nhất, DB cùng máy với app (mất máy thì quay về backup đêm trước, RPO ≤ 24 giờ); 2 GB RAM giới hạn
số worker và kích thước Postgres; deploy chậm tối đa ~2 phút sau khi push và kết quả deploy không hiện trên Actions (xem `journalctl`);
rollback không đảo ngược migration (migration chỉ đi tiến); runner tắt ban đêm nên CI ngoài giờ phải chờ; hạ tầng tạo tay bằng CLI dễ lệch
so với runbook.

**Quay lại ADR gốc khi nào:** có người dùng thật hoặc cần SLA → RDS + EC2/ECS theo ADR-0004/0005, Terraform theo ADR-0009; có OTel → gửi
lên Grafana Cloud free tier trước khi dựng LGTM riêng (ADR-0008).

## Alternatives considered

- **Kiến trúc gốc (EC2 + RDS + EC2 LGTM)**: ~200 USD/tháng, vượt credit.
- **Đẩy (push) bằng SSH từ Actions**: cần private key làm secret trong GitHub, đội không thêm được.
- **Đẩy bằng SSM Run Command**: SSM cho máy ngoài EC2 cần tier advanced (~5 USD/máy/tháng) để mở shell, và role OIDC phải có quyền chạy
  lệnh trên máy prod; kéo từ ECR đơn giản hơn và quyền hẹp hơn.
- **Runner chung của BTC**: rẻ nhất (~13 USD/tháng tổng), nhưng xếp hàng FIFO và không biết kiến trúc CPU của máy.
- **Runner ARM `t4g.small`** (plan 012): rẻ hơn chút, nhưng phải cross-build sang amd64 cho Lightsail.

## Observability Impact

- Chưa có OTel trong code nên chưa có trace / metric; log container ở `json-file` (10 MB × 3) và log Caddy dạng JSON trên stdout.
- Log deploy và backup nằm trong journald (`journalctl -u parksmart-deploy`, `-u parksmart-backup`).
- Khi thêm OTel: collector gửi thẳng lên Grafana Cloud (OTLP), không thêm container LGTM vào máy 2 GB. Không đưa PII, API key vào log / span.

## Cần xác nhận

- BTC cho phép label `p142` và giới hạn runner cho riêng repo P-142 (runner group) không.
- Lightsail trên gói Free của tài khoản có tạo được `small_3_0` không (kiểm tra ở bước 5 của plan 015).
