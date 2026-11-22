# ADR-0010: Server theo module, tầng điều phối `agent/` cho W0–W7, job N1–N9 là delivery adapter

- **Status**: Accepted
- **Date**: 2026-11-17 · viết lại 2026-11-22 (plan 021: gộp N9 của plan 013 và phần outbox của ADR-0011)
- **Liên quan**: [Backlog](../01-product/05-backlog.md) · [ADR-0004](ADR-0004-fastapi-langgraph-arq-on-ec2-docker-compose.md) · [ADR-0007](ADR-0007-claude-via-amazon-bedrock.md) · [Cấu trúc server](../04-development/01-server-structure.md)

## Context

- Backlog có 14 module (M1–M14), 8 workflow Agent (W0–W7), 9 job nền (N1–N9). Workflow cắt ngang nhiều module; đặt nó trong
  một module sẽ buộc import chéo, điều Clean Architecture của đội cấm.
- Một workflow có nhiều cửa vào: chat (W0), nút trên app ("Tôi về sớm"), sự kiện từ job nền, BQL duyệt rồi chạy tiếp (HITL).
- Rule engine quyết định, LLM chỉ gợi ý (BR-14); job nền chỉ phát hiện và chuẩn bị dữ liệu.

## Decision

- **Ba tầng:** **Module (M)** sở hữu dữ liệu và quy tắc, ở `app/<module>/{domain,usecase,delivery,infrastructure}`, chỉ import chính
  nó và `platform/` · **Workflow (W)** ở `app/agent/`, điều phối nhiều module, có LLM và HITL, import `usecase` + DTO của module ·
  **Job (N)** ở `app/<module sở hữu dữ liệu>/delivery/jobs/`, không gọi LLM, chỉ gọi usecase của module đó.
- **`agent/`:** `domain` (port `LLMPort`, `WorkflowEngine`), `usecase` (`chat_turn`, `start_workflow`, `resume_workflow`),
  `workflows/<wN>/` (`steps.py` không import langgraph, `graph.py`, `state.py`), `delivery`, `infrastructure`. Composition root:
  `main_api.py`, `main_worker.py`.
- **Phụ thuộc:** module không import lẫn nhau, cần dữ liệu module khác thì khai báo port trong `domain/ports.py`; bước workflow là hàm
  `async (state, deps) -> partial_state`, nhãn `[TĐ]` / `[LLM]` / `[HITL]`; rule engine (`policy/domain`) là hàm thuần không I/O.
  `import-linter` trong CI kiểm các luật này.
- **Giao tiếp:** trong một luồng gọi usecase cùng process; việc kéo theo việc khác và job kích hoạt workflow đi qua port
  `platform.publish()` (ghi `notification` cùng transaction, đẩy sau commit; outbox khi cần, ADR-0011). HITL: `interrupt()` →
  `approval.enqueue` → BQL duyệt qua REST → enqueue `agent.resume_workflow`.
- **Idempotent:** node chứa `interrupt()` không có tác dụng phụ (LangGraph chạy lại cả node khi resume); bước ghi dữ liệu dùng
  `idempotency_key = thread_id:step`.
- **N9** (module `booking`, cron 1 phút) chuyển bản ghi quá hạn sang `expired` (booking `held`, thỏa thuận, yêu cầu duyệt, lịch chia
  sẻ) để ràng buộc chống trùng không khóa ô mãi; ca về sớm quá hạn → sự kiện cho W3.

## Consequences

- **Tích cực:** mỗi workflow một thư mục, thêm W / N không sửa module khác; bước workflow test bằng mock, rule engine test không cần mock.
- **Tiêu cực:** composition root dài vì gắn nhiều port; `agent/` phụ thuộc DTO của nhiều module nên đổi DTO có thể vỡ workflow, cần test workflow trong CI.

## Observability Impact

- Span `agent.<wN>.<step>`, `usecase.<Module>.<Op>`, `worker.<nN>.<job>`; thuộc tính `workflow.id`, `workflow.thread_id`, `zone.id`.
- Metric (nhãn `workflow` chỉ W0–W7, `outcome` tập cố định): `agent_workflow_runs_total`, `agent_workflow_duration_seconds` (exemplar), `agent_hitl_pending`.
