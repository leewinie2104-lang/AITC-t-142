# ADR-0013: Môi trường dev: Postgres + Redis dùng chung trên máy runner CI qua Tailscale

- **Status**: Accepted
- **Date**: 2026-11-21 · viết lại 2026-11-22 (plan 021: phần LLM dev chuyển sang ADR-0007)
- **Liên quan**: [ADR-0005](ADR-0005-rds-postgres-asyncpg-rls-alembic-sql.md) · [ADR-0007](ADR-0007-claude-via-amazon-bedrock.md) · [ADR-0012](ADR-0012-lean-lightsail-prod-and-team-ci-runner.md) · [infra/dev-db](../../infra/dev-db/README.md) · plan 017

## Context

- Mỗi dev tự chạy Postgres riêng nên đội không có dữ liệu chung để thử luồng end-to-end.
- Máy runner CI (`t3.small`, ADR-0012) phần lớn thời gian rảnh giữa các job.
- Redis free bên ngoài giới hạn lệnh hoặc kết nối, trong khi worker arq poll Redis liên tục.

## Decision

- **Postgres 16 + pgvector và Redis 7** chạy trên chính máy runner, compose riêng `infra/dev-db/` (cổng 15432 / 16379, không đụng
  cổng 5432 của job CI). Giới hạn RAM: Postgres 512 MB, Redis 128 MB (`noeviction` để arq không mất job).
- **Truy cập qua Tailscale** (gói free): máy và laptop dev cùng một tailnet; security group vẫn không có rule inbound.
- **Role theo ADR-0005**; **chỉ CI migrate**: job `migrate-dev-db` chạy `alembic upgrade head` sau khi merge `dev`. Dev thử migration
  trên Postgres local trước khi mở PR.
- **Chỉ dữ liệu giả.** Mật khẩu sinh trên máy (`infra/dev-db/.env`, chmod 600), chia qua Bitwarden, không vào git / Jira / chat.
- `docker-compose.yml` ở gốc repo giữ làm mẫu cho prod (ADR-0012), không còn là môi trường dev chính. LLM dev: Groq (ADR-0007).

## Consequences

- **Tích cực:** không thêm chi phí; không bị giới hạn quota như dịch vụ free; cùng image Postgres với prod nên RLS, role, extension giống nhau.
- **Tiêu cực:** DB dev chỉ chạy khi máy bật (10:00–02:00 giờ VN); 2 GB RAM chia với CI; job CI (kể cả từ PR) có quyền với DB dev qua
  Docker; chưa backup (mất máy thì seed lại).

## Alternatives considered

- Neon free: có branch theo PR nhưng giới hạn 0.5 GB, nằm ngoài AWS. Redis Cloud / Upstash free: giới hạn không hợp arq.
- SSM port forwarding: mỗi dev cần IAM user và plugin. Nâng máy lên 8 GB: ~40 USD/tháng, chỉ khi CI chậm vì thiếu RAM.

## Observability Impact

- Không thêm metric hay span. DSN được che mật khẩu trước khi ghi log (`platform/db/session.py`).

## Cần xác nhận

- Có cần kéo dài lịch bật máy (thêm ~2–3 USD/tháng) hay backup hằng đêm (role máy hiện chỉ có SSM) không.
