---
paths:
  - "server/src/app/agent/**"
  - "server/src/app/knowledge/**"
  - "server/src/app/approval/**"
  - "server/src/app/platform/llm/**"
  - "server/src/app/platform/prompts/**"
  - "server/prompts/**"
---

# Backend rules — agent, LLM, prompts, HITL

Loads on top of `.claude/rules/backend.md`. Background: `.claude/references/llm-usage.md` · ADR-0007 · ADR-0010.
Skills: `new-agent-workflow`, `new-prompt`, `eval-case`.

- Every LLM call goes through `app.platform.llm.client.get_llm(task_type)` (later the `LLMPort`).
  Names and plates are pseudonymized before the call and restored after.
- Prompts live in `prompts/*.md` with `{{placeholders}}`, loaded via `app.platform.prompts.loader`. Never inline.
- All agent user input passes `app/agent/infrastructure/guardrails.py`; LLM output is validated into a Pydantic model.
- LLM output is a suggestion only: route it through a deterministic step or the rule engine before acting (BR-14).
- HITL (W2, W3, W5, W6): `interrupt()` → `approval` enqueue → BQL approves via REST → `agent.resume_workflow`
  job (queue `agent`). Never resume inside the HTTP request. Approver = BQL of the slot's zone (BR-18).
- `ai_decision_log` is append-only.
- Tests patch `get_llm`; never call a real model. Agent, prompt or guardrail change → add eval cases and run `make eval`.
