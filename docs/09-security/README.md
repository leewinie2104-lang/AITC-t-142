# 09-security — Bảo mật và quyền riêng tư

> **Thư mục này trả lời:** ai được thấy dữ liệu gì, dữ liệu cá nhân được bảo vệ ra sao, và LLM được phép nhận gì.

## Tổng quan

**Chưa có tài liệu.** Các quyết định và quy tắc bảo mật hiện nằm rải ở nhiều nơi; thư mục này sẽ gom lại thành một chỗ.

| Chủ đề | Quy tắc | Nguồn |
|---|---|---|
| Xác thực | JWT tự phát hành trong FastAPI; bộ test auth bắt buộc (rủi ro R4) | [ADR-0006](../10-adr/ADR-0006-self-issued-jwt-auth.md) |
| Phân quyền | RLS theo khu và hộ; BQL chỉ thấy khu mình; vận hành chuỗi chỉ thấy số liệu tổng hợp | [ADR-0005](../10-adr/ADR-0005-rds-postgres-asyncpg-rls-alembic-sql.md), [PRD §9](../01-product/02-prd.md#9-yêu-cầu-phi-chức-năng) |
| Biển số, ảnh | Xử lý theo đồng ý khi đăng ký; mã hóa khi lưu; ẩn trong ticket; xem bản gốc phải ghi log | BR-09, [Scope §3](../01-product/03-scope.md#3-nguyên-tắc-dữ-liệu-và-quyền-riêng-tư) |
| LLM | Tên và biển số thay bằng mã giả trước khi gửi LLM; LLM không quyết định | BR-14 |
| Liên khu | Giữa các khu chỉ trao đổi kết quả xác nhận tư cách (cấp, hạn) | BR-17 |
| Sổ cái | Chỉ ghi thêm, chuỗi hash để phát hiện sửa đổi | PRD §9 |
| Secret | Lưu ở SSM Parameter Store; không đưa vào repo, log, span | [ADR-0009](../10-adr/ADR-0009-terraform-github-actions-ecr-ssm.md) |
| SQL | Chỉ dùng tham số `$1, $2…`, không ghép chuỗi | `.claude/rules/backend.md` |

## Việc cần xác nhận

- Pháp lý về dữ liệu cá nhân và chuyển dữ liệu xuyên biên giới trước khi nối AI với dữ liệu thật ([Scope §5](../01-product/03-scope.md#5-phụ-thuộc)).
- Phạm vi, thời hạn lưu và quy trình rút đồng ý xử lý biển số, ảnh (A-03).
- Region Bedrock (ADR-0007).

## Nên có

| File gợi ý | Nội dung |
|---|---|
| `01-threat-model.md` | Tài sản cần bảo vệ, kẻ tấn công, biện pháp |
| `02-data-classification.md` | Dữ liệu nào là cá nhân, lưu ở đâu, ai xem, lưu bao lâu |
| `03-llm-safety.md` | Guardrail, ẩn danh, chống prompt injection, giới hạn đầu ra |

Thêm file thì cập nhật bảng trên và [docs/README.md](../README.md). Skill `pre-pr` có bước quét secret.
