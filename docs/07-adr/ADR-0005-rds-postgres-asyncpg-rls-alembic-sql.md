# ADR-0005: PostgreSQL + pgvector, SQL-first với asyncpg, RLS theo khu / hộ, Alembic SQL thuần

- **Status**: Accepted
- **Date**: 2026-11-17 · viết lại 2026-11-22 (plan 021: gộp phần liên quan của ADR-0011, 0012, 0013)
- **Liên quan**: [Thiết kế CSDL](../03-design/01-data-model.md) · [ADR-0006](ADR-0006-self-issued-jwt-auth.md) · [ADR-0011](ADR-0011-mvp-simplifications.md) · [ADR-0012](ADR-0012-lean-lightsail-prod-and-team-ci-runner.md) · [ADR-0013](ADR-0013-dev-env-on-ci-runner-and-groq.md)

## Context

- PRD yêu cầu tách dữ liệu theo khu và hộ; BQL chỉ thấy khu mình (BR-17).
- Logic nặng nằm trong SQL (ghép theo giờ, bằng chứng không sửa được, đối soát), nên đội muốn viết SQL tay là chính.
- RAG nội quy (W7) chỉ vài chục tài liệu, không cần vector DB riêng.

## Decision

- **PostgreSQL 16** với `pgvector` (RAG), `pgcrypto`, `btree_gist` (chặn chồng khung giờ). Demo chạy trong container trên máy prod,
  `pg_dump` hằng đêm lên S3 (ADR-0012); dev dùng chung DB trên máy runner CI (ADR-0013). RDS khi có người dùng thật.
- **Truy cập:** asyncpg; SQL nằm trong repository, **luôn tham số `$1, $2…`**, không ghép chuỗi.
- **RLS** trên mọi bảng theo khu hoặc hộ. Mỗi đơn vị công việc mở transaction và đặt `app.user_id`, `app.role`, `app.zone_ids`
  qua `set_config(..., true)`, policy đọc bằng `current_setting`. Nguồn ngữ cảnh: request ← JWT; job `bg` ← `app.role = 'system'` +
  khu trong payload; workflow ← state lúc khởi chạy (+ `app.approver_id` khi resume). Tất cả qua helper `platform.db.unit_of_work(ctx)`.
- **Role:** `parksmart_owner` sở hữu object, `parksmart_migrator` chỉ cho migration, `parksmart_app` cho app (không `BYPASSRLS`).
- **Toàn vẹn bằng ràng buộc DB:** exclusion constraint `tstzrange` trên một ô; bằng chứng chỉ `INSERT`; bước ghi dữ liệu có cột
  UNIQUE `idempotency_key` (`thread_id:step`, mã sự kiện) vì LangGraph chạy lại node khi resume và arq chạy lại job.
- **Migration:** Alembic, nội dung là `op.execute("""SQL""")`, không autogenerate; chỉ CI chạy migrate lên DB dùng chung.
- **Checkpointer LangGraph:** `langgraph-checkpoint-postgres` (psycopg 3), pool nhỏ riêng, schema `agent`.

## Consequences

- **Tích cực:** bảo vệ hai lớp (code + RLS), quên `WHERE` cũng không lộ khu khác; quy tắc quan trọng do DB bảo đảm.
- **Tiêu cực:** hai driver, ba process cùng mở pool nên phải chia số kết nối; role `system` cần policy và test riêng; RLS khó debug;
  SQL tay cần test tích hợp với Postgres thật.

## Observability Impact

- Span mỗi truy vấn: `db.system=postgresql`, `db.operation`; **không** ghi giá trị tham số (có thể chứa biển số).
- Metric USE cho pool (nhãn `pool` chỉ `app` / `checkpointer`): `db_client_connections_in_use`, `db_client_connections_max`, `db_client_connection_wait_seconds`.
