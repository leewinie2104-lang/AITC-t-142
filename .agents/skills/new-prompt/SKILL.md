---
name: new-prompt
description: Add or change a ParkSmart LLM prompt in server/prompts (Markdown with {{placeholders}}, loaded via app.platform.prompts.loader), with output schema, guardrail validation, tests and eval cases. Use for any new LLM step (intent classification, suggestions, summaries, RAG answers, judge rubric).
---

# New / changed prompt

## Rules
- File `server/prompts/<workflow>_<purpose>.md` (e.g. `w0_intent.md`). Prompt text never lives in Python.
- Structure like `system_prompt.md`: `<role>`, `<context>`, `<instructions>`, `<rules>{{shared_rules}}</rules>`,
  `<output_format>` with an exact JSON schema. Content is Vietnamese (user-facing), placeholders `{{snake_case}}`.
- The prompt asks for a **suggestion**; it must say the model cannot approve, deny, set fees or eligibility
  (BR-14) and must answer "tôi không chắc" when context is insufficient.
- Only pseudonyms reach the prompt (`USER_1`, `PLATE_1`); never real names/plates.
- RAG prompts include `citation_rules.md` requirements.

## Steps
1. Write the prompt file; list its placeholders in a comment at the top.
2. Load with `load_prompt("<file>.md")` and `render(template, **values)` from `app.platform.prompts.loader`.
3. Define a Pydantic output model and validate with `guardrails.validate_output(raw, Model)`; handle
   `GuardrailViolation` explicitly.
4. Choose the task type for `get_llm`: `classify` (temperature 0) or `generate`.
5. Unit test: render with sample values (no `{{` left), and the step with a patched LLM returning valid and
   invalid JSON.
6. Add eval cases (skill `eval-case`) and run `make eval`; report pass-rate change.
