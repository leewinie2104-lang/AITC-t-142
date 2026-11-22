# ADR-0013: Môi trường dev: Postgres + Redis dùng chung trên máy runner CI (Tailscale), LLM dev qua Groq

- **Status**: Accepted
- **Date**: 2026-11-21
- **Liên quan**: [ADR-0004](ADR-0004-fastapi-langgraph-arq-on-ec2-docker-compose.md) · [0005](ADR-0005-rds-postgres-asyncpg-rls-alembic-sql.md) · [0007](ADR-0007-claude-via-amazon-bedrock.md) · [0012](ADR-0012-lean-lightsail-prod-and-team-ci-runner.md) · [infra/dev-db](../../infra/dev-db/README.md) · plan 017 · **Thay một phần** 0004, 0005, 0007 (chỉ môi trường dev)

## Context

- Mỗi dev tự chạy Postgres trong docker compose, nên đội không có dữ liệu chung để thử luồng end-to-end.
- Máy EC2 `parksmart-ci-runner` (t3.small, ~14 USD/tháng, ADR-0012) phần lớn thời gian rảnh giữa các job CI.
- Dịch vụ free bên ngoài có giới hạn khó chịu: Redis free giới hạn lệnh hoặc kết nối, trong khi worker arq poll Redis liên tục.
- Credit AWS cần giữ cho CI và bản demo; key OpenAI tốn tiền mỗi lần dev thử.

## Decision

**Postgres 16 + pgvector và Redis 7 dùng chung** chạy trên chính máy runner CI, compose riêng `infra/dev-db/` (cổng 15432 / 16379,
không đụng compose của job CI ở 5432). Giới hạn RAM: Postgres 512 MB, Redis 128 MB (`noeviction` để arq không mất job).

**Truy cập qua Tailscale** (gói free): máy và laptop dev cùng một tailnet. Security group vẫn không có rule inbound nào.

**Role theo ADR-0005:** `parksmart_owner` (NOLOGIN, sở hữu object), `parksmart_migrator` (chỉ CI), `parksmart_app` (app, không
`BYPASSRLS`). **Chỉ CI migrate**: job `migrate-dev-db` chạy `alembic upgrade head` sau khi merge `dev`. Dev thử migration trên
Postgres local trước khi mở PR.

**LLM khi dev: Groq** qua API tương thích OpenAI (`OPENAI_BASE_URL`), không đổi code gọi `get_llm`. Unit test và CI không gọi LLM thật.
Claude qua Bedrock (ADR-0007) để dành cho demo. Trace LLM: LangSmith free, mỗi dev một project.

`docker-compose.yml` ở gốc repo giữ lại làm mẫu cho demo/prod (ADR-0012), không còn là môi trường dev chính.

## Consequences

**Tích cực:** không thêm chi phí AWS; không giới hạn quota như dịch vụ free; cùng image Postgres với prod nên RLS, role và extension
giống nhau; LLM dev miễn phí.

**Tiêu cực:** DB dev chỉ chạy khi máy bật (10:00 đến 02:00 sáng hôm sau, giờ VN); 2 GB RAM chia với CI; mọi job CI (kể cả từ PR) có quyền với DB dev qua
Docker, nên **chỉ được chứa dữ liệu giả**; chưa backup (mất máy thì seed lại); Groq free có rate limit theo ngày, eval lớn có thể chạm.

**Bảo mật và quan sát:** mật khẩu sinh trên máy (`infra/dev-db/.env`, chmod 600), chia qua Bitwarden, không vào git / Jira / chat;
DSN được che mật khẩu trước khi ghi log (`platform/db/session.py`). Không thêm metric hay span.

## Alternatives considered

- **Neon free**: có branch theo PR, nhưng giới hạn 0.5 GB và DB nằm ngoài AWS; máy runner đã trả tiền nên dùng luôn.
- **Redis Cloud / Upstash free**: giới hạn kết nối hoặc số lệnh, không hợp với arq poll liên tục.
- **SSM port forwarding thay Tailscale**: mỗi dev cần IAM user, AWS CLI và plugin, khó với người mới.
- **Nâng máy lên `m7i-flex.large`** (8 GB): ~40 USD/tháng, chỉ làm khi CI bị chậm vì thiếu RAM.

## Cần xác nhận

- Lịch bật máy có cần kéo dài (ví dụ 07:00–24:00, thêm ~2–3 USD/tháng) không.
- Backup hằng đêm (`pg_dump` lên S3) có cần không, vì role của máy hiện chỉ có SSM.
