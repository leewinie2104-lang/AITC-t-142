# ADR-0007: Dùng Claude qua Amazon Bedrock

- **Status**: Accepted (region chưa chốt, xem mục cần xác nhận)
- **Date**: 2026-11-17
- **Liên quan**: [Workflow AI Agent](../01-product/backlog/agent-workflows.md) · [PRD §9 Tuân thủ](../01-product/prd.md#9-yêu-cầu-phi-chức-năng) · [ADR-0008](ADR-0008-opentelemetry-lgtm-on-dedicated-ec2.md)

## Context

- **Hiện trạng code:** template đang gọi OpenAI qua `ChatOpenAI` trong `src/services/llm.py`, có router chia 3 loại task: `classify`, `generate`, `judge`.
- **Lựa chọn đã có:** ảnh kiến trúc ParkSmart AI đã chọn Claude trên Bedrock. Đội có credit AWS.
- **Nhu cầu dùng LLM:**
  - Phân loại ý định (W0).
  - Đề xuất khung giờ (W2).
  - Đọc ảnh tranh chấp (W5, chỉ để gợi ý).
  - Tóm tắt.
  - Trả lời có trích dẫn nội quy (W7, RAG).
- **Ràng buộc từ PRD (BR-14):**
  - LLM không thay rule engine.
  - Tên và biển số phải được thay bằng mã giả trước khi gửi.
  - Cần xác nhận về chuyển dữ liệu xuyên biên giới.

## Decision

- **Gọi model:** dùng `langchain-aws` (`ChatBedrockConverse`). Thay `ChatOpenAI` nhưng giữ nguyên router 3 loại task. Đổi model chỉ bằng `.env`.

  | Task | Khi dev | Khi demo |
  |------|---------|----------|
  | `classify` (W0, guardrail mềm) | Haiku 5.5 | Haiku 5.5 |
  | `generate` (trả lời, đề xuất, tóm tắt, đọc ảnh) | Haiku 5.5 | Opus 5.5 |
  | `judge` (eval) | Sonnet 5.5 (khác model với `generate`) | Sonnet 5.5 |

- **Embedding cho RAG:** dùng model embedding trên Bedrock, lưu vào pgvector (ADR-0005).
- **Quyền truy cập:** EC2 gọi Bedrock bằng **IAM instance role**, quyền `bedrock:InvokeModel*` giới hạn theo ARN của các model trên. Không dùng access key.
- **Ẩn danh:** áp dụng trước mọi lần gọi (W0 bước 3) và khôi phục sau khi nhận kết quả (W0 bước 6).
- **Mock-first:** giữ chế độ mock của template để test và CI không gọi Bedrock thật.
- **Giới hạn chi phí:** đặt `max_tokens` cho mỗi task; AWS Budgets cảnh báo theo ngày.

**Cần xác nhận trước khi dựng hạ tầng:**
1. **Region:** Haiku / Sonnet / Opus 5.5 có sẵn ở region nào (ví dụ `ap-southeast-1`) hay phải dùng **cross-region inference profile**. Nếu phải dùng cross-region, ghi rõ dữ liệu (đã ẩn danh) có thể được xử lý ở region khác.
2. **Quota** request/token mỗi phút của tài khoản, đủ cho buổi demo hay chưa.
3. **Model ID chính xác** trên Bedrock của từng model.

## Consequences

**Tích cực**
- Dùng credit AWS; không phải quản lý API key (dùng IAM role); dữ liệu đi trong hạ tầng AWS.
- Router 3 loại task cho phép tiết kiệm: model rẻ cho việc đơn giản, model mạnh chỉ dùng khi demo.

**Tiêu cực**
- Phải đổi code `llm.py` và thêm dependency `langchain-aws`.
- Model mới có thể ra trên Bedrock chậm hơn so với Anthropic API; quota mặc định có thể thấp, cần xin tăng sớm.
- Dev local cần AWS credentials (SSO profile) hoặc phải chạy mock.

## Observability Impact

- **Span:** mỗi lần gọi LLM là một span `llm.<task>`, thuộc tính theo semantic conventions GenAI của OTel: `gen_ai.system=aws.bedrock`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`. **Không** ghi prompt hay response vào span (có thể chứa dữ liệu chưa ẩn danh).
- **Metric** (nhãn chỉ gồm model và task):
  - `gen_ai_client_operation_duration_seconds{model,task}`
  - `gen_ai_client_token_usage_total{model,task,type}`
  - `gen_ai_client_errors_total{model,task,error_type}`
- **Chi phí:** Grafana tính chi phí ước lượng theo ngày từ số token × đơn giá cấu hình.
