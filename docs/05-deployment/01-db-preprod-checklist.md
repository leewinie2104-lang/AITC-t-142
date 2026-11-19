# 01 — Database: Pre-production checklist

Status legend (v5 MVP, 25 tables, 2026-11-19):
**Done · PG17** = implemented and verified by `../03-design/sql/seed-and-tests.sql` on PostgreSQL 17 (257 assertions: 159 PASS + 98 OK, 0 FAIL) ·
**Verified on PG16** = also executed on the target version (none yet, see 00 §6) ·
**Designed** = written, not executable here · **Open** = work or decision still needed ·
**Deferred** = belongs to a removed table or function, see [08-deferred-tables](../03-design/08-deferred-tables.md); was verified on
v2 only (git `333b85b`) and must be re-verified when the object returns.

## Schema and integrity

| # | Item | Status | Evidence / next step |
|---|------|--------|----------------------|
| 1 | Every table has a primary key | Done · PG17 | 25/25 tables (03-data-dictionary) |
| 2 | Every FK states ON DELETE; no accidental cascades of business history | Done · PG17 | 01 §4; tests "ON DELETE RESTRICT"; SET NULL columns checked (D-27) |
| 3 | Zone consistency enforced by composite FKs | Done · PG17 | Test "booking a zone-A slot under zone C"; the "BR-10 swap leg" test is **deferred** with `swap_leg` |
| 4 | No double booking / overlapping windows / overlapping holders; released rows do not block | Done · PG17 | EXCLUDE constraints; rebook-after-cancel/expiry/relocation/void tests (D-26); 8-session race → 1 winner (v2 run) |
| 5 | Hard business invariants in the DB (BR-01/02/03/04/11/12/16, AC-07/15; BR-10 swap deferred) | Done · PG17 | BR-11 now by the ordered enum `app.size_class`; tests pass with expected SQLSTATE and message. AC-16 voucher and D-10 swap consent invariants are **deferred** |
| 6 | Confirmation evidence append-only (`consent_record`), AI decision log append-only (`ai_decision_log`) and dispute evidence append-only (`dispute_evidence`, v5) | Done · PG17 | UPDATE/DELETE/TRUNCATE rejected by trigger and grants (tests in the v4 and v5 sections). Hash chain, `ledger_verify` and tamper detection are **deferred** with the ledger (D-32); see 06 R-28 |
| 7 | Idempotency key on every workflow/job write target | Done · PG17 | 05 §0.1 (25-table inventory: columns only, no `idempotency_keys` table; `dispute_case` key, `dispute_evidence` unique items, `overstay_pre:`/`overstay_due:` notification keys); tests; evidence/voucher keys **deferred** |
| 7a | Overstay fee only after exit; one paid fee per booking (v5) | Done · PG17 | Trigger `payment_overstay_guard` (fee before `checked_out_at` refused), `payment_paid_uq`; tests "second paid overstay fee", "duplicate reminder key"; waiver via dispute (`fee_waived`) test |
| 7b | Dispute integrity (v5): zone-scoped FKs, one open report per reporter/booking(or slot)/category, evidence kind CHECKs | Done · PG17 | Tests "cross-zone FK", "duplicate open report", "evidence kind mismatch"; decision-flow test; `dispute_case` resolution CHECKs |
| 8 | Money as integer VND, non-negative; refunds explicit | Done · PG17 | `payment.direction`, `amount_vnd >= 0`; early-return settlement test (D-09) |
| 9 | All times `timestamptz`; ranges half-open | Done · PG17 | Data dictionary |
| 10 | TBD values are configuration with researched defaults | Done · PG17 | `zone_policy` DEFAULTs and `prices` "default, confirm with BQL" |
| 11 | DDL runs on PostgreSQL 16 | **Open** | Blocked locally (WSL2 hardware crash, binary download not permitted). Run in CI on `pgvector/pgvector:pg16` |
| 12 | pgvector column for W7 | **Open** | Not executed anywhere yet (`knowledge_chunk` now also carries the doc columns) |
| 13 | Business values confirmed by BQL / product owner | **Open** | Review [07-db-decision-log](../03-design/07-db-decision-log.md) §1 (D-01…D-04, D-08, D-16, D-21; D-03 overstay values and D-33) |
| 13a | `zone_policy.prices` shape validated | **Open** | DB checks only `jsonb_typeof = 'object'`; Pydantic validation in the rule engine to be built (06 R-23) |
| 13b | `lpr_event` dedupe `UNIQUE (zone_id, source_code, source_event_id)` | Done · PG17 | Test "LPR duplicate" |
| 13c | `kpi_daily_v` row filter (BQL own zone, chain operator all, resident none); v5 columns `overstay_fees`, `disputes_opened`, `dispute_prep_minutes_avg` | Done · PG17 | View tests |

## Security and privacy

| # | Item | Status | Evidence / next step |
|---|------|--------|----------------------|
| 14 | RLS on every zone- or household-owned table | Done · PG17 | Policies of the 25-table schema (new in v4: `agent_thread`, `recovery_case`, `consent_record`, `ai_decision_log`; new in v5: `dispute_case`, `dispute_evidence` with zone staff / system / parties-read / reporter-insert policies; a reporter cannot set the respondent, AI or resolution fields); RLS/privilege tests. Policies of `privacy_request`, `occupancy_hourly` etc. are **deferred** |
| 15 | App role: not owner, no DDL/TRUNCATE/BYPASSRLS | Done · PG17 | Tests in §8 |
| 16 | Missing RLS context exposes nothing | Done · PG17 | Test "no context" |
| 17 | Cross-zone exchange limited to level + expiry (BR-17) | Done · PG17 | BQL C tests |
| 18 | Plate ciphertext never readable by the app role (AC-12) | Done · PG17 | Column grants; **masked plates only** in the MVP. Logged reveal (`reveal_*`, `plate_access_log`) is **deferred** and required before any screen shows an original plate |
| 18a | Original dispute photo key never readable by the app role; vision model gets masked photos only (BR-14) | Done · PG17 | Column grant on `dispute_evidence` (no `object_key_original`); test "original key not selectable". Blur pipeline and S3 are **Open** (06 R-31) |
| 19 | Passwords only as argon2id hashes | Done · PG17 | CHECK |
| 20 | Plate key management decided | Designed | D-07; [ADR-0005 amendment](../03-design/09-adr-0005-amendment-proposal.md) awaiting team acceptance |
| 21 | Retention per data class + purge | **Deferred** | `retention_rule`, `purge_expired`, LPR partition drop removed (D-31); targets in 02-database-security §3; required before real user data |
| 22 | Erasure and data-subject requests (PDPL 91/2025, Decree 356/2025) | **Deferred** | `erase_user`, `privacy_request` removed (D-31); consent history is `consent_record` (append-only, no erasure path yet); required before real user data; legal review of deadlines **Open** |
| 23 | Agent schema isolated, PII rule, cleanup | Done · PG17 (mock table) | Isolation tests; checkpoint purge (`purge_agent_checkpoints`) **deferred**; real `langgraph-checkpoint-postgres` tables and encrypted serializer **Open** (D-12) |
| 23a | Demo access token (8 h, no refresh token, no revocation) replaced before real users | **Deferred** | `refresh_token` removed (D-32); bring it back with a short access token, see 08-deferred-tables group (d) and 06 R-26 |
| 23b | Retention target and purge path for `ai_decision_log` (and `consent_record`) decided | **Open** | 02-database-security §3 (AI decision log); 06 R-29; before any real data |
| 23c | Outbox for realtime / job-triggered workflows | **Deferred** | `outbox` removed (D-32); `platform.publish()` port keeps the way open; 06 R-27 |
| 24 | TLS enforced, DB in private subnets | **Open** | Terraform `rds` module |
| 25 | Per-process login roles, secrets in SSM, rotation | **Open** | 02-database-security §3 |
| 26 | DPIA + cross-border transfer dossier (Bedrock) | **Open** | D-23, legal workstream before real data |

## Operations

| # | Item | Status | Evidence / next step |
|---|------|--------|----------------------|
| 27 | Alembic plain-SQL revisions with downgrade | **Open** | Split 02 per 01-database-operations §1 |
| 28 | Online migration recipes | Done · PG17 | `booking`, `notification` executed; partitioned-table recipes **deferred** with LPR partitioning (D-29) |
| 29 | Role-level statement/lock/idle timeouts | Done · PG17 | `ALTER ROLE parksmart_app SET …` |
| 30 | Partition create/drop jobs scheduled | **Deferred** | `lpr_event` is a plain table in the MVP; revisit before real LPR feeds |
| 31 | Backups, PITR, Multi-AZ | Designed | Demo: RDS automated backups; Multi-AZ before real data |
| 32 | Restore drill with measured RTO | **Open** | 01-database-operations §2 |
| 33 | `pg_stat_statements`, slow log, Performance Insights | **Open** | RDS parameter group |
| 34 | Alerts from 03-database-monitoring-scaling §4 | **Open** | CloudWatch + Grafana |
| 35 | Main queries have indexes; plans checked at realistic volume | **Open** | Plans forced on tiny tables only; large-volume EXPLAIN not run (04) |
| 36 | Integration tests in CI with real Postgres | **Open** | Port `../03-design/sql/seed-and-tests.sql` into `server/tests/integration/` |
| 37 | Concurrency tests | Done · PG17 | Booking race and cancel vs booking (v2 run; the EXCLUDE code is unchanged). Ledger appends no longer apply (deferred). One-open-case rule of `recovery_case` is a single-session negative test; a two-session race is **Open** |
| 38 | Load test of booking/matching path | **Open** | After W1/W2 exist |
