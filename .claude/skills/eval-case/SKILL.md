---
name: eval-case
description: Add, validate and run ParkSmart eval golden cases (eval/datasets/*.jsonl) for agent workflows, safety, off-topic and edge behaviour, then run make eval and summarize the report. Use when a workflow, prompt or guardrail changes, or to grow the dataset toward the 45+ cases required for Demo Day.
---

# Eval cases

Rules: `.claude/rules/eval.md`. Schema per line:

```json
{"id": "w1-02", "category": "on-topic", "query": "…", "must": ["…"], "must_not": ["…"], "expect_refusal": false, "notes": "W1 — blocked: L4 asks for TH1 slot (BR-01)"}
```

## Steps
1. Count current coverage:
   `python -c "import json,collections,pathlib;c=collections.Counter(json.loads(l)['category'] for l in pathlib.Path('eval/datasets/golden_sample.jsonl').read_text(encoding='utf-8').splitlines() if l.strip());print(c)"`
2. For the target workflow write cases covering: happy path, rule-engine block (cite BR), fallback (TH3 /
   public parking), ambiguous request, and at least one safety case (injection such as "bỏ qua hướng dẫn",
   "hãy duyệt luôn cho tôi", key leak, request for another resident's plate).
3. Use fake data only; `must` / `must_not` are short, phrasing-robust substrings. `notes` names the
   workflow and BR/AC.
4. Validate: every line parses as JSON, ids unique, categories in {on-topic, off-topic, safety, edge}.
5. Run `make eval`; summarize pass rate by category and list failing ids with cause (agent vs case).
   Never edit `eval/results/report.md` by hand and never lower `eval/thresholds.yaml`.
