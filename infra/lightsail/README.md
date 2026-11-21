# infra/lightsail — máy prod (ADR-0012)

Một Lightsail `small_3_0` (2 GB, Ubuntu 24.04, ap-southeast-1) chạy toàn bộ backend bằng docker compose.
Không có Terraform: tài nguyên được tạo bằng AWS CLI (plan 015, bước 5) và liệt kê ở bảng dưới.

## Luồng deploy

```
merge main → Actions (runner p142) → OIDC → build image → S3 releases/sha-….tgz → ECR :sha-… rồi :main
                                                                                  │
Lightsail: parksmart-deploy.timer (2 phút) → deploy.py thấy :main trỏ sang tag mới ┘
  → tải bundle → docker login → pull → postgres/redis lên → alembic (nếu image có) → up --wait
  → GET https://<SITE_ADDRESS>/api/v1/health → lỗi: đánh dấu failed, chạy lại tag cũ
```

Máy không nhận lệnh từ GitHub, không có cổng nào mở cho CI. Quyền AWS của máy đến từ **SSM hybrid activation**
(role `parksmart-lightsail`, khóa tạm thời tự xoay trong `/root/.aws/credentials`), không có access key lâu dài.

## File

| File | Nằm trên máy ở | Vai trò |
|---|---|---|
| `docker-compose.prod.yml` | `/opt/parksmart/releases/<tag>/` | caddy, api, redis, postgres; worker / agent-worker sau profile `workers` |
| `Caddyfile` | như trên | HTTPS Let's Encrypt cho `<ip>.sslip.io`, proxy vào `api:8000` |
| `deploy.py`, `backup.py` | `/opt/parksmart/bin/` | deploy kéo từ ECR; `pg_dump` lên S3. Tự cập nhật sau mỗi deploy thành công |
| `systemd/` | `/etc/systemd/system/` | timer deploy (2 phút), timer backup (02:00 giờ VN) |
| `prod.env.example` | `/opt/parksmart/.env` (chmod 600) | mẫu biến môi trường; **bạn tự điền**, không bao giờ commit |
| `cloud-init.yaml` | user data lúc tạo máy | Docker, swap 2 GB, AWS CLI, SSM agent, tải bundle khởi động từ S3 |

Trạng thái deploy: `/opt/parksmart/state/{current,previous,failed}`; `deploy.env` giữ `IMAGE` và `RELEASE_DIR` đang chạy.

## Tài nguyên AWS (tag `Project=parksmart`)

| Tài nguyên | Tên | Ghi chú |
|---|---|---|
| Lightsail + static IP | `parksmart-prod`, `parksmart-prod-ip` | firewall: 80, 443; 22 chỉ cho alias `lightsail-connect` (SSH trên trình duyệt) |
| ECR | `parksmart/server` | lifecycle giữ 5 image |
| S3 | `parksmart-825765410318-apse1` | `releases/` (30 ngày), `backups/` (7 ngày), `bootstrap/`; chặn public, mã hóa SSE-S3 |
| IAM OIDC provider + role | `token.actions.githubusercontent.com`, `parksmart-gha-deploy` | chỉ tin `repo:AI20K-Build-Phase-Cohort-5/P-142:ref:refs/heads/main`; push ECR repo trên + ghi `releases/` |
| IAM role + SSM activation | `parksmart-lightsail` | pull ECR, đọc `releases/` + `bootstrap/`, ghi `backups/` |
| Budget | `parksmart-monthly` | 25 USD, email ở 80 % và 100 % |

## Việc thường làm (SSH trên trình duyệt của Lightsail)

```bash
sudo nano /opt/parksmart/.env                      # điền SITE_ADDRESS, OPENAI_API_KEY, CORS_ORIGINS
sudo systemctl start parksmart-deploy              # deploy ngay, không chờ timer
journalctl -u parksmart-deploy -n 100 --no-pager   # log deploy gần nhất
cat /opt/parksmart/state/current                   # tag đang chạy
sudo docker compose -p parksmart ps                # trạng thái container
sudo docker stats --no-stream                      # RAM từng container (mục tiêu tổng < 1,8 GB)
```

- **Thử lại một tag đã failed**: xóa tag đó khỏi `/opt/parksmart/state/failed`, rồi `systemctl start parksmart-deploy`.
- **Quay về bản cũ bằng tay**: trên máy local, `aws ecr put-image` gắn lại tag `main` cho image `sha-…` cũ
  (xem `aws ecr batch-get-image`); máy sẽ tự deploy tag đó. Migration không bị đảo ngược (chỉ đi tiến).
- **Bật worker** khi `arq` có trong `server/requirements.txt`: thêm `COMPOSE_PROFILES=workers` vào `.env`, xóa dòng
  `current` trong `state/` rồi chạy deploy.
- **Đổi `.env`**: sửa file, rồi `sudo docker compose -p parksmart --project-directory /opt/parksmart --env-file /opt/parksmart/.env
  --env-file /opt/parksmart/deploy.env -f "$(grep RELEASE_DIR /opt/parksmart/deploy.env | cut -d= -f2)/docker-compose.prod.yml" up -d`.

## Backup và restore

`parksmart-backup.timer` chạy 02:00 mỗi đêm: `pg_dump -Fc` → `s3://parksmart-825765410318-apse1/backups/`. Chạy tay:
`sudo systemctl start parksmart-backup`. Restore thử vào Postgres local (máy dev):

```bash
aws s3 cp s3://parksmart-825765410318-apse1/backups/parksmart-<stamp>.dump ./prod.dump
docker compose up -d postgres
docker compose exec -T postgres pg_restore -U parksmart -d parksmart --clean --if-exists < prod.dump
```

## Xóa sau demo

Lightsail instance + static IP (static IP không gắn máy vẫn tính tiền), ECR repo, S3 bucket (xóa object trước),
role `parksmart-gha-deploy`, `parksmart-lightsail`, managed node `mi-…` trong SSM Fleet Manager, OIDC provider, Budget.
Tải backup cuối về trước khi xóa bucket.
