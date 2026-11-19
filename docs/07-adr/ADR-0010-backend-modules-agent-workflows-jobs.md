# ADR-0010: Cấu trúc server theo module, tầng điều phối `agent/` cho W0–W7 và job N1–N8 là delivery adapter

- **Status**: Accepted · **Partly superseded by [ADR-0011](ADR-0011-mvp-simplifications.md) (2026-11-18)**: outbox, bảng `idempotency_keys`, metric `outbox_lag_seconds` (demo: `notification` cùng transaction + port `platform.publish()`; cột UNIQUE `idempotency_key` từng bảng). Cấu trúc module / `agent/` / job giữ nguyên
- **Date**: 2026-11-17
- **Liên quan**: [Backlog](../01-product/backlog/README.md) · [ADR-0004](ADR-0004-fastapi-langgraph-arq-on-ec2-docker-compose.md) · [ADR-0005](ADR-0005-rds-postgres-asyncpg-rls-alembic-sql.md) · [ADR-0007](ADR-0007-claude-via-amazon-bedrock.md) · [Cây thư mục server](../04-development/01-server-structure.md) · [ảnh](../images/ParkSmartAI-arch-backend-folders.png)

## Context

- Backlog có 14 module (M1–M14), 8 workflow Agent (W0–W7), 8 job nền (N1–N8). Workflow cắt ngang nhiều module (W1 gọi M1, M2, M3, M5; W2 gọi M4, M6, M7); đặt workflow trong một module sẽ buộc import chéo, điều Clean Architecture của đội cấm.
- Một workflow có nhiều cửa vào: chat qua W0, nút trên app (W3 "Tôi về sớm"), sự kiện từ job nền (N2 → W4), BQL duyệt rồi chạy tiếp (HITL).
- Rule engine quyết định, LLM chỉ gợi ý (BR-14); job nền chỉ phát hiện và chuẩn bị dữ liệu.
- Template đặt graph LangGraph trong `chat/infrastructure`, không mở rộng được cho 8 workflow.

## Decision

- **Ba tầng:** **Module (M)** sở hữu dữ liệu và quy tắc, ở `app/<module>/{domain,usecase,delivery,infrastructure}`, chỉ import chính nó và `platform/` · **Workflow Agent (W)** điều phối nhiều module, có LLM và HITL, ở `app/agent/`, import `usecase` + DTO của mọi module · **Job nền (N)** không gọi LLM, ở `app/<module sở hữu dữ liệu>/delivery/jobs/`, chỉ gọi usecase của module đó.
- **`agent/`:** `domain` (Intent, PseudonymMap, port `LLMPort` / `WorkflowEngine`), `usecase` (`chat_turn`, `start_workflow`, `resume_workflow`), `workflows/<wN>/` (`steps.py` không import langgraph, `graph.py`, `state.py`), `delivery` (REST SSE chat, jobs), `infrastructure` (runner, PostgresSaver, pseudonymizer, Bedrock client). Hai composition root `main_api.py`, `main_worker.py`.
- **Phụ thuộc:** module không import lẫn nhau, cần dữ liệu module khác thì khai báo port trong `domain/ports.py`, composition root gắn vào · mỗi bước workflow là hàm thuần `async (state, deps) -> partial_state` (`[TĐ]` gọi usecase, `[LLM]` gọi `LLMPort`); chỉ `graph.py` và `agent/infrastructure` import langgraph · rule engine (`policy/domain`) là hàm thuần không I/O · `import-linter` trong CI kiểm: không import chéo module, `domain` không import thư viện ngoài, job `bg` không import `platform.llm`.
- **Giao tiếp:** trong một luồng, bước workflow gọi usecase cùng process · thay đổi kéo theo việc khác và job kích hoạt workflow: qua outbox (demo: `platform.publish()`, ADR-0011) · từ app: `POST /api/v1/workflows/early-return` → `StartWorkflow` · HITL: node `interrupt()` → `approval.Enqueue(zone_id, thread_id)` → BQL duyệt qua REST → enqueue `agent.resume_workflow`, không resume trong HTTP request.
- **Idempotent:** LangGraph chạy lại cả node chứa `interrupt()` khi resume nên node đó không có tác dụng phụ; mọi bước có ghi dữ liệu nhận `idempotency_key = thread_id:step`, DB có UNIQUE trên khóa này. **Ẩn danh** nằm trong wrapper `LLMPort` (ADR-0007).

## Consequences

**Tích cực:** mỗi workflow là một thư mục, thêm W / N không sửa module khác; bước workflow test bằng mock không cần LangGraph, rule engine test
không cần mock; cùng workflow chạy từ chat, app, job hoặc sau duyệt nhờ `StartWorkflow` / `ResumeWorkflow`.

**Tiêu cực:** thêm hạ tầng (import-linter; outbox, relay khi quay lại); composition root dài vì gắn nhiều port; `agent/` phụ thuộc usecase của
nhiều module, đổi DTO có thể vỡ workflow nên cần test workflow trong CI.

## Observability Impact

- Span `agent.<wN>.<step>` (ví dụ `agent.w1.check_eligibility`), `usecase.<Module>.<Op>`, `worker.<nN>.<job>`; thuộc tính `workflow.id`, `workflow.thread_id`, `zone.id`.
- `traceparent` đi theo payload job arq → metadata lần chạy LangGraph, nên chuỗi job → workflow → thông báo nằm trong một trace.
- Metric (nhãn `workflow` chỉ W0–W7, `outcome` tập cố định): `agent_workflow_runs_total{workflow,outcome}`, `agent_workflow_duration_seconds{workflow}` (exemplar), `agent_hitl_pending{workflow}`.
