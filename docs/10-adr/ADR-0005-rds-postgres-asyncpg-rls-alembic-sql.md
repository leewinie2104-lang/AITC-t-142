# ADR-0005: RDS PostgreSQL + pgvector, SQL-first với asyncpg, RLS theo khu/hộ, Alembic SQL thuần

- **Status**: Accepted
- **Date**: 2026-11-17
- **Partly superseded by [ADR-0011](ADR-0011-mvp-simplifications.md) (2026-11-18)**: bảng `outbox`, `idempotency_keys` và sổ cái chuỗi hash (`ledger_entry`/`ledger_head`) không có trong schema demo 23 bảng; thay bằng cột `idempotency_key` UNIQUE ở từng bảng đích và `consent_record`. Phần RLS, asyncpg, Alembic giữ nguyên.
- **Cập nhật 2026-11-17**: bổ sung ngữ cảnh RLS cho job và workflow chạy ngoài HTTP request; thêm bảng `outbox` và `idempotency_keys` ([ADR-0010](ADR-0010-backend-modules-agent-workflows-jobs.md))
- **Liên quan**: [PRD §9 Phi chức năng](../01-product/02-prd.md#9-yêu-cầu-phi-chức-năng) · [ADR-0004](ADR-0004-fastapi-langgraph-arq-on-ec2-docker-compose.md) · [ADR-0006](ADR-0006-self-issued-jwt-auth.md) · [ADR-0010](ADR-0010-backend-modules-agent-workflows-jobs.md)

## Context

- **Yêu cầu tách dữ liệu:** PRD yêu cầu phân tách theo khu và theo hộ. BQL chỉ thấy khu mình. Giữa các khu chỉ trao đổi kết quả xác nhận tư cách (BR-17).
- **Logic nặng nằm trong SQL:** ghép cung–cầu theo khung giờ, sổ cái append-only có chuỗi hash, tính cấp tư cách L1–L4, đối soát. Phần lớn là truy vấn phức tạp, nên đội muốn **viết SQL tay là chính**, ORM chỉ dùng cho CRUD đơn giản.
- **RAG nội quy (W7):** chỉ khoảng vài chục tài liệu.
- **Hạ tầng:** đã chọn toàn bộ AWS.

## Decision

**Hạ tầng DB**
- RDS PostgreSQL (khởi điểm `db.t4g.small`, single-AZ), bật extension `pgvector` (RAG), `pgcrypto` (mã hóa biển số, hash sổ cái) và `btree_gist` (ràng buộc không chồng khung giờ).

**Truy cập dữ liệu**
- Driver **asyncpg**. SQL nằm trong lớp repository (hằng chuỗi hoặc file `.sql`), **luôn dùng tham số `$1, $2…`**, không bao giờ ghép chuỗi.
- SQLAlchemy Core / ORM chỉ dùng cho bảng tra cứu và CRUD đơn giản.

**RLS**
- Bật RLS trên mọi bảng có dữ liệu theo khu hoặc theo hộ.
- Mỗi đơn vị công việc mở transaction và đặt ngữ cảnh: `SET LOCAL app.user_id`, `app.role`, `app.zone_ids`. Policy đọc các biến này bằng `current_setting(...)`. Đơn vị công việc gồm:
  - **HTTP request:** ngữ cảnh lấy từ JWT (ADR-0006).
  - **Job `bg` (N1–N8):** `app.role = 'system'` và `app.zone_ids` = khu trong payload của job. Mỗi job chạy riêng cho một khu, khớp backlog. Riêng N7 và N8 chỉ đọc view KPI đã tổng hợp, không đọc bảng chứa dữ liệu cá nhân.
  - **Workflow trong `agent-worker`:** ngữ cảnh lưu trong state của workflow lúc khởi chạy (người khởi tạo, khu có ô). Khi resume sau HITL, thêm `app.approver_id` là BQL đã duyệt.

  Mọi trường hợp đều đi qua **một helper chung** `platform.db.unit_of_work(ctx)`. Không có đường nào truy vấn mà không đặt ngữ cảnh.
- Ứng dụng kết nối bằng role **không phải owner** và không có `BYPASSRLS`. Migration chạy bằng role owner riêng.
- Kết quả: quên điều kiện `WHERE` trong code cũng không làm lộ dữ liệu của khu khác.

**Toàn vẹn dữ liệu bằng ràng buộc DB**
- **Sổ cái:** chỉ `INSERT`; trigger tính `hash = sha256(prev_hash || payload)`; thu hồi quyền `UPDATE`/`DELETE`.
- **Lịch chia sẻ và lượt thuê:** exclusion constraint `tstzrange` để chặn chồng khung giờ trên cùng một ô.
- **Outbox:** bảng `outbox(id, event_type, zone_id, payload, traceparent, created_at, published_at)`.
  - Usecase ghi vào outbox **trong cùng transaction** với thay đổi nghiệp vụ.
  - Relay chạy trong `worker` đọc theo `FOR UPDATE SKIP LOCKED`.
- **Idempotency:** bảng `idempotency_keys(key PRIMARY KEY, result, created_at)`.
  - Mọi bước workflow có ghi dữ liệu đều dùng `key = thread_id:step`.
  - Mọi job N dùng mã sự kiện làm key.
  - Lý do: LangGraph chạy lại node khi resume, và arq có thể chạy lại job.

**Migration**
- Dùng Alembic, nhưng nội dung migration viết bằng `op.execute("""SQL""")`: bảng, index, policy RLS, trigger, grant.
- Không dùng autogenerate.

**Checkpointer LangGraph**
- Dùng `langgraph-checkpoint-postgres`. Thư viện này chạy trên **psycopg 3**, nên server có thêm một pool psycopg 3 nhỏ dành riêng cho checkpointer, nằm trong schema `agent`.
- Code nghiệp vụ vẫn dùng asyncpg.

## Consequences

**Tích cực**
- Bảo vệ hai lớp (code + RLS), khớp yêu cầu riêng tư trong PRD.
- Ràng buộc nghiệp vụ quan trọng (không chồng giờ, sổ cái không sửa được) được DB bảo đảm, không phụ thuộc code.
- Không cần vector DB riêng; backup tự động của RDS.

**Tiêu cực**
- Hai driver Postgres trong cùng service: hai pool, cần đặt giới hạn kết nối tổng cho RDS. Có ba process cùng mở pool (`api`, `worker`, `agent-worker`), nên phải chia ngân sách kết nối cho từng process.
- Role `system` của job phải được viết policy riêng và có test: job khu A không đọc được dữ liệu khu B.
- SQL viết tay cần test tích hợp với Postgres thật (testcontainers hoặc compose). Không thể chỉ mock.
- RLS khó debug hơn. Cần có test chứng minh user khu A không đọc được dữ liệu khu B.
- `SET LOCAL` bắt buộc mọi truy vấn chạy trong transaction; phải có một helper dùng chung để không ai quên.

## Observability Impact

- `opentelemetry-instrumentation-asyncpg` tạo span cho mỗi truy vấn. Thuộc tính span gồm `db.system=postgresql`, `db.operation` và tên truy vấn, **không** gồm giá trị tham số (có thể chứa biển số).
- **Metric USE cho pool** (nhãn `pool` chỉ có hai giá trị: `app`, `checkpointer`):
  - `db_client_connections_in_use{pool}`
  - `db_client_connections_max{pool}`
  - `db_client_connection_wait_seconds{pool}`
- **RDS:** CPU, kết nối, IOPS lấy từ CloudWatch, kéo vào Grafana bằng CloudWatch datasource.
