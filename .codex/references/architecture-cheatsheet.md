# Architecture cheatsheet (for AI agents)

Condensed from `docs/07-adr/` and `docs/04-development/01-server-structure.md`. When this file and an ADR
disagree, the ADR wins; when an ADR and code disagree, code wins — flag it.

## ADRs at a glance

| ADR | Decision |
|-----|----------|
| 0001 | Monorepo: `server/`, `client/`, `infra/`, `eval/`, `docs/` |
| 0002 | Client: React + TS + Vite SPA, Tailwind, shadcn/ui, TanStack Query, on S3 + CloudFront |
| 0003 | API: REST `/api/v1` + OpenAPI, SSE (chat stream), WebSocket (realtime), single domain |
| 0004 | Backend: FastAPI + LangGraph + arq workers (`bg`, `agent` queues) on EC2 with Docker Compose |
| 0005 | Data: RDS Postgres (+pgvector), asyncpg, hand-written SQL, RLS per zone, Alembic with plain SQL |
| 0006 | Auth: self-issued JWT (ES256) |
| 0007 | LLM: Claude on Amazon Bedrock via `ChatBedrockConverse`; router classify / generate / judge; pseudonymize in `LLMPort` |
| 0008 | Observability: OpenTelemetry → LGTM on a dedicated EC2 |
| 0009 | Infra: Terraform, GitHub Actions → ECR → SSM deploy |
| 0010 | Modules (Clean Architecture), `agent/` orchestrates W0–W7, jobs N1–N9 are delivery adapters |

## Request paths

```
Client ─REST─▶ <module>/delivery/rest/router ─▶ usecase.execute ─▶ domain ports ─▶ infrastructure/postgres
Client ─SSE──▶ agent/delivery/rest (chat) ─▶ agent/usecase/chat_turn ─▶ W0 graph ─▶ W1–W7
                                                   │ LLM via platform/llm (pseudonymized)
                                                   └ other modules' use cases via ports
arq bg queue ─▶ <module>/delivery/jobs/nX ─▶ usecase ─▶ publish port ─▶ agent workflow
HITL: graph interrupt() ─▶ approval queue (zone of slot) ─▶ BQL REST approve ─▶ agent.resume_workflow job
```

## Workflows (agent/)

| W | Purpose | Modules | HITL |
|---|---------|---------|------|
| W0 | Supervisor: guardrail → pseudonymize → classify intent → route → restore → stream | M14 | |
| W1 | Request slot / routing by eligibility level | M5, M3, M1, M2 | |
| W2 | Share slot (schedule, match, agreement, OTP, confirmation evidence, payment) | M4, M6, M7 | yes (over threshold) |
| W3 | Owner returns early → TH3 replacement | M9, M4, M5 | yes |
| W4 | Overstay | M9, M7, M13 | |
| W5 | Dispute | M10, M8, M6 | yes |
| W6 | Swap within a zone | M11, M2 | yes |
| W7 | Rules Q&A (RAG with citations) | M3, M14 | |

## Background jobs

N1 LPR log processing (access) · N2 overstay check (access) · N3 daily reconciliation (reporting) ·
N4 free-slot forecast (sharing) · N5 repeated-dispute detection (dispute) · N6 eligibility expiry scan
(eligibility) · N7 chain KPI (reporting) · N8 inter-zone supply/demand balancing (reporting) · N9 expiry sweeper: holds, agreements,
approvals, share windows, recovery deadlines (booking).

## Priority tiers

Backlog items are tagged **Ưu tiên 1** (weeks 1–2, must), **Ưu tiên 2** (week 3, before the demo) and **Ưu tiên 3**
(only if time allows; list in `docs/01-product/05-backlog.md` §6). Implement Ưu tiên 1 first; never start Ưu tiên 3
unless the plan says so.
