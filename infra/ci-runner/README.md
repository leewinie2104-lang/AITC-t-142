# infra/ci-runner — runner GitHub Actions của đội trên EC2 (ADR-0012)

Một EC2 `t3.small` (amd64, 2 vCPU / 2 GB, 20 GB gp3, Ubuntu 24.04, ap-southeast-1) chạy cả job CI (`ci.yml`) và job build
image (`deploy.yml`) qua label `team-142`. Gộp từ plan 012 vào plan 015. Không chạy runner trên laptop cá nhân (yêu cầu BTC).

## Vì sao như vậy

- **amd64** giống Lightsail, nên build image không cần buildx / QEMU.
- **Không inbound**: security group không có rule vào; vào máy bằng SSM Session Manager (miễn phí với EC2).
- **Role của máy chỉ có `AmazonSSMManagedInstanceCore`**. Job `deploy.yml` lấy quyền AWS bằng OIDC (role `parksmart-gha-deploy`
  chỉ tin nhánh `main` của P-142). Vì vậy job lạ có rơi vào máy này cũng không có quyền AWS nào.
- **Bật theo giờ**: EventBridge Scheduler bật 08:00, tắt 22:00 (Asia/Ho_Chi_Minh). Ngoài giờ, job CI xếp hàng tới khi máy bật
  (GitHub giữ job tối đa 24 giờ). Cần chạy ngoài giờ thì bật máy bằng tay (dưới).

## Tài nguyên (tag `Project=parksmart`)

| Tài nguyên | Tên |
|---|---|
| EC2 + EBS 20 GB gp3 | `parksmart-ci-runner` |
| Security group | `parksmart-ci-runner` (không inbound, outbound tất cả) |
| IAM role + instance profile | `parksmart-ci-runner` (`AmazonSSMManagedInstanceCore`) |
| Scheduler + role | `parksmart-ci-runner-start`, `parksmart-ci-runner-stop`, role `parksmart-scheduler` (chỉ start / stop máy này) |

Chi phí ước tính: EC2 14 h/ngày ~10 USD + EBS ~2 USD + IPv4 công khai lúc chạy ~2 USD.

## Đăng ký runner qua Phoenix (bạn làm, một lần)

1. Lấy lệnh / token đăng ký runner cho repo P-142 trên Phoenix (`portal-cohort5.edufun.ai/runners`). Token không bao giờ vào repo.
2. Mở shell trên máy: AWS Console → EC2 → `parksmart-ci-runner` → **Connect** → **Session Manager**.
3. Trên Phoenix chọn **Linux + x64**. Bỏ bước tải runner (cloud-init đã tải) và `./run.sh`. Gõ **từng dòng**, không dán cả khối
   (`exit` sẽ nuốt các dòng sau):
   ```bash
   sudo -iu runner
   cd ~/actions-runner && cat INSTALLED && uname -m   # actions runner … unpacked, x86_64
   # dán nguyên dòng ./config.sh ở bước 2 của Phoenix (đã có token, tên team-142-…, label team-142)
   exit
   cd /home/runner/actions-runner
   sudo ./svc.sh install runner
   sudo ./svc.sh start
   ```
4. Kiểm tra: runner hiện **Idle** trên Phoenix / GitHub; `sudo ./svc.sh status` báo `active (running)`.

Đã đăng ký 2026-11-21: `team-142-NgMinPhuc`, cấp repo P-142, label `team-142`, máy `i-04664f2dcb5658d18`.
Đăng ký lại (đổi máy, token cũ hỏng): `./config.sh remove --token <token mới từ Phoenix>` rồi làm lại bước 3.

## Việc thường làm

```bash
aws ec2 start-instances --instance-ids <id>     # bật ngoài giờ (máy local, đã aws login)
aws ec2 stop-instances  --instance-ids <id>
df -h / && docker system df                     # trong Session Manager: kiểm tra đĩa
sudo systemctl start docker-prune               # dọn Docker ngay (timer chạy 03:00 chủ nhật)
```

## Rủi ro đã biết

- Phoenix đăng ký runner ở cấp **repo P-142**, nên repo khác không đặt job lên máy này được. Mọi PR trong repo (kể cả của
  thành viên) đều chạy code trên máy: máy không có quyền AWS, `deploy.yml` build với `--pull`.
- Máy tắt lúc 22:00 có thể cắt ngang job đang chạy; job đó cần chạy lại.

## Xóa sau demo

Gỡ runner trên Phoenix (hoặc `./config.sh remove`), terminate EC2 (EBS xóa theo), xóa 2 schedule, role `parksmart-scheduler`,
role + instance profile `parksmart-ci-runner`, security group.
