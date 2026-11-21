# ADR-0007: Dùng Claude qua Amazon Bedrock

- **Status**: Accepted (region chưa chốt, xem cuối mục Decision) · **Partly superseded by [ADR-0013](ADR-0013-dev-env-on-ci-runner-and-groq.md) (2026-11-21)**: khi dev gọi Groq qua API tương thích OpenAI (`LLM_API_KEY`, `LLM_BASE_URL`), chưa chuyển sang Bedrock; Bedrock để dành cho demo
- **Date**: 2026-11-17 (cập nhật cùng ngày: ẩn danh nằm trong wrapper `LLMPort` cho mọi lần gọi, [ADR-0010](ADR-0010-backend-modules-agent-workflows-jobs.md))
- **Liên quan**: [Workflow Agent](../01-product/05-backlog.md#2-tính-năng) · [PRD §9](../01-product/02-prd.md#9-yêu-cầu-phi-chức-năng) · [ADR-0008](ADR-0008-opentelemetry-lgtm-on-dedicated-ec2.md)

## Context

- Template gọi OpenAI qua `ChatOpenAI` (`server/src/app/platform/llm/client.py`), có router 3 loại task `classify`, `generate`, `judge`.
- Ảnh kiến trúc đã chọn Claude trên Bedrock; đội có credit AWS. Nhu cầu LLM: phân loại ý định (W0), gợi ý (W1), đọc ảnh tranh chấp (W5,
  chỉ gợi ý), tóm tắt, trả lời có trích dẫn (W7).
- BR-14: LLM không thay rule engine; tên, biển số thay bằng mã giả trước khi gửi; cần xác nhận chuyển dữ liệu xuyên biên giới.

## Decision

- **Gọi model:** `langchain-aws` (`ChatBedrockConverse`) thay `ChatOpenAI`, giữ router; đổi model bằng `.env`.
  `classify`: Haiku 5.5 · `generate`: Haiku 5.5 khi dev, Opus 5.5 khi demo · `judge` (eval): Sonnet 5.5 (khác model `generate`).
- **Embedding:** model embedding trên Bedrock, lưu pgvector (ADR-0005).
- **Quyền:** EC2 dùng **IAM instance role**, `bedrock:InvokeModel*` giới hạn theo ARN model; không dùng access key.
- **Ẩn danh trong wrapper `LLMPort`** (`agent/infrastructure`): mọi lần gọi thay giá trị thật bằng mã giả rồi khôi phục. Không đặt ở W0 vì
  LLM còn được gọi ở W1, W2, W5, W7, và W5 do N1 kích hoạt không qua W0. Ảnh W5 chỉ gửi sau khi che biển số; che lỗi thì bỏ bước đọc ảnh,
  chuyển BQL. Code ngoài `agent/` không gọi Bedrock trực tiếp (import-linter, ADR-0010).
- **Nơi gọi:** process `api` (chat, SSE) và `agent-worker`; `worker` không gọi LLM (ADR-0004).
- **Mock-first** cho test và CI; `max_tokens` mỗi task; AWS Budgets cảnh báo theo ngày.
- **Cần xác nhận trước khi dựng hạ tầng:** (1) region có Haiku / Sonnet / Opus 5.5 hay phải dùng cross-region inference profile (nếu có,
  ghi rõ dữ liệu đã ẩn danh có thể xử lý ở region khác); (2) quota request / token mỗi phút đủ cho demo; (3) model ID chính xác.

## Consequences

**Tích cực:** Dùng credit AWS, không quản lý API key, dữ liệu đi trong hạ tầng AWS; router cho phép model rẻ cho việc đơn giản.

**Tiêu cực:** Đổi code LLM client, thêm `langchain-aws`; model mới có thể lên Bedrock chậm hơn; quota mặc định có thể thấp, cần xin tăng sớm. · Dev local cần AWS SSO profile hoặc chạy mock.

## Observability Impact

- Mỗi lần gọi LLM là span `llm.<task>`, con của `agent.<wN>.<step>`; thuộc tính GenAI của OTel (`gen_ai.system=aws.bedrock`,
  `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`); **không** ghi prompt hay response.
- Metric (nhãn chỉ model, task): `gen_ai_client_operation_duration_seconds`, `gen_ai_client_token_usage_total{type}`, `gen_ai_client_errors_total{error_type}`.
- Grafana ước lượng chi phí theo ngày từ số token × đơn giá cấu hình.
