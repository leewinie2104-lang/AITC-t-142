# Evaluation — ParkSmart AI

Deliverable #10 của BTC: report nằm ở `eval/results/report.md`, sinh lại bằng `make eval`.
Thư mục này ở gốc repo (không nằm trong `server/`) vì BTC chấm đúng đường dẫn trên.
Code được chấm nằm ở `server/src/app/` (xem [server-structure](../docs/05-development/server-structure.md)).

## Files

| File | Vai trò |
|---|---|
| `datasets/golden_sample.jsonl` | Golden case: `must` / `must_not` / `expect_refusal`. Hiện là 4 case mẫu, cần ≥45 case trước Demo Day |
| `run_eval.py` | Chạy agent qua từng case, chấm bằng judge, ghi report |
| `judge.py` | LLM-as-Judge chấm theo rubric (faithfulness, helpfulness, safety, citation) |
| `cost_benchmark.py` | Ước chi phí một lượt eval theo model |
| `thresholds.yaml` | Ngưỡng PASS/FAIL |
| `results/report.md` | Report mới nhất |

## Chạy

```bash
make eval                     # = python3 eval/run_eval.py (không cần API key)
python3 eval/run_eval.py --strict   # exit 1 nếu dưới ngưỡng, dùng cho CI
python3 eval/cost_benchmark.py
```

## Hiện trạng

`run_agent()` trong `run_eval.py` mới chỉ có guardrail đầu vào, vì workflow W0 chưa được
viết. Case `edge` đã pass; case `on-topic` sẽ fail cho tới khi nối W0 (`agent/usecase/chat_turn`).
