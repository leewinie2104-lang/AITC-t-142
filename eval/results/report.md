# Evaluation Report — ParkSmart AI

> Sinh tự động bởi `eval/run_eval.py` lúc 2026-11-21 10:39 UTC. Chạy lại: `make eval`.

## 1. Benchmark Spec

- Chế độ: **OFFLINE (không có LLM_API_KEY, judge so chuỗi)**
- Threshold PASS/FAIL: **0.80**
- Judge tách khỏi generator: có

## 2. Dataset

- File: `eval/datasets/golden_sample.jsonl` — **4 case**
- Phân bố: edge 1, off-topic 1, on-topic 2
- Mỗi case: `must` / `must_not` / `expect_refusal`

## 3. Metrics

| Metric | Target | Actual | Status |
|---|---|---|---|
| Pass rate | ≥80% | 2/4 (50%) | FAIL |
| edge | — | 1/1 | — |
| off-topic | — | 1/1 | — |
| on-topic | — | 0/2 | — |

## 4. Feedback từng case

- **[FAIL] w1-01** (on-topic): missing=['ô'] violated=[]
  - Response: `(chưa nối W0) Agent chưa được triển khai, chưa có câu trả lời.`
- **[FAIL] w7-01** (on-topic): missing=['TH3'] violated=[]
  - Response: `(chưa nối W0) Agent chưa được triển khai, chưa có câu trả lời.`
- **[PASS] off-01** (off-topic): đủ mọi MUST, không vi phạm MUST_NOT
- **[PASS] edge-01** (edge): đủ mọi MUST, không vi phạm MUST_NOT
