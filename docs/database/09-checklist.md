# 09 — Pre-production checklist

Status legend (v2, 2026-11-18):
**Done · PG17** = implemented and verified by `08-seed-and-tests.sql` on PostgreSQL 17.10 ·
**Verified on PG16** = also executed on the target version (none yet, see 00 §6) ·
**Designed** = written, not executable here · **Open** = work or decision still needed.

## Schema and integrity

| # | Item | Status | Evidence / next step |
|---|------|--------|----------------------|
| 1 | Every table has a primary key | Done · PG17 | 57/57 tables (03-data-dictionary) |
| 2 | Every FK states ON DELETE; no accidental cascades of business history | Done · PG17 | 01 §4; tests "ON DELETE RESTRICT"; SET NULL columns checked (D-27) |
| 3 | Zone consistency enforced by composite FKs | Done · PG17 | Tests "booking a zone-A slot under zone C", "BR-10 swap leg" |
| 4 | No double booking / overlapping windows / overlapping holders; released rows do not block | Done · PG17 | EXCLUDE constraints; rebook-after-cancel/expiry/relocation/void tests (D-26); 8-session race → 1 winner |
| 5 | Hard business invariants in the DB (BR-01/02/03/04/10/11/12/16, AC-07/15/16/23, D-10) | Done · PG17 | 51 + 30 tests pass with expected SQLSTATE and message |
| 6 | Ledger append-only, hash-chained, tamper detection | Done · PG17 | Tamper test; 160 concurrent appends verified (v2 re-run) |
| 7 | Idempotency key on every workflow/job write target | Done · PG17 | D-28 added `share_window`, `voucher`, evidence keys; tests §9.5 |
| 8 | Money as integer VND, non-negative; refunds explicit | Done · PG17 | `payment.direction`; early-return settlement test (D-09) |
| 9 | All times `timestamptz`; ranges half-open | Done · PG17 | Data dictionary |
| 10 | TBD values are configuration with researched defaults | Done · PG17 | `zone_policy` DEFAULTs "default, confirm with BQL"; test §9.1 |
| 11 | DDL runs on PostgreSQL 16 | **Open** | Blocked locally (WSL2 hardware crash, binary download not permitted). Run in CI on `pgvector/pgvector:pg16` |
| 12 | pgvector column for W7 | **Open** | Not executed anywhere yet |
| 13 | Business values confirmed by BQL / product owner | **Open** | Review [10-decision-log](10-decision-log.md) §1 (D-01…D-04, D-08, D-16, D-21) |

## Security and privacy

| # | Item | Status | Evidence / next step |
|---|------|--------|----------------------|
| 14 | RLS on every zone- or household-owned table | Done · PG17 | 48 tables incl. `privacy_request`, `occupancy_hourly`; 33 RLS/privilege tests |
| 15 | App role: not owner, no DDL/TRUNCATE/BYPASSRLS | Done · PG17 | Tests in §8 |
| 16 | Missing RLS context exposes nothing | Done · PG17 | Test "no context" |
| 17 | Cross-zone exchange limited to level + expiry (BR-17) | Done · PG17 | BQL C tests |
| 18 | Plate ciphertext readable only via logged functions (AC-12) | Done · PG17 | Column grants; reveal + log tests |
| 19 | Passwords only as argon2id hashes | Done · PG17 | CHECK |
| 20 | Plate key management decided | Designed | D-07; [ADR-0005 amendment](adr-proposals/ADR-0005-amendment.md) awaiting team acceptance |
| 21 | Retention per data class + purge | Done · PG17 | `retention_rule`, `purge_expired`, `drop_expired_lpr_partitions` tests (D-05, D-06) |
| 22 | Erasure and data-subject requests (PDPL 91/2025, Decree 356/2025) | Done · PG17 | `erase_user`, `privacy_request` tests (D-14, D-15); legal review of deadlines **Open** |
| 23 | Agent schema isolated, PII rule, cleanup | Done · PG17 (mock table) | Isolation + purge tests; real `langgraph-checkpoint-postgres` tables and encrypted serializer **Open** (D-12) |
| 24 | TLS enforced, DB in private subnets | **Open** | Terraform `rds` module |
| 25 | Per-process login roles, secrets in SSM, rotation | **Open** | 07 §3 |
| 26 | DPIA + cross-border transfer dossier (Bedrock) | **Open** | D-23, legal workstream before real data |

## Operations

| # | Item | Status | Evidence / next step |
|---|------|--------|----------------------|
| 27 | Alembic plain-SQL revisions with downgrade | **Open** | Split 02 per 07 §1 |
| 28 | Online migration recipes | Done · PG17 | `booking`, `notification`, `lpr_event` executed; partitioned FK limitation documented (D-29) |
| 29 | Role-level statement/lock/idle timeouts | Done · PG17 | `ALTER ROLE parksmart_app SET …` |
| 30 | Partition create/drop jobs scheduled | Designed | Functions tested; schedule daily owner job |
| 31 | Backups, PITR, Multi-AZ | Designed | Demo: RDS automated backups; Multi-AZ before real data |
| 32 | Restore drill with measured RTO | **Open** | 07 §2 |
| 33 | `pg_stat_statements`, slow log, Performance Insights | **Open** | RDS parameter group |
| 34 | Alerts from 07 §4 | **Open** | CloudWatch + Grafana |
| 35 | Main queries have indexes; plans checked at realistic volume | **Open** | v1 plans only (LPR, inbox measured); large-volume EXPLAIN skipped in v2 |
| 36 | Integration tests in CI with real Postgres | **Open** | Port `08-seed-and-tests.sql` into `server/tests/integration/` |
| 37 | Concurrency tests | Done · PG17 | Booking race, ledger appends, cancel vs booking (v2 re-run) |
| 38 | Load test of booking/matching path | **Open** | After W1/W2 exist |
