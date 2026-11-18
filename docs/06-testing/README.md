# 06-testing — Kiểm thử và đánh giá

> **Thư mục này trả lời:** kiểm thử những gì, ở tầng nào, và làm sao chứng minh Agent đạt chất lượng cho Demo Day.

## Tổng quan

**Chưa có tài liệu.** Kiểm thử có hai phần:

| Phần | Ở đâu | Kiểm tra gì |
|---|---|---|
| **Test code** | `server/tests/` | Use case, rule engine, API, bước LangGraph, tích hợp Postgres |
| **Eval Agent** | `eval/` ở gốc repo | Câu trả lời của Agent theo golden case; BTC chấm `eval/results/report.md` |

Eval cần **≥45 case trước Demo Day** (hiện có 4 case mẫu) — thuộc Ưu tiên 2 trong [backlog](../01-product/backlog/README.md).

## Tầng test

| Tầng | Thư mục | Ghi chú |
|---|---|---|
| Unit | `server/tests/unit/<module>/` | Port giả, không DB / LLM / mạng |
| Agent | `server/tests/unit/agent/` | Patch `get_llm`, không gọi model thật |
| Tích hợp | `server/tests/integration/` | Postgres thật, đánh dấu `@pytest.mark.integration` |
| Eval | `eval/datasets/*.jsonl` | `must` / `must_not` / `expect_refusal`; judge chấm theo rubric |

Bảng quy tắc (L1–L4 × phạm vi mở × TH1/TH2/TH3) viết bằng `@pytest.mark.parametrize`.

## Nối với yêu cầu

Mỗi AC trong [04-user-stories](../01-product/04-user-stories.md) nên có ít nhất một test hoặc eval case. Use case tương ứng: [06-traceability](../01-product/06-traceability.md).

## Lệnh

`make test` · `make check` · `make eval` · `python3 eval/run_eval.py --strict` (CI, exit 1 nếu dưới ngưỡng). Skill: `eval-case`.

## Nên có

| File gợi ý | Nội dung |
|---|---|
| `01-test-strategy.md` | Phạm vi từng tầng, cái gì bắt buộc test trước khi merge |
| `02-eval-plan.md` | Phân bổ ≥45 case theo workflow, an toàn, off-topic; ngưỡng trong `eval/thresholds.yaml` |
| `03-demo-scenarios.md` | Kịch bản chạy thử demo trên 2–3 khu (tuần 4) |
