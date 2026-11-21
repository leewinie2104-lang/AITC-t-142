# ADR-0008: OpenTelemetry + LGTM (Loki, Grafana, Tempo, Mimir) trên một EC2 riêng

- **Status**: Accepted · **Partly superseded by [ADR-0012](ADR-0012-lean-lightsail-prod-and-team-ci-runner.md) (2026-11-21)**: chưa dựng LGTM cho demo; khi thêm OTel thì gửi lên Grafana Cloud free
- **Date**: 2026-11-17
- **Liên quan**: [ADR-0004](ADR-0004-fastapi-langgraph-arq-on-ec2-docker-compose.md) · [ADR-0007](ADR-0007-claude-via-amazon-bedrock.md)

## Context

- Cần trace xuyên suốt: client → API → node LangGraph → Bedrock → Postgres → job arq → WebSocket, nhất là luồng có bước chờ BQL duyệt và luồng LPR → worker → Agent.
- Cần liên kết metric (exemplar) → trace (`trace_id`) → log (lọc theo `trace_id`).
- Stack LGTM cần ~4–6 GB RAM; chạy chung máy app thì app sự cố sẽ mất luôn khả năng quan sát.

## Decision

- **EC2 riêng** (t3.large, EBS gp3 ~50 GB), docker compose: Grafana, Loki, Tempo, Mimir, OTel Collector gateway; dữ liệu đĩa local, giữ 7 ngày.
- **Đường dữ liệu:** EC2 app: Collector (agent) → OTLP gRPC trong VPC → gateway → Tempo / Mimir (remote write) / Loki. Trình duyệt: OTel Web SDK →
  `/api/v1/otel` (proxy qua API, có rate limit) → collector.
- **Code server:** OTel SDK Python; log JSON (`structlog` / `logging`) tự gắn `trace_id`, `span_id`; histogram thời gian bật exemplar.
- **Grafana:** datasource Tempo, Loki, Mimir, CloudWatch (RDS); liên kết trace → log, log → trace (derived field), metric → trace (exemplar).
  Dashboard tối thiểu: RED của API, hàng đợi arq, LLM (token, độ trễ, chi phí), pool DB, nguồn LPR theo khu.
- **Truy cập:** Grafana không mở ra Internet; dùng SSM port forwarding, hoặc CloudFront có xác thực khi trình chiếu.
- **Cardinality (bắt buộc):** không dùng ID người dùng, ID lượt đỗ, biển số hay URL thô làm nhãn; nhãn `zone` được phép (số khu nhỏ, cố định).

## Consequences

**Tích cực**
- Liên kết đủ metric → trace → log, kể cả bước chờ duyệt và job nền; app sự cố vẫn xem được dữ liệu đến lúc đó; không phụ thuộc SaaS.

**Tiêu cực**
- Thêm một máy phải vận hành và trả tiền; dữ liệu ngắn hạn, không HA; tốn ~2–3 ngày công dựng.
- Theo dõi LLM không chi tiết bằng công cụ chuyên dụng (Langfuse); bù bằng span GenAI và kết quả eval trong repo.

## Observability Impact

Đây là nền tảng cho toàn bộ telemetry. Hướng dẫn chi tiết (tên metric, span, cách xem trên Grafana) sẽ ghi trong
`docs/06-operations/observability-guide.md` khi triển khai.
