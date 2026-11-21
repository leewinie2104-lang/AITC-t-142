# ADR-0005: RDS PostgreSQL + pgvector, SQL-first với asyncpg, RLS theo khu/hộ, Alembic SQL thuần

- **Status**: Accepted · **Partly superseded by [ADR-0011](ADR-0011-mvp-simplifications.md) (2026-11-18)**: `outbox`, `idempotency_keys`, sổ cái chuỗi hash không có trong demo 23 bảng (thay bằng cột UNIQUE `idempotency_key` từng bảng và `consent_record`); RLS, asyncpg, Alembic giữ nguyên · **[ADR-0012](ADR-0012-lean-lightsail-prod-and-team-ci-runner.md)**: demo dùng Postgres trong container thay RDS, `pg_dump` hằng đêm lên S3 · **[ADR-0013](ADR-0013-dev-env-on-ci-runner-and-groq.md)**: DB dev dùng chung trên máy runner CI, chỉ CI migrate
- **Date**: 2026-11-17 (cập nhật cùng ngày: ngữ cảnh RLS cho job và workflow ngoài HTTP, [ADR-0010](ADR-0010-backend-modules-agent-workflows-jobs.md))
- **Liên quan**: [PRD §9](../01-product/02-prd.md#9-yêu-cầu-phi-chức-năng) · [ADR-0004](ADR-0004-fastapi-langgraph-arq-on-ec2-docker-compose.md) · [ADR-0006](ADR-0006-self-issued-jwt-auth.md) · [Thiết kế CSDL](../03-design/01-data-model.md)

## Context

- PRD yêu cầu tách dữ liệu theo khu và hộ; BQL chỉ thấy khu mình; giữa các khu chỉ trao đổi kết quả xác nhận tư cách (BR-17).
- Logic nặng nằm trong SQL (ghép cung–cầu theo giờ, bằng chứng không sửa được, tính cấp L1–L4, đối soát) nên đội muốn **viết SQL tay là chính**.
- RAG nội quy (W7) chỉ vài chục tài liệu. Hạ tầng chọn toàn bộ AWS.

## Decision

- **Hạ tầng:** RDS PostgreSQL (khởi điểm `db.t4g.small`, single-AZ), extension `pgvector` (RAG), `pgcrypto` (mã hóa biển số; xem
  [đề xuất sửa](../03-design/09-adr-0005-amendment-proposal.md)), `btree_gist` (ràng buộc không chồng khung giờ).
- **Truy cập:** driver **asyncpg**; SQL trong lớp repository, **luôn tham số `$1, $2…`**, không ghép chuỗi. SQLAlchemy chỉ cho CRUD đơn giản.
- **RLS** trên mọi bảng theo khu hoặc hộ. Mỗi đơn vị công việc mở transaction và `SET LOCAL app.user_id`, `app.role`, `app.zone_ids`; policy đọc
  bằng `current_setting(...)`. Nguồn ngữ cảnh: HTTP request ← JWT (ADR-0006); job `bg` ← `app.role = 'system'` + khu trong payload (mỗi job
  một khu); workflow trong `agent-worker` ← state lúc khởi chạy, thêm `app.approver_id` khi resume sau HITL. Tất cả qua **một helper**
  `platform.db.unit_of_work(ctx)`. App kết nối bằng role không phải owner, không `BYPASSRLS`; migration dùng role owner riêng.
- **Toàn vẹn bằng ràng buộc DB:** exclusion constraint `tstzrange` chặn chồng giờ trên một ô; bằng chứng chỉ `INSERT` (thu quyền
  `UPDATE` / `DELETE`); bước workflow và job có ghi dữ liệu dùng khóa idempotent (`thread_id:step`, mã sự kiện) vì LangGraph chạy lại node
  khi resume và arq chạy lại job. (Outbox, bảng idempotency chung, chuỗi hash: thay bởi ADR-0011.)
- **Migration:** Alembic, nội dung viết bằng `op.execute("""SQL""")` (bảng, index, policy RLS, trigger, grant); không autogenerate.
- **Checkpointer LangGraph:** `langgraph-checkpoint-postgres` chạy trên **psycopg 3**, một pool nhỏ riêng, schema `agent`; code nghiệp vụ dùng asyncpg.

## Consequences

**Tích cực:** Bảo vệ hai lớp (code + RLS): quên `WHERE` cũng không lộ dữ liệu khu khác. Ràng buộc nghiệp vụ quan trọng do DB bảo đảm. · Không cần vector DB riêng; RDS backup tự động.

**Tiêu cực:** Hai driver, ba process cùng mở pool (`api`, `worker`, `agent-worker`): phải chia ngân sách kết nối RDS. · Role `system` cần policy và test riêng (job khu A không đọc khu B); SQL tay cần test tích hợp với Postgres thật, không chỉ mock. · RLS khó debug; `SET LOCAL` buộc mọi truy vấn nằm trong transaction.

## Observability Impact

- `opentelemetry-instrumentation-asyncpg` tạo span mỗi truy vấn: `db.system=postgresql`, `db.operation`, tên truy vấn; **không** ghi giá trị tham số (có thể chứa biển số).
- Metric USE cho pool (nhãn `pool` chỉ `app` / `checkpointer`): `db_client_connections_in_use`, `db_client_connections_max`, `db_client_connection_wait_seconds`.
- CPU, kết nối, IOPS của RDS lấy từ CloudWatch vào Grafana.
