# 07 — Operations: migrations, backup, security, monitoring, scaling

Context: RDS PostgreSQL 16 (`db.t4g.small`, single-AZ at first, ADR-0005), three app processes (`api`, `worker`,
`agent-worker`) on one EC2 host via docker compose (ADR-0004), secrets in SSM (ADR-0009), observability via
OpenTelemetry → LGTM + CloudWatch (ADR-0008).

## 1. Migrations

**Tool**: Alembic with plain SQL (`op.execute("""…""")`), no autogenerate (ADR-0005, `new-migration` skill).
Roles: migrations log in as `parksmart_migrator` (member of `parksmart_owner`) and run `SET ROLE parksmart_owner`,
so every object is owned by the owner role and the app role never owns anything.

**Turning `02-schema.sql` into revisions** (follow the backlog order, one logical change per revision):

| Rev | Content | Backlog |
|-----|---------|---------|
| 0001 | schemas, extensions, roles + defaults, enums, helper functions | foundation |
| 0002 | facility + pools (`chain` … `gate`), `size_class` | M2 |
| 0003 | identity (`app_user`, `staff_zone`, `consent`, tokens, `vehicle`) | M1 |
| 0004 | eligibility (`asset`, `eligibility`, `slot_holding`, `eligibility_level_at`) | M1 |
| 0005 | policy (`zone_policy`, `price_rule`, `agreement_template`, `holiday`) | M3 |
| 0006 | `approval_request`, `share_window`, `parking_request`, `booking` + triggers | M4, M5, M12 |
| 0007 | `agreement`, `otp_challenge`, ledger + functions | M6 |
| 0008 | `voucher`, `payment` | M7 |
| 0009 | platform (`outbox`, `idempotency_keys`, `workflow_run`, `audit_log` + triggers) | ADR-0010 |
| 0010 | access (`lpr_source`, `lpr_event` partitions, `parking_session`, `overstay_case`, plate log, reveal functions) | M8, M9 |
| 0011+ | disputes, swaps, notifications, reporting, knowledge | M10–M13, W7 |
| each | RLS policies and grants **in the same revision** as the table | ADR-0005 |

Every revision has a working `downgrade()`. Run `upgrade head → downgrade -1 → upgrade head` locally and in CI
(the CI Postgres service must be `pgvector/pgvector:pg16`).

**Rules for changes on live, large tables** (`lpr_event`, `booking`, `notification`, `ledger_entry`, `audit_log`):

| Change | Safe recipe |
|--------|-------------|
| Every migration | `SET lock_timeout = '5s'; SET statement_timeout = '15min';` and retry on timeout (the DDL lock queue blocks everyone behind it) |
| Add column | Nullable, no default, or a **constant** default (PG ≥ 11 metadata-only). No volatile defaults on big tables. |
| Add NOT NULL | 1) add nullable; 2) backfill in batches of 5–10 k rows (`UPDATE … WHERE id IN (SELECT … LIMIT n)`), commit per batch; 3) `ADD CONSTRAINT c CHECK (col IS NOT NULL) NOT VALID`; 4) `VALIDATE CONSTRAINT c` (SHARE UPDATE EXCLUSIVE, no write block); 5) `SET NOT NULL` (uses the validated check, no scan); 6) drop the check |
| Add FK / CHECK | `ADD CONSTRAINT … NOT VALID`, then `VALIDATE CONSTRAINT` in a separate transaction |
| Add index | `CREATE INDEX CONCURRENTLY` in a revision that sets `transaction_per_migration` / uses `op.get_context().autocommit_block()`; check `pg_index.indisvalid` afterwards, drop and retry if invalid |
| Index on a partitioned table | `CREATE INDEX … ON ONLY app.lpr_event`, then `CREATE INDEX CONCURRENTLY` per partition, then `ALTER INDEX … ATTACH PARTITION` |
| Unique constraint | Build the unique index `CONCURRENTLY`, then `ADD CONSTRAINT … UNIQUE USING INDEX` |
| Change a column type | Never in place on big tables: new column → dual write → backfill → switch reads → drop old (expand/contract) |
| Rename / drop column | Expand/contract across two releases: release N stops using it; release N+1 drops it |
| Enum value | `ALTER TYPE … ADD VALUE` in its own revision; never remove values |
| Exclusion constraint on existing data | Build the GiST index `CONCURRENTLY` first, then the constraint |

**Expand → migrate → contract**: release N adds the new structure and writes both; a backfill job migrates;
release N+1 reads the new structure; release N+2 removes the old. Each step is deployable and reversible alone.

**Rollback plan**: (1) application rollback first: every migration is backward-compatible with the previous app
release (expand/contract guarantees it); (2) `alembic downgrade` only for revisions that did not destroy data;
(3) destructive "contract" revisions run only after a verified backup and are rolled back by PITR restore to a
new instance, not by downgrade.

## 2. Backup and restore

| Item | Demo (ADR-0005) | Before real data |
|------|-----------------|------------------|
| Automated backups + WAL (PITR) | RDS automated backups, retention 7 days | 14–35 days |
| **RPO** | ≤ 5 min (RDS ships WAL to S3 every 5 min) | ≤ 5 min |
| **RTO** | ~1 h (restore to a new instance + DNS/SSM switch) | ≤ 30 min with Multi-AZ failover (1–2 min) for instance failure; ≤ 1 h for PITR |
| Multi-AZ | No | **Yes** |
| Manual snapshot | Before each migration with a "contract" step | Same + monthly kept 12 months |
| Cross-region copy | No | Daily snapshot copy to a second region (ransomware / region loss) |
| Logical export | — | Weekly `pg_dump -Fc` of `app` to S3 (Object Lock) for long-term ledger evidence |
| Ledger anchor | — | Daily export of every zone's `ledger_head.last_hash` to S3 with Object Lock (detects a full-chain rewrite) |
| **Restore test** | Once before the demo | **Monthly**: PITR to a scratch instance, run `08-seed-and-tests.sql`'s read-only checks + `ledger_verify` per zone + row counts vs prod; record the measured RTO |

The LangGraph checkpointer (schema `agent`) is in the same database and is restored with it, so paused HITL
workflows survive a restore up to the RPO.

## 3. Security

**Network and transport**
* RDS in private subnets, no public accessibility; security group allows 5432 only from the app EC2 SG.
* TLS required: `rds.force_ssl = 1`; clients use `sslmode=verify-full` with the RDS CA bundle.

**Roles (least privilege)**

| Role | Login | Rights |
|------|-------|--------|
| RDS master | break-glass only | stored in SSM, MFA-guarded IAM access |
| `parksmart_owner` | no | owns all objects |
| `parksmart_migrator` | yes (CI/CD) | member of owner; used only by migrations |
| `parksmart_app` | yes (api/worker/agent-worker) | DML on `app` per 02 §21; **no DDL, no TRUNCATE, no BYPASSRLS**; ciphertext columns not selectable |
| `parksmart_checkpointer` | yes | schema `agent` only |
| `parksmart_readonly` | yes | `kpi_daily` + reference tables (analysts) |

Separate login roles per process (`parksmart_api`, `parksmart_worker`, … `IN ROLE parksmart_app`) are
recommended so `pg_stat_activity` and connection limits are per process.

**Secrets**: DB passwords in SSM SecureString (ADR-0009), rotated every 90 days; prefer RDS IAM authentication
for `migrator`. Plate encryption key and HMAC pepper live in KMS/SSM, never in the DB or the repo.

**Row-level security**: enabled on 46 tables (02 §20); context set with `SET LOCAL` per transaction (ADR-0005).
Integration tests must cover: BQL zone A vs zone B, resident vs other resident, chain operator aggregates only,
no-context = nothing (all present in 08 §8).

**PII handling**

| Data | Protection |
|------|-----------|
| Plates | Encrypted (`plate_ciphertext`, column-revoked), HMAC for matching, masked for display; reveal only through functions that log to `plate_access_log` (AC-12) |
| Names, phones, emails | Stored clear (needed for login/contact); RLS limits visibility; pseudonymised before LLM calls in `agent/infrastructure` (BR-14) |
| Unit numbers (`asset.code`) | RLS to the owning zone only (BR-17) |
| Photos | S3 (SSE-KMS), original keys column-revoked, masked copies for tickets |
| Logs/traces | No parameter values in spans (ADR-0005); `log_min_duration_statement` logs statement text with `$n` placeholders only; never `log_statement = all` |

**Retention (proposal, confirm with Q6)**: `lpr_event` 13 months (drop partitions), photos 12 months after ticket
close, `plate_access_log` and `audit_log` 3 years, `outbox` published rows 7 days, `idempotency_keys` 30 days,
`notification` 180 days, `refresh_token`/`otp_challenge` 30 days after expiry, LangGraph checkpoints of finished
threads 30 days. **Erasure**: soft-delete the user, scrub `full_name`/`phone_e164`/`email`, deactivate vehicles
and drop their ciphertext; ledger payloads hold ids only, so the ledger needs no rewrite.

**SQL injection / IDOR**: asyncpg `$n` parameters only (ADR-0005); dynamic SQL exists only in owner-run
maintenance functions using `format('%I', …)`. IDOR is blocked twice: RLS on every user/zone table and
non-sequential UUIDv7 ids; `SECURITY DEFINER` functions re-check the caller.

## 4. Monitoring and alerts

**Enable**: `shared_preload_libraries = 'pg_stat_statements'`, `pg_stat_statements.track = top`,
`track_io_timing = on`, `log_min_duration_statement = 500ms`, `log_lock_waits = on`, `deadlock_timeout = 1s`,
`log_autovacuum_min_duration = 10s`, `log_temp_files = 0`, Performance Insights on RDS.

**Connection pooling**: three processes × two drivers. Budget for `db.t4g.small` (max_connections ≈ 180):
api asyncpg 20 + checkpointer 5; worker 10; agent-worker 10 + checkpointer 5 → ~50, leaving room for
migrations and admin. Add **PgBouncer in transaction mode** (or RDS Proxy) once a second app host exists; RLS
context uses `SET LOCAL`, which is transaction-scoped and compatible; never use session-level `SET` or advisory
*session* locks (use `pg_try_advisory_xact_lock`).

**Autovacuum tuning** for high-churn tables (`booking` statuses, `outbox`, `idempotency_keys`, `otp_challenge`,
`notification`): `autovacuum_vacuum_scale_factor = 0.02`, `autovacuum_analyze_scale_factor = 0.01` per table.

**Alerts**

| Alert | Threshold | Source |
|-------|-----------|--------|
| CPU | > 80 % for 10 min | CloudWatch |
| Free storage | < 20 % (warn), < 10 % (page) | CloudWatch |
| Connections | > 80 % of `max_connections`; pool wait `db_client_connection_wait_seconds` p95 > 100 ms | CloudWatch, app metrics (ADR-0005) |
| Replication lag (when a replica exists) | > 30 s | CloudWatch `ReplicaLag` |
| Long transactions | any xact > 60 s; `idle in transaction` > 30 s | `pg_stat_activity` |
| Lock waits / deadlocks | deadlocks > 0 in 5 min; lock wait > 5 s | logs, `pg_stat_database.deadlocks` |
| Slow queries | new top-10 query by total time, or mean > 200 ms | `pg_stat_statements` |
| Dead tuples / bloat | `n_dead_tup / n_live_tup > 0.2` on a table > 1 M rows; last autovacuum > 24 h on hot tables | `pg_stat_user_tables` |
| Transaction ID wraparound | `age(datfrozenxid)` > 1 billion | `pg_database` |
| Outbox lag | oldest unpublished > 60 s (`outbox_lag_seconds`, ADR-0010) | app metric |
| LPR default partition | any row in `app.lpr_event_default` | daily check |
| Missing future partition | next month's partition absent 7 days before month end | daily check |
| Ledger integrity | `ledger_verify(zone)` not NULL | nightly job per zone |
| Backup | latest automated backup older than 26 h; restore test overdue | AWS Backup / runbook |
| Failed logins spike | `auth_login_attempts_total{result="invalid"}` × 5 baseline | app metric (ADR-0006) |

## 5. Scaling (only when the numbers demand it)

| Lever | Trigger to act | Action |
|-------|----------------|--------|
| Bigger instance | CPU > 60 % sustained at peak, or working set > RAM (buffer cache hit < 99 %) | `db.t4g.small` → `db.m7g.large` (no burst credits) |
| Index/query fixes | Before any architectural change | `pg_stat_statements` top 10 by total time |
| PgBouncer / RDS Proxy | > 2 app hosts or > 150 connections | Transaction pooling |
| Read replica | Reporting/dashboards > 10 % of primary CPU, or N3/N4 jobs slow OLTP | Route `reporting` reads and N4 history scans to the replica; RLS still applies |
| Materialised views | A dashboard query > 500 ms on the replica | MV refreshed by N3/N7 `CONCURRENTLY` (needs a unique index) |
| More partitioning | `notification` or `audit_log` > 50 M rows, or their purge `DELETE` takes > 10 min | Monthly range partitions + drop instead of delete |
| Cache | Same reference data (`slot_pool`, `zone_policy`, `price_rule`) read > 1 k/s | In-process cache keyed by policy version (immutable rows → trivial invalidation) |
| ANN index for RAG | > 50 k chunks or retrieval p95 > 100 ms | `CREATE INDEX … USING hnsw (embedding vector_cosine_ops)` |
| Sharding by zone | Only if a single primary cannot hold write load after all of the above (> ~5 k write tx/s); not expected at AS-01 scale | Zone is the natural shard key: every table already carries `zone_id` and transactions are single-zone |
