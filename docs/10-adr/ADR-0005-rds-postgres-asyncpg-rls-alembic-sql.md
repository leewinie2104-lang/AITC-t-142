# ADR-0005: RDS PostgreSQL + pgvector, SQL-first với asyncpg, RLS theo khu/hộ, Alembic SQL thuần

- **Status**: Accepted
- **Date**: 2026-11-17
- **Liên quan**: [PRD §9 Phi chức năng](../01-product/prd.md#9-yêu-cầu-phi-chức-năng) · [ADR-0004](ADR-0004-fastapi-langgraph-arq-on-ec2-docker-compose.md) · [ADR-0006](ADR-0006-self-issued-jwt-auth.md)

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
- Mỗi request mở transaction và đặt ngữ cảnh: `SET LOCAL app.user_id`, `app.role`, `app.zone_ids`. Policy đọc các biến này bằng `current_setting(...)`.
- Ứng dụng kết nối bằng role **không phải owner** và không có `BYPASSRLS`. Migration chạy bằng role owner riêng.
- Kết quả: quên điều kiện `WHERE` trong code cũng không làm lộ dữ liệu của khu khác.

**Toàn vẹn dữ liệu bằng ràng buộc DB**
- **Sổ cái:** chỉ `INSERT`; trigger tính `hash = sha256(prev_hash || payload)`; thu hồi quyền `UPDATE`/`DELETE`.
- **Lịch chia sẻ và lượt thuê:** exclusion constraint `tstzrange` để chặn chồng khung giờ trên cùng một ô.

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
- Hai driver Postgres trong cùng service: hai pool, cần đặt giới hạn kết nối tổng cho RDS.
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
