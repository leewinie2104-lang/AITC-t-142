---
name: new-agent-workflow
description: Build or extend a ParkSmart LangGraph agent workflow (W0 supervisor, W1–W7) under server/src/app/agent/workflows — state, deterministic steps, LLM-suggestion steps, HITL interrupt/resume, prompts, guardrails and eval cases. Use when implementing a workflow from docs/01-product/05-backlog.md#2-tính-năng or adding a step to one.
---

# New / extended agent workflow

Read first: `docs/01-product/05-backlog.md#2-tính-năng` (the **Worker Agent** column lists what each feature needs
from W0–W7, with `[LLM]` / `[HITL]` / RAG marked), BR-xx in `docs/01-product/02-prd.md`, ADR-0010 (orchestration, HITL), ADR-0007 (LLM), `server/AGENTS.md`.

## Layout

```
server/src/app/agent/workflows/wN_<name>/
  state.py   # TypedDict / dataclass state; ids and pseudonyms only, never raw names/plates
  steps.py   # one async function per step; no langgraph import here
  graph.py   # the ONLY file importing langgraph: nodes, edges, interrupt points
```
Entry point: `agent/usecase/start_workflow.py`; resume: `agent/usecase/resume_workflow.py`
(queued via `agent/delivery/jobs/`).

## Steps

1. Map each backlog step to a function in `steps.py`, keeping the backlog numbering in docstrings
   (`"""W1.3 [TĐ] rule engine checks rent permission"""`).
2. `[TĐ]` steps call other modules' **use cases** through ports injected into the workflow — never their
   infrastructure. Decisions (eligibility, permission, fee, approval) come only from these deterministic calls.
3. `[LLM]` steps: `get_llm("classify" | "generate")` through the agent's `LLMPort`, input pseudonymized
   (BR-14), prompt from `server/prompts/` (skill `new-prompt`), output validated with
   `guardrails.validate_output(...)` into a Pydantic schema. LLM output is a *suggestion* stored in state.
4. `[HITL]` steps (W2, W3, W5, W6): `interrupt()` in `graph.py` → `approval` enqueue with `zone_id` of the
   slot owner (BR-18) and `thread_id` → resume through the `agent` queue job, never inside an HTTP request.
   Requires the Postgres checkpointer.
5. `[RAG]` steps (W7): retrieve via the `knowledge` module port; answer must cite (`citation_rules.md`).
6. Observability: span per step named `agent.wN.<step>`; no PII in attributes.
7. Tests `server/tests/unit/agent/test_wN_<name>.py`: steps with fake ports and patched LLM; graph routing
   for each branch (allowed / blocked / TH3 fallback / HITL pause+resume).
8. Eval: add ≥ 5 cases for the workflow with skill `eval-case` (happy, blocked, edge, safety).
9. Verify: `make check`, `python .codex/hooks/check_arch.py --all`, `make eval`.
