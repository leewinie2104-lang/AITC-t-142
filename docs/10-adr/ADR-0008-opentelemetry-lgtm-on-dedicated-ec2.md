# ADR-0008: OpenTelemetry + LGTM (Loki, Grafana, Tempo, Mimir) trên một EC2 riêng

- **Status**: Accepted
- **Date**: 2026-11-17
- **Liên quan**: [ADR-0004](ADR-0004-fastapi-langgraph-arq-on-ec2-docker-compose.md) · [ADR-0007](ADR-0007-claude-via-amazon-bedrock.md)

## Context

- **Cần trace xuyên suốt** một luồng nghiệp vụ: client → API → node LangGraph → Bedrock → Postgres → job arq → WebSocket. Đặc biệt với các luồng có bước dừng chờ BQL duyệt và luồng LPR → worker → Agent.
- **Cần liên kết ba nguồn dữ liệu:** metric (exemplar) → trace (`trace_id`) → log (lọc theo `trace_id`).
- **Tài nguyên:** stack LGTM cần khoảng 4–6 GB RAM. Chạy chung máy với ứng dụng thì máy app gặp sự cố sẽ kéo theo mất luôn khả năng quan sát.

## Decision

**EC2 riêng cho observability** (t3.large, đĩa EBS gp3 khoảng 50 GB), chạy docker compose gồm Grafana, Loki, Tempo, Mimir và một OTel Collector gateway. Dữ liệu lưu trên đĩa local, giữ 7 ngày (đủ cho demo).

**Đường đi của dữ liệu**
- **Từ EC2 app:** OTel Collector (agent) → OTLP gRPC qua mạng nội bộ VPC → collector gateway → Tempo (trace), Mimir (metric, nhận qua remote write), Loki (log).
- **Từ trình duyệt:** OTel Web SDK → `/api/v1/otel` (proxy qua API, có rate limit) → collector.

**Code server**
- Dùng OTel SDK cho Python.
- Log dạng JSON qua `structlog` / `logging`, tự gắn `trace_id`, `span_id` vào mỗi dòng.
- Histogram thời gian bật exemplar.

**Grafana**
- **Datasource:** Tempo, Loki, Mimir và CloudWatch (để xem RDS).
- **Liên kết:**
  - Từ trace sang log (Tempo → Loki theo `trace_id`).
  - Từ log sang trace (derived field trong Loki).
  - Từ metric sang trace qua exemplar.
- **Dashboard tối thiểu:**
  - RED của API
  - Hàng đợi arq
  - LLM: token, độ trễ, chi phí
  - Pool DB
  - Nguồn LPR theo khu

**Truy cập:** Grafana không mở ra Internet. Người xem dùng SSM port forwarding, hoặc mở qua CloudFront có xác thực nếu cần trình chiếu.

**Quy tắc cardinality** (bắt buộc với mọi metric):
- Không dùng ID người dùng, ID lượt đỗ, biển số hay URL thô làm nhãn.
- Nhãn `zone` được phép, vì số khu nhỏ và cố định.

## Consequences

**Tích cực**
- Liên kết đầy đủ metric → trace → log; quan sát được cả bước dừng chờ duyệt và job nền.
- Máy app có sự cố vẫn xem được dữ liệu đến thời điểm gặp sự cố.
- Không phụ thuộc dịch vụ SaaS; dữ liệu ở trong VPC.

**Tiêu cực**
- Thêm một máy phải vận hành và trả tiền. Dữ liệu chỉ giữ ngắn hạn, không có HA.
- Một người trong đội phải dành thời gian dựng và cấu hình, ước tính 2–3 ngày.
- Theo dõi LLM (prompt, eval) không chi tiết bằng công cụ chuyên dụng như Langfuse. Bù lại bằng span GenAI và kết quả eval lưu trong repo.

## Observability Impact

Đây là quyết định nền tảng cho toàn bộ telemetry. Hướng dẫn chi tiết (tên metric, span, cách xem trên Grafana) sẽ được ghi trong `docs/08-operations/observability-guide.md` khi triển khai.
