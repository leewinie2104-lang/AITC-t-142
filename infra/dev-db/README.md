# infra/dev-db — Postgres + Redis dùng chung cho DEV (ADR-0013, plan 017)

Chạy trên máy runner CI `parksmart-ci-runner` ([infra/ci-runner](../ci-runner/README.md)), vào bằng **Tailscale**.
Không phải demo/prod: prod nằm ở [infra/lightsail](../lightsail/README.md). **Chỉ chứa dữ liệu giả.**

| Dịch vụ | Cổng | User | Ghi chú |
|---|---|---|---|
| Postgres 16 + pgvector, pgcrypto, btree_gist | 15432 | `parksmart_app` (app), `parksmart_migrator` (chỉ CI) | DB `parksmart`, RAM tối đa 512 MB |
| Redis 7 | 16379 | mật khẩu `REDIS_PASSWORD` | `noeviction`, AOF bật, RAM tối đa 128 MB |

Máy bật 08:00–22:00 (giờ VN). Ngoài giờ không truy cập được; dữ liệu vẫn còn trên đĩa.

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

## Phần của người giữ mật khẩu (một lần)

1. Đọc mật khẩu trên máy: `cat /opt/parksmart-devdb/.env` (quyền root). Lưu vào Bitwarden của đội.
   Dev chỉ cần `APP_PASSWORD` và `REDIS_PASSWORD`; `MIGRATOR_PASSWORD` chỉ CI dùng, `POSTGRES_PASSWORD` để cứu hộ.
2. Mời từng thành viên vào tailnet. Gói free giới hạn số user: kiểm tra trên trang giá Tailscale; thiếu thì dùng
   tính năng share máy `parksmart-ci-runner` cho tài khoản của từng người.

## Dev kết nối

Bật Tailscale trên laptop, rồi trong `.env` ở gốc repo (xem [.env.example](../../.env.example)):
```
DATABASE_URL=postgresql://parksmart_app:<APP_PASSWORD>@parksmart-ci-runner:15432/parksmart
REDIS_URL=redis://:<REDIS_PASSWORD>@parksmart-ci-runner:16379/<db-index của bạn>
```
`parksmart_app` không tạo được bảng: schema chỉ đổi qua migration, CI chạy sau khi merge `dev`.
Thử migration trên Postgres local: `docker compose up -d postgres`, rồi `MIGRATE_DATABASE_URL=postgresql://parksmart:parksmart@localhost:5432/parksmart alembic upgrade head` trong `server/`.

## Gỡ / làm lại

`docker compose -f docker-compose.devdb.yml down` giữ dữ liệu; thêm `-v` để xóa sạch (init role chạy lại ở lần `setup.py` sau).
