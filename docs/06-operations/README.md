# 06-operations — Vận hành và quan sát

> **Thư mục này trả lời:** khi hệ thống chạy, nhìn vào đâu để biết nó khỏe, và làm gì khi có sự cố.

## Tổng quan

Theo [ADR-0008](../07-adr/ADR-0008-opentelemetry-lgtm-on-dedicated-ec2.md): OpenTelemetry SDK ở client, api, worker → collector → Tempo (trace), Mimir (metric), Loki (log) → Grafana, chạy trên một EC2 riêng. Metric, trace và log liên kết với nhau qua `trace_id`.

Sơ đồ: [quan sát hệ thống](../02-architecture/diagrams/observability.html).

## Cần quan sát

| Nhóm | Ví dụ |
|---|---|
| API | Tỷ lệ yêu cầu, lỗi, độ trễ theo route (dùng route template, không dùng ID) |
| Agent | Span theo bước `agent.<wN>.<step>`; thời gian và chi phí gọi LLM; số lượt chờ HITL |
| CSDL | Kết nối đang dùng của Postgres (rủi ro R3) |
| Worker | Độ dài queue `bg` / `agent`; job lỗi |
| Nghiệp vụ | KPI theo khu: yêu cầu, ghép, bị chặn sai tư cách / phạm vi ([Brief §7](../01-product/01-project-brief.md#7-chỉ-số-thành-công-kpi)). Pilot ([ADR-0015](../07-adr/ADR-0015-renter-gps-eta-otp-and-two-layer-approval.md)): thời gian chờ có chỗ, tỷ lệ ghép lần đầu, tỷ lệ không nhập OTP / không tới, độ lệch ETA, tỷ lệ tự xử lý ≥ 95%, ca xấu BQL đồng ý, thời gian BQL xử lý ca xấu, thời gian lập hồ sơ tranh chấp |

## Quy tắc

- Không đưa dữ liệu cá nhân (tên, biển số, số căn hộ) vào log, span hay nhãn metric (BR-14).
- Không đưa tọa độ GPS thô vào log, span, metric hay prompt LLM; chỉ ETA và thời điểm (BR-27).
- Nhãn metric chỉ dùng giá trị có giới hạn: khu, route template, workflow; không dùng ID người dùng.

## Bảo mật và quyền riêng tư (gộp từ thư mục `09-security` cũ)

| Chủ đề | Quy tắc | Nguồn |
|---|---|---|
| Xác thực | JWT tự phát hành; demo access JWT 8 giờ, không thu hồi; bộ test auth bắt buộc | [ADR-0006](../07-adr/ADR-0006-self-issued-jwt-auth.md), [ADR-0011](../07-adr/ADR-0011-mvp-simplifications.md) |
| Phân quyền | RLS theo khu và hộ; BQL chỉ thấy khu mình; vận hành chuỗi chỉ thấy số tổng hợp | [ADR-0005](../07-adr/ADR-0005-rds-postgres-asyncpg-rls-alembic-sql.md) |
| Dữ liệu cá nhân | Biển số mã hóa, chỉ hiện bản ẩn; mã giả trước khi gửi LLM; liên khu chỉ trao đổi cấp + hạn | BR-09, BR-14, BR-17, [Scope §3](../01-product/03-scope.md#3-nguyên-tắc-dữ-liệu-và-quyền-riêng-tư) |
| Đồng ý GPS | Người thuê đồng ý riêng trước khi app lấy GPS (NĐ 13/2023, `consent_record`); GPS chỉ lấy khi đang trong hàng chờ | BR-27, [ADR-0015](../07-adr/ADR-0015-renter-gps-eta-otp-and-two-layer-approval.md) |
| Bằng chứng, kiểm toán AI | `consent_record` chỉ ghi thêm; `ai_decision_log` chỉ hash | ADR-0011 |
| Secret, SQL | `.env` trên máy (chmod 600) và GitHub secrets, không vào repo / log / span; SQL chỉ tham số `$1, $2…` | [ADR-0012](../07-adr/ADR-0012-lean-lightsail-prod-and-team-ci-runner.md) · [ADR-0013](../07-adr/ADR-0013-dev-env-on-ci-runner-and-groq.md) |

Còn cần xác nhận: pháp lý dữ liệu cá nhân và chuyển dữ liệu xuyên biên giới, hạn lưu, region Bedrock khi chuyển từ Groq sang Bedrock (ADR-0007, ADR-0013).

## Tài liệu

| File | Nội dung |
|---|---|
| [01-database-operations.md](01-database-operations.md) | Vận hành PostgreSQL: migration, backup / restore (thiết kế ở [03-design](../03-design/README.md)) |
| [02-database-security.md](02-database-security.md) | Mạng, vai trò DB, secret, RLS, dữ liệu cá nhân, `ai_decision_log`, schema `agent` |
| [03-database-monitoring-scaling.md](03-database-monitoring-scaling.md) | Cấu hình giám sát, connection pool, cảnh báo, khi nào mở rộng |

## Nên có thêm

| File gợi ý | Nội dung |
|---|---|
| `04-observability-guide.md` | Danh sách metric, span, cách xem trên Grafana |
| `05-runbook.md` | Xử lý sự cố thường gặp: LLM không trả lời, SSE bị cắt (R2), hết kết nối DB (R3), EC2 chết (R5) |
| `06-lpr-simulation.md` | Cách nạp bộ log LPR mô phỏng cho demo (N1) |

Thêm file thì cập nhật bảng trên và [docs/README.md](../README.md).
