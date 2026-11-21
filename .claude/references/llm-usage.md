# LLM usage in ParkSmart code

Rules for any code that calls a language model. Decision: `docs/07-adr/ADR-0007-claude-via-amazon-bedrock.md`.

## One entry point

```python
from app.platform.llm.client import get_llm

llm = get_llm("classify")   # cheap model, temperature 0 — intent, soft guardrails
llm = get_llm("generate")   # strong model — answers, suggestions, summaries, image reading
llm = get_llm("judge")      # eval only; must differ from generate (raises otherwise)
```

- Models come from `.env` (`MODEL_CLASSIFY`, `MODEL_GENERATE`, `MODEL_JUDGE`); never hard-code a model id.
- Current code uses `ChatOpenAI` against any OpenAI-compatible endpoint (dev: Groq via `LLM_BASE_URL`, ADR-0013);
  ADR-0007 later moves to `ChatBedrockConverse` (Claude Haiku in dev, Opus for
  the demo, a different model as judge) behind an `LLMPort` that pseudonymizes inputs. Keep call sites on
  `get_llm` / `LLMPort` so the switch is one file.

## Hard rules

1. **BR-14**: names and licence plates are replaced with pseudonyms before the call and restored after.
2. The LLM **suggests**; eligibility, rent permission, fees and approvals come from `policy/domain`
   or a human (BQL). Never branch an authorization decision on LLM text.
3. Prompts live in `server/prompts/*.md` (skill `new-prompt`), loaded with `load_prompt()` / `render()`.
4. Inputs go through `guardrails.check_input()`; outputs through `check_output_text()` and
   `validate_output(raw, PydanticModel)`. Handle `GuardrailViolation` explicitly — no silent fallback.
5. Only `agent/` (and `knowledge/` for RAG) call the LLM. Background jobs and `policy/` never import `platform.llm`.
6. Unit tests patch the LLM; eval runs offline without keys (string judge) and online with `get_llm("judge")`.
7. Log token usage / latency as span attributes, never prompt content with PII.

## Cost

`python3 eval/cost_benchmark.py` estimates one eval run; `eval/thresholds.yaml` caps it
(`cost_per_run_max_usd`). Prefer `classify` for routing and short structured outputs.
