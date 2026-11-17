"""Eval harness: chạy agent qua golden dataset, chấm bằng judge riêng, xuất report.

Giữ từ template của BTC (deliverable #10 nằm ở `eval/results/report.md`).
Chạy lại bằng một lệnh: `make eval`.

  - Dataset: eval/datasets/golden_sample.jsonl (mẫu; cần ≥45 case trước Demo Day).
  - Judge: model KHÁC generator; không có OPENAI_API_KEY thì dùng judge so chuỗi
    và ghi rõ "OFFLINE" trong report.
  - Agent: hàm `run_agent(case) -> str`. Hiện chỉ có guardrail đầu vào vì W0
    chưa được viết (ADR-0010). Khi có W0, thay thân hàm bằng usecase `ChatTurn`.

Chạy: python eval/run_eval.py [--dataset ...] [--threshold 0.8] [--strict]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

# Code server nằm ở server/src (ADR-0001)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server" / "src"))

from app.agent.infrastructure.guardrails import GuardrailViolation, guardrails  # noqa: E402
from app.platform.config.settings import get_settings  # noqa: E402
from app.platform.llm.client import get_llm  # noqa: E402

logger = logging.getLogger("parksmart.eval")

EVAL_DIR = Path(__file__).resolve().parent
DATASET_DEFAULT = EVAL_DIR / "datasets" / "golden_sample.jsonl"
REPORT_PATH = EVAL_DIR / "results" / "report.md"

REFUSAL = "Không thể xử lý yêu cầu này."
NOT_WIRED = "(chưa nối W0) Agent chưa được triển khai, chưa có câu trả lời."


# ---------------------------------------------------------------------------
# Phần 1 — Agent cần chấm
# ---------------------------------------------------------------------------

async def run_agent(case: dict) -> str:
    """Trả về câu trả lời của agent cho một case."""
    try:
        guardrails.check_input(case["query"])
    except GuardrailViolation:
        return REFUSAL
    return NOT_WIRED


# ---------------------------------------------------------------------------
# Phần 2 — Judge (tách khỏi generator)
# ---------------------------------------------------------------------------

class JudgeVerdict(BaseModel):
    """Schema judge — schema-first, sai schema là eval hỏng chứ không phải pass."""

    passed: bool
    reason: str = Field(min_length=1)
    needs_human_review: bool = False


_JUDGE_PROMPT = """<role>Bạn là judge ĐỘC LẬP với agent (model khác generator).</role>
<context>
Query: {query}
Response của agent: {response}
MUST (phải có ý nghĩa đó): {must}
MUST_NOT (không được có): {must_not}
Expect refusal: {expect_refusal}
</context>
<instructions>
Chấm passed chỉ khi: mọi MUST được thoả, không MUST_NOT nào vi phạm, và nếu
expect_refusal thì agent phải từ chối rõ ràng. Agent bịa dữ kiện -> fail.
</instructions>
<output_format>Đúng schema JudgeVerdict.</output_format>"""


async def llm_judge(case: dict, response: str) -> JudgeVerdict:
    structured = get_llm("judge").with_structured_output(JudgeVerdict)
    verdict = await structured.ainvoke(_JUDGE_PROMPT.format(
        query=case["query"], response=response,
        must=case.get("must", []), must_not=case.get("must_not", []),
        expect_refusal=case.get("expect_refusal", False),
    ))
    return JudgeVerdict.model_validate(verdict)


async def rule_judge(case: dict, response: str) -> JudgeVerdict:
    """Judge deterministic khi offline — substring check, không mang tính ngữ nghĩa."""
    low = response.lower()
    missing = [m for m in case.get("must", []) if m.lower() not in low]
    violated = [m for m in case.get("must_not", []) if m.lower() in low]
    if case.get("expect_refusal") and "không thể xử lý" not in low:
        missing.append("expect_refusal")
    if missing or violated:
        return JudgeVerdict(passed=False,
                            reason=f"missing={missing} violated={violated}",
                            needs_human_review=True)
    return JudgeVerdict(passed=True, reason="đủ mọi MUST, không vi phạm MUST_NOT")


# ---------------------------------------------------------------------------
# Phần 3 — Runner
# ---------------------------------------------------------------------------

async def main(dataset: Path, threshold: float, strict: bool) -> int:
    settings = get_settings()
    # Key rỗng hoặc còn là placeholder của .env.example -> chạy offline
    offline = not settings.openai_api_key or settings.openai_api_key.startswith("sk-your")
    mode = (
        "OFFLINE (không có OPENAI_API_KEY, judge so chuỗi)"
        if offline
        else f"LLM thật (judge={settings.model_judge})"
    )

    cases = [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line.strip()]
    judge = rule_judge if offline else llm_judge

    rows: list[dict[str, Any]] = []
    for case in cases:
        try:
            response = await run_agent(case)
            verdict = await judge(case, response)
            rows.append({"case": case, "response": response, "verdict": verdict})
        except Exception as exc:  # lỗi một case = fail case đó, không dừng cả lượt eval
            logger.error("FAILED case %s — %s", case["id"], exc)
            rows.append({"case": case, "response": "",
                         "verdict": JudgeVerdict(passed=False, reason=f"EXCEPTION: {exc}", needs_human_review=True)})

    report = render_report(mode, dataset, cases, rows, threshold)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(report)
    print(f"\n==> Đã ghi report: {REPORT_PATH}")

    pass_rate = sum(1 for r in rows if r["verdict"].passed) / len(rows) if rows else 0.0
    if pass_rate < threshold:
        print(f"REGRESSION: pass_rate={pass_rate:.2f} < threshold={threshold:.2f}")
        return 1 if strict else 0
    return 0


def render_report(mode: str, dataset: Path, cases: list[dict], rows: list[dict], threshold: float) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    total = len(rows)
    passed = sum(1 for r in rows if r["verdict"].passed)
    pass_rate = passed / total if total else 0.0
    categories = sorted({c["category"] for c in cases})

    def cat_rate(cat: str) -> str:
        sub = [r for r in rows if r["case"]["category"] == cat]
        return f"{sum(1 for r in sub if r['verdict'].passed)}/{len(sub)}"

    lines = [
        "# Evaluation Report — ParkSmart AI",
        "",
        f"> Sinh tự động bởi `eval/run_eval.py` lúc {now}. Chạy lại: `make eval`.",
        "",
        "## 1. Benchmark Spec",
        "",
        f"- Chế độ: **{mode}**",
        f"- Threshold PASS/FAIL: **{threshold:.2f}**",
        "- Judge tách khỏi generator: có",
        "",
        "## 2. Dataset",
        "",
        f"- File: `eval/datasets/{dataset.name}` — **{len(cases)} case**",
        "- Phân bố: " + ", ".join(f"{c} {sum(1 for x in cases if x['category'] == c)}" for c in categories),
        "- Mỗi case: `must` / `must_not` / `expect_refusal`",
        "",
        "## 3. Metrics",
        "",
        "| Metric | Target | Actual | Status |",
        "|---|---|---|---|",
        f"| Pass rate | ≥{threshold:.0%} | {passed}/{total} ({pass_rate:.0%}) | {'PASS' if pass_rate >= threshold else 'FAIL'} |",
    ]
    lines += [f"| {cat} | — | {cat_rate(cat)} | — |" for cat in categories]
    lines += ["", "## 4. Feedback từng case", ""]
    for r in rows:
        mark = "PASS" if r["verdict"].passed else "FAIL"
        lines.append(f"- **[{mark}] {r['case']['id']}** ({r['case']['category']}): {r['verdict'].reason}")
        if not r["verdict"].passed:
            lines.append(f"  - Response: `{r['response'][:200]}`")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ParkSmart eval harness")
    parser.add_argument("--dataset", type=Path, default=DATASET_DEFAULT)
    parser.add_argument("--threshold", type=float, default=0.8)
    parser.add_argument("--strict", action="store_true", help="Exit 1 nếu dưới threshold (dùng cho CI)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    raise SystemExit(asyncio.run(main(args.dataset, args.threshold, args.strict)))
