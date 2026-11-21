# infra/ci-runner — runner GitHub Actions của đội trên EC2 (ADR-0012)

Một EC2 `t3.small` (amd64, 2 vCPU / 2 GB, 20 GB gp3, Ubuntu 24.04, ap-southeast-1) chạy cả job CI (`ci.yml`) và job build
image (`deploy.yml`) qua label `p142`. Gộp từ plan 012 vào plan 015. Không chạy runner trên laptop cá nhân (yêu cầu BTC).

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
3. Chạy dưới user `runner`, thêm label `p142` vào lệnh Phoenix đưa:
   ```bash
   sudo -iu runner
   cd ~/actions-runner && cat INSTALLED
   ./config.sh --url <URL Phoenix đưa> --token <TOKEN> --labels p142 --name parksmart-ci-runner --unattended
   exit
   cd /home/runner/actions-runner && sudo ./svc.sh install runner && sudo ./svc.sh start
   ```
4. Kiểm tra: runner hiện **Idle** trên Phoenix / GitHub; `sudo ./svc.sh status` báo `active (running)`.

## Việc thường làm

```bash
aws ec2 start-instances --instance-ids <id>     # bật ngoài giờ (máy local, đã aws login)
aws ec2 stop-instances  --instance-ids <id>
df -h / && docker system df                     # trong Session Manager: kiểm tra đĩa
sudo systemctl start docker-prune               # dọn Docker ngay (timer chạy 03:00 chủ nhật)
```

## Rủi ro đã biết

- Nếu label `p142` dùng chung cả org, repo khác có thể đặt job lên máy này và làm bẩn cache Docker. `deploy.yml` build với
  `--pull`, máy không có quyền AWS; vẫn nên nhờ BTC giới hạn runner cho riêng repo P-142 (runner group).
- Máy tắt lúc 22:00 có thể cắt ngang job đang chạy; job đó cần chạy lại.

## Xóa sau demo

Gỡ runner trên Phoenix (hoặc `./config.sh remove`), terminate EC2 (EBS xóa theo), xóa 2 schedule, role `parksmart-scheduler`,
role + instance profile `parksmart-ci-runner`, security group.
