---
name: new-background-job
description: Add a ParkSmart background job N1–N8 (arq, queue "bg") in the owning module's delivery/jobs folder, register it in main_worker.BgWorkerSettings, emit outbox events instead of acting, and test it. Use for LPR log processing, overstay checks, daily reconciliation, forecasts, expiry scans and KPI aggregation.
---

# New background job

Owners (from ADR-0010): N1, N2 → `access` · N3, N7, N8 → `reporting` · N4 → `sharing` · N5 → `dispute` ·
N6 → `eligibility`. Spec: `docs/01-product/backlog/background-workflows.md`.

## Rules
- File: `server/src/app/<module>/delivery/jobs/nX_<name>.py`, one async function `nX_<name>(ctx, ...)`.
- The job only **detects** and calls its module's use case, which writes an **outbox event**; agent
  workflows (W3/W4/W5/W6) act on those events. Jobs never call another module or `app.platform.llm`.
- Idempotent: safe to re-run; dedupe by event id (BR-13 for LPR duplicates).
- Zone-scoped queries; no PII in logs.

## Steps
1. Write/extend the use case in `<module>/usecase/` (skill `new-usecase`) that holds the logic.
2. Add the job function calling that use case; read dependencies from `ctx` (set in worker startup).
3. Register in `server/src/app/main_worker.py`: `BgWorkerSettings.functions` and, for schedules,
   `cron_jobs` with `arq.cron(...)` (uncomment `arq` in `server/requirements.txt` if still commented — ask first).
4. Test the use case with fake ports and the job with a fake `ctx`: duplicate input, empty input, normal input.
5. Verify: `make check`, `python .claude/hooks/check_arch.py --all`.
