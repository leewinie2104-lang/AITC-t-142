# ADR-0009: Hạ tầng bằng Terraform; CI/CD bằng GitHub Actions → ECR → EC2 qua SSM

- **Status**: Superseded by [ADR-0012](ADR-0012-lean-lightsail-prod-and-team-ci-runner.md) (gộp ngày 2026-11-22, plan 021)
- **Date**: 2026-11-17

Phần còn hiệu lực (OIDC thay access key, không mở SSH cho CI, bí mật không nằm trong GitHub, cảnh báo ngân sách) đã chuyển sang
ADR-0012. Terraform và deploy qua SSM Run Command không dùng cho demo. Nội dung cũ xem git history của file này.
