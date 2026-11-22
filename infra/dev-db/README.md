# infra/dev-db — Postgres + Redis dùng chung cho DEV (ADR-0013, plan 017)

Chạy trên máy runner CI `parksmart-ci-runner` ([infra/ci-runner](../ci-runner/README.md)), vào bằng **Tailscale**.
Không phải demo/prod: prod nằm ở [infra/lightsail](../lightsail/README.md). **Chỉ chứa dữ liệu giả.**

| Dịch vụ | Cổng | User | Ghi chú |
|---|---|---|---|
| Postgres 16 + pgvector, pgcrypto, btree_gist | 15432 | `parksmart_app` (app), `parksmart_migrator` (chỉ CI) | DB `parksmart`, RAM tối đa 512 MB |
| Redis 7 | 16379 | mật khẩu `REDIS_PASSWORD` | `noeviction`, AOF bật, RAM tối đa 128 MB |

Máy bật 10:00 đến 02:00 sáng hôm sau (giờ VN). Ngoài giờ không truy cập được; dữ liệu vẫn còn trên đĩa.

## Dựng lần đầu (trên máy, qua SSM Session Manager)

1. Cài Tailscale và đăng nhập (mở link in ra, chọn tailnet của đội, rồi **Disable key expiry** cho máy này trong admin console):
   ```bash
   curl -fsSL https://tailscale.com/install.sh | sh
   tailscale up --hostname=parksmart-ci-runner --ssh=false
   ```
2. Chép thư mục này lên `/opt/parksmart-devdb/` rồi chạy (quyền root): `python3 /opt/parksmart-devdb/setup.py`.
   Lần đầu script sinh `.env` gồm 4 mật khẩu ngẫu nhiên (chmod 600, không in ra) và khởi động 2 container.
   Script cũng ghi `MIGRATE_DATABASE_URL` (role migrator) vào `/home/runner/actions-runner/.env` để job CI
   `migrate-dev-db` dùng; **không cần GitHub secret**. Sau đó khởi động lại runner khi không có job đang chạy:
   `systemctl restart actions.runner.*.service`.
3. Kiểm tra: `docker compose -f /opt/parksmart-devdb/docker-compose.devdb.yml ps` → cả hai `healthy`.
4. **Volume tạo trước 2026-11-22** (chỉ có `01-roles.sql`): chép `initdb/02-runtime-roles.sql` lên
   `/opt/parksmart-devdb/initdb/`, rồi chạy **một lần** (chạy lại cũng an toàn):
   ```bash
   cd /opt/parksmart-devdb && docker compose -f docker-compose.devdb.yml exec -T postgres \
     psql -U postgres -d parksmart -v ON_ERROR_STOP=1 -f /docker-entrypoint-initdb.d/02-runtime-roles.sql
   ```
   Script tạo `parksmart_checkpointer`, `parksmart_readonly`, đặt timeout cho `parksmart_app` và cho
   `parksmart_owner` làm thành viên của checkpointer. Revision 0001 cần những thứ này nhưng owner không có `CREATEROLE`
   nên không tự làm được. Thiếu bước này thì job `migrate-dev-db` báo `run infra/dev-db/initdb/02-runtime-roles.sql`.

## Onboarding thành viên mới

### Người giữ tailnet làm (một lần cho mỗi người)

1. Đọc mật khẩu trên máy (một lần): `cat /opt/parksmart-devdb/.env` (quyền root, qua SSM Session Manager), lưu vào
   Bitwarden của đội. Thành viên chỉ nhận **`APP_PASSWORD`** và **`REDIS_PASSWORD`**; `MIGRATOR_PASSWORD` chỉ CI dùng,
   `POSTGRES_PASSWORD` (superuser) chỉ để cứu hộ. Mỗi mật khẩu dài 48 ký tự `0-9a-f`.
2. Cho thành viên vào được máy, chọn một cách:
   - **Share máy** (nên dùng): Tailscale admin console → Machines → `parksmart-ci-runner` → **Share** → gửi link.
     Người nhận dùng tài khoản Tailscale của họ và chỉ thấy máy này.
   - **Mời vào tailnet**: Settings → Users → **Invite**. Người nhận thấy mọi máy trong tailnet; gói free giới hạn số user.
3. Gửi qua Bitwarden: hai mật khẩu trên và **số Redis DB index** riêng của người đó (0, 1, 2, 3…, không trùng nhau).

### Thành viên làm

1. Cài [Tailscale](https://tailscale.com/download), bấm link mời và đăng nhập. **Tắt Cloudflare WARP / VPN khác** trước,
   nếu không Tailscale không kết nối được.
2. Kiểm tra: `tailscale ping 100.111.246.41` phải ra `pong`.
3. Trong repo: `make install`, `make .env`. Mở `.env` ở gốc repo (mẫu: [.env.example](../../.env.example)) và sửa:
   ```
   DATABASE_URL=postgresql://parksmart_app:APP_PASSWORD_HERE@parksmart-ci-runner:15432/parksmart
   REDIS_URL=redis://:REDIS_PASSWORD_HERE@parksmart-ci-runner:16379/0
   ```
   Thay **nguyên chữ** `APP_PASSWORD_HERE` / `REDIS_PASSWORD_HERE` bằng mật khẩu, **không** giữ dấu `< >` hay nháy;
   đổi số cuối của `REDIS_URL` thành DB index của bạn. Nếu tên `parksmart-ci-runner` không tìm được (khi dùng share máy),
   thay bằng IP `100.111.246.41`. Điền thêm `LLM_API_KEY` (Groq) và `AI_LOG_API_KEY` (Phoenix) của bạn.
4. Kiểm tra kết nối, chạy trong `server/`:
   ```bash
   PYTHONPATH=src ../.venv/bin/python -c "
   import asyncio, asyncpg, redis
   from app.platform.config.settings import get_settings
   s = get_settings()
   async def main():
       c = await asyncpg.connect(s.database_url)
       print('db user:', await c.fetchval('select current_user'))
       try: await c.execute('create table t_probe(id int)'); print('CREATE: allowed (SAI)')
       except asyncpg.InsufficientPrivilegeError: print('CREATE: denied (đúng)')
       await c.close()
   asyncio.run(main())
   print('redis ping:', redis.Redis.from_url(s.redis_url).ping())
   "
   ```
   Đúng: `db user: parksmart_app`, `CREATE: denied (đúng)`, `redis ping: True`. Sau đó `make run` ở gốc repo.

### Xem dữ liệu bằng UI (trên laptop, không cài lên EC2)

| Dịch vụ | Công cụ gợi ý | Kết nối |
|---|---|---|
| Postgres | DBeaver, pgAdmin desktop, TablePlus, hoặc `make up PROFILE=tools` → pgAdmin http://localhost:5050 | Host `100.111.246.41`, port `15432`, DB `parksmart`, user `parksmart_app`, mật khẩu `APP_PASSWORD` |
| Redis | Redis Insight desktop, hoặc `make up PROFILE=tools` → http://localhost:5540 | Host `100.111.246.41`, port `16379`, username **để trống**, mật khẩu `REDIS_PASSWORD`, DB index của bạn |

Ô username của Postgres chỉ ghi `parksmart_app`, không có chữ `user` đằng trước. Bằng role này bạn đọc / ghi dữ liệu được,
không sửa được schema.

### Lỗi hay gặp

| Triệu chứng | Nguyên nhân / cách sửa |
|---|---|
| Tailscale bấm Sign in không có gì xảy ra; `tailscale status` báo `no route to host` | Cloudflare WARP / VPN khác đang chạy, hoặc mạng không có IPv6: tắt WARP, Quit rồi mở lại Tailscale |
| `password authentication failed for user "parksmart_app"` | Còn dấu `< >` hoặc dán nhầm mật khẩu khác; mật khẩu đúng dài đúng 48 ký tự |
| `password authentication failed for user "user parksmart_app"` | Ô username trong UI gõ thừa chữ `user ` |
| `ModuleNotFoundError: No module named 'app'` | Thiếu `PYTHONPATH=src` khi chạy `python -c` trong `server/` |
| `No module named 'redis'` | Chạy `../.venv/bin/pip install -r requirements.txt` trong `server/` |
| Kết nối treo / timeout ngoài 08:00–22:00 | Máy đã tắt theo lịch; báo người giữ hạ tầng nếu cần bật |

### Quy tắc

- **Không chạy `alembic` lên DB dùng chung.** Schema chỉ đổi qua migration trong PR; CI tự migrate sau khi merge `dev`.
  Thử migration trên Postgres local: `docker compose up -d postgres`, rồi trong `server/`:
  `MIGRATE_DATABASE_URL=postgresql://parksmart:parksmart@localhost:5432/parksmart alembic upgrade head`.
  Quy trình đầy đủ (migrate, `make seed`, integration test): `docs/06-operations/01-database-operations.md` §1.
- **Seed DB dùng chung** chỉ do người giữ hạ tầng chạy một lần sau khi CI migrate (`make seed` với `.env` trỏ vào DB
  dev và role có quyền ghi); không ai khác seed lên DB này.
- **Chỉ dữ liệu giả**: không đưa biển số, SĐT, tên thật vào DB dev (mọi job CI đều với tới được DB này).
- Không gửi mật khẩu qua git / Jira / chat; không commit `.env`.

## Gỡ / làm lại

`docker compose -f docker-compose.devdb.yml down` giữ dữ liệu; thêm `-v` để xóa sạch (init role chạy lại ở lần `setup.py` sau).
