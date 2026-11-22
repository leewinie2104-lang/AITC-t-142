# ADR-0008: OpenTelemetry, gửi lên Grafana Cloud free khi demo; LGTM tự dựng để sau

- **Status**: Accepted
- **Date**: 2026-11-17 · viết lại 2026-11-22 (plan 021: gộp phần quan sát của ADR-0012)
- **Liên quan**: [ADR-0004](ADR-0004-fastapi-langgraph-arq-on-ec2-docker-compose.md) · [ADR-0007](ADR-0007-claude-via-amazon-bedrock.md) · [ADR-0012](ADR-0012-lean-lightsail-prod-and-team-ci-runner.md)

## Context

- Cần trace xuyên suốt: client → API → node LangGraph → LLM → Postgres → job arq, nhất là luồng chờ BQL duyệt và luồng log cổng → worker → Agent.
- Cần liên kết metric (exemplar) → trace (`trace_id`) → log (lọc theo `trace_id`).
- Stack LGTM (Loki, Grafana, Tempo, Mimir) tự dựng cần ~4–6 GB RAM, không chạy được trên máy prod 2 GB (ADR-0012).

## Decision

- **Code:** OTel SDK Python; log JSON tự gắn `trace_id`, `span_id`; histogram thời gian bật exemplar.
- **Nơi nhận:** khi thêm OTel, gửi OTLP thẳng lên **Grafana Cloud free tier**. Không thêm LGTM vào máy prod.
- **Grafana:** liên kết trace → log, log → trace (derived field), metric → trace (exemplar). Dashboard tối thiểu: RED của API,
  hàng đợi arq, LLM (token, độ trễ), pool DB, log cổng theo khu.
- **Cardinality (bắt buộc):** không dùng ID người dùng, ID lượt đỗ, biển số hay URL thô làm nhãn; nhãn `zone` được phép.
- **Trước khi có OTel:** log container `json-file` (10 MB × 3), log Caddy dạng JSON.
- **Quay lại LGTM tự dựng** (máy riêng, giữ dữ liệu 7 ngày) khi vượt hạn mức free hoặc cần giữ dữ liệu trong hạ tầng.

## Consequences

- **Tích cực:** không tốn thêm máy; vẫn đủ liên kết metric → trace → log; máy prod sự cố vẫn xem được dữ liệu đã gửi.
- **Tiêu cực:** phụ thuộc SaaS và hạn mức free (giữ dữ liệu ngắn); theo dõi LLM không chi tiết bằng công cụ chuyên dụng,
  bù bằng span GenAI và kết quả eval.

## Observability Impact

Đây là nền tảng cho toàn bộ telemetry. Tên metric, span và cách xem trên Grafana ghi trong `docs/06-operations/` khi triển khai.
Không đưa PII, API key vào log hay span.
