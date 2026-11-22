# Eval rules

`eval/results/report.md` is Demo Day deliverable #10 and is graded at this exact path. Keep `eval/` at repo root.

- **Run**: `make eval` (offline, no API key) · `python3 eval/run_eval.py --strict` (exit 1 below thresholds).
  Cost estimate: `python3 eval/cost_benchmark.py`.
- **Dataset**: `datasets/golden_sample.jsonl`, one JSON object per line:
  `{"id", "category", "query", "must", "must_not", "expect_refusal", "notes"}`.
  - `id`: `<workflow>-NN` (`w1-01`, `w7-03`) or `off-NN`, `safety-NN`, `edge-NN`; unique.
  - `category`: `on-topic` | `off-topic` | `safety` | `edge`.
  - `query`: Vietnamese, realistic, no real personal data (fake names, plates like `30A-123.45`).
  - `must` / `must_not`: short substrings checked in the answer; keep them robust to phrasing.
  - Target ≥ 45 cases before Demo Day, covering every implemented workflow plus safety (prompt
    injection, key leak, PII), off-topic and refusal cases.
- **Thresholds**: `thresholds.yaml`. Do not lower a threshold to make a run pass — fix the agent or the case.
  Every `safety` case must pass.
- **Judge** (`judge.py`): must use `get_llm("judge")`; judge model ≠ generate model (enforced in
  `platform/llm/client.py`).
- **Agent hook**: `run_agent(case)` in `run_eval.py` is the only bridge to the server; when W0 exists it
  calls the `ChatTurn` use case. Do not import workflow internals.
- Regenerate `results/report.md` only through `run_eval.py`; never hand-edit numbers in it.
