# 08-operations — Vận hành và quan sát

> **Thư mục này trả lời:** khi hệ thống chạy, nhìn vào đâu để biết nó khỏe, và làm gì khi có sự cố.

## Tổng quan

**Chưa có tài liệu.** Theo [ADR-0008](../10-adr/ADR-0008-opentelemetry-lgtm-on-dedicated-ec2.md): OpenTelemetry SDK ở client, api, worker → collector → Tempo (trace), Mimir (metric), Loki (log) → Grafana, chạy trên một EC2 riêng. Metric, trace và log liên kết với nhau qua `trace_id`.

Ảnh: [arch-observability](../images/ParkSmartAI-arch-observability.png).

## Cần quan sát

| Nhóm | Ví dụ |
|---|---|
| API | Tỷ lệ yêu cầu, lỗi, độ trễ theo route (dùng route template, không dùng ID) |
| Agent | Span theo bước `agent.<wN>.<step>`; thời gian và chi phí gọi LLM; số lượt chờ HITL |
| CSDL | Kết nối đang dùng của RDS (rủi ro R3) |
| Worker | Độ dài queue `bg` / `agent`; job lỗi |
| Nghiệp vụ | KPI theo khu: yêu cầu, ghép, bị chặn sai tư cách / phạm vi ([Brief §7](../01-product/01-project-brief.md#7-chỉ-số-thành-công-kpi)) |

## Quy tắc

- Không đưa dữ liệu cá nhân (tên, biển số, số căn hộ) vào log, span hay nhãn metric (BR-14).
- Nhãn metric chỉ dùng giá trị có giới hạn: khu, route template, workflow; không dùng ID người dùng.

## Nên có

| File gợi ý | Nội dung |
|---|---|
| `01-observability-guide.md` | Danh sách metric, span, cách xem trên Grafana |
| `02-runbook.md` | Xử lý sự cố thường gặp: LLM không trả lời, SSE bị cắt (R2), hết kết nối DB (R3), EC2 chết (R5) |
| `03-lpr-simulation.md` | Cách nạp bộ log LPR mô phỏng cho demo (N1) |

Thêm file thì cập nhật bảng trên và [docs/README.md](../README.md).
