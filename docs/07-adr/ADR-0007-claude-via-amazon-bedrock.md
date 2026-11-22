# ADR-0007: LLM: Groq khi dev, Claude qua Amazon Bedrock khi demo; ẩn danh trong `LLMPort`

- **Status**: Accepted (region Bedrock chưa chốt, xem "Cần xác nhận")
- **Date**: 2026-11-17 · viết lại 2026-11-22 (plan 021: gộp phần LLM của ADR-0013)
- **Liên quan**: [ADR-0010](ADR-0010-backend-modules-agent-workflows-jobs.md) · [ADR-0013](ADR-0013-dev-env-on-ci-runner-and-groq.md) · [PRD BR-14](../01-product/02-prd.md#5-quy-tắc-nghiệp-vụ)

## Context

- Nhu cầu LLM: phân loại ý định (W0), đề xuất ghép (W2), đọc ảnh tranh chấp (W5), tóm tắt, trả lời có trích dẫn (W7).
- BR-14: LLM chỉ gợi ý, không thay rule engine; tên và biển số thay bằng mã giả trước khi gửi.
- Credit AWS cần giữ cho demo; dev thử nhiều lần nên cần LLM miễn phí.

## Decision

- **Một client chung** `get_llm(task)` (`platform/llm/client.py`), router 3 task: `classify`, `generate`, `judge` (eval, khác model `generate`).
- **Dev:** Groq qua API tương thích OpenAI (`LLM_API_KEY`, `LLM_BASE_URL`), model trong `.env.example`. Unit test và CI dùng mock.
- **Demo:** Claude trên Bedrock (`langchain-aws`), quyền qua IAM role giới hạn ARN model, không access key; đổi model bằng `.env`.
- **Ẩn danh trong wrapper `LLMPort`** (`agent/infrastructure`): mọi lần gọi thay giá trị thật bằng mã giả rồi khôi phục. Ảnh chỉ gửi
  sau khi che biển số; che lỗi thì bỏ bước đọc ảnh, chuyển BQL. Code ngoài `agent/` không gọi LLM (import-linter).
- **Nơi gọi:** process `api` và `agent-worker`; `worker` (queue `bg`) không gọi LLM (ADR-0004).
- `max_tokens` theo task; cảnh báo ngân sách theo ngày.

## Consequences

- **Tích cực:** dev miễn phí, demo dùng credit AWS; đổi nhà cung cấp chỉ đổi `.env`; router cho phép model rẻ cho việc đơn giản.
- **Tiêu cực:** Groq free có rate limit theo ngày, eval lớn có thể chạm; hành vi model dev và demo khác nhau nên phải chạy eval
  trên Bedrock trước Demo Day; quota Bedrock mặc định có thể thấp.

## Observability Impact

- Mỗi lần gọi là span `llm.<task>`, con của `agent.<wN>.<step>`; thuộc tính GenAI (`gen_ai.system`, `gen_ai.request.model`,
  `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`); **không** ghi prompt hay response. Dev có thể bật LangSmith free.
- Metric (nhãn chỉ model, task): `gen_ai_client_operation_duration_seconds`, `gen_ai_client_token_usage_total{type}`, `gen_ai_client_errors_total{error_type}`.

## Cần xác nhận

- Region Bedrock có model cần dùng hay phải dùng cross-region inference profile; quota token mỗi phút; model ID chính xác.
