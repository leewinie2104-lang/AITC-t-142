# 01 — Database Operations: migrations, backup, security, monitoring, scaling

Context: RDS PostgreSQL 16 (`db.t4g.small`, single-AZ at first, ADR-0005), three app processes (`api`, `worker`,
`agent-worker`) on one EC2 host via docker compose (ADR-0004), secrets in SSM (ADR-0009), observability via
OpenTelemetry → LGTM + CloudWatch (ADR-0008).

## 1. Migrations

**Tool**: Alembic with plain SQL (`op.execute("""…""")`), no autogenerate (ADR-0005, `new-migration` skill).
Roles: migrations log in as `parksmart_migrator` (member of `parksmart_owner`) and run `SET ROLE parksmart_owner`,
so every object is owned by the owner role and the app role never owns anything.

**Turning `../03-design/sql/schema.sql` into revisions** (follow the backlog order, one logical change per revision):

| Rev | Content | Backlog |
|-----|---------|---------|
| 0001 | schemas, extensions, roles + defaults, enums, helper functions | foundation |
| 0002 | facility + pools (`zone`, `building`, `slot_pool`, `slot` incl. `operational_status`, enum `app.size_class`) | M2 |
| 0003 | identity (`app_user` incl. `staff_zone_id`, `vehicle`) | M1 |
| 0004 | eligibility (`asset`, `eligibility`, `slot_holding`, `eligibility_level_at`) | M1 |
| 0005 | policy (`zone_policy` incl. `prices`, `agreement_template_md`, `ocr_review_threshold`) | M3 |
| 0006 | `agent_thread`, `approval_request`, `share_window`, `parking_request`, `booking` (incl. `checked_in_at` / `checked_out_at`) + triggers | M4, M5, M12, M14 |
| 0007 | `agreement`, `recovery_case`, `reject_mutation()`, `consent_record` | M6, W3 |
| 0008 | `payment` | M7 |
| 0009 | `ai_decision_log` (append-only trigger, INSERT/SELECT-only grant for the app role) | M14, ADR-0011 |
| 0010 | access (`lpr_event`, plain table) and `notification` | M8, M13 |
| 0011 | `knowledge_chunk` (needs pgvector), view `app.kpi_daily_v` | W7, M12 |
| each | RLS policies and grants **in the same revision** as the table | ADR-0005 |

Every revision has a working `downgrade()`. Run `upgrade head → downgrade -1 → upgrade head` locally and in CI
(the CI Postgres service must be `pgvector/pgvector:pg16`).

**Rules for changes on live, large tables** (`lpr_event`, `booking`, `notification`, `consent_record`, `ai_decision_log`):

| Change | Safe recipe |
|--------|-------------|
| Every migration | `SET lock_timeout = '5s'; SET statement_timeout = '15min';` and retry on timeout (the DDL lock queue blocks everyone behind it) |
| Add column | Nullable, no default, or a **constant** default (PG ≥ 11 metadata-only). No volatile defaults on big tables. |
| Add NOT NULL | 1) add nullable; 2) backfill in batches of 5–10 k rows (`UPDATE … WHERE id IN (SELECT … LIMIT n)`), commit per batch; 3) `ADD CONSTRAINT c CHECK (col IS NOT NULL) NOT VALID`; 4) `VALIDATE CONSTRAINT c` (SHARE UPDATE EXCLUSIVE, no write block); 5) `SET NOT NULL` (uses the validated check, no scan); 6) drop the check |
| Add FK / CHECK | `ADD CONSTRAINT … NOT VALID`, then `VALIDATE CONSTRAINT` in a separate transaction |
| Add index | `CREATE INDEX CONCURRENTLY` in a revision that sets `transaction_per_migration` / uses `op.get_context().autocommit_block()`; check `pg_index.indisvalid` afterwards, drop and retry if invalid |
| Partitioned table (deferred) | `lpr_event` is a plain table in the MVP. If it is partitioned later (see [08-deferred-tables](../03-design/08-deferred-tables.md)), FKs on a partitioned parent cannot be `NOT VALID` (verified on PG17, D-29) and indexes need `CREATE INDEX … ON ONLY` + per-partition `CONCURRENTLY` + `ATTACH PARTITION` |
| Unique constraint | Build the unique index `CONCURRENTLY`, then `ADD CONSTRAINT … UNIQUE USING INDEX` |
| Change a column type | Never in place on big tables: new column → dual write → backfill → switch reads → drop old (expand/contract) |
| Rename / drop column | Expand/contract across two releases: release N stops using it; release N+1 drops it |
| Enum value | `ALTER TYPE … ADD VALUE` in its own revision; never remove values |
| Exclusion constraint on existing data | Build the GiST index `CONCURRENTLY` first, then the constraint |

**Expand → migrate → contract**: release N adds the new structure and writes both; a backfill job migrates;
release N+1 reads the new structure; release N+2 removes the old. Each step is deployable and reversible alone.

**Worked examples, executed on PostgreSQL 17.10 (check e):**

```sql
-- every revision starts with
SET lock_timeout = '5s'; SET statement_timeout = '15min';

-- 1) booking (hot table): add column + index + FK without blocking writes
ALTER TABLE app.booking ADD COLUMN cancel_reason text;                         -- metadata only
CREATE INDEX CONCURRENTLY booking_cancel_reason_idx ON app.booking (cancel_reason)
  WHERE cancel_reason IS NOT NULL;                                             -- outside a transaction block
ALTER TABLE app.booking ADD COLUMN cancelled_by uuid;
ALTER TABLE app.booking ADD CONSTRAINT booking_cancelled_by_fk
  FOREIGN KEY (cancelled_by) REFERENCES app.app_user (id) ON DELETE RESTRICT NOT VALID;  -- brief lock, no scan
ALTER TABLE app.booking VALIDATE CONSTRAINT booking_cancelled_by_fk;           -- scans, writes continue
SELECT indisvalid FROM pg_index WHERE indexrelid = 'app.booking_cancel_reason_idx'::regclass;  -- must be true

-- 2) notification (large): NOT NULL in steps
ALTER TABLE app.notification ADD COLUMN channel text;
UPDATE app.notification SET channel = 'in_app' WHERE channel IS NULL;          -- in batches on real data
ALTER TABLE app.notification ADD CONSTRAINT notification_channel_nn CHECK (channel IS NOT NULL) NOT VALID;
ALTER TABLE app.notification VALIDATE CONSTRAINT notification_channel_nn;
ALTER TABLE app.notification ALTER COLUMN channel SET NOT NULL;                -- uses the validated check
ALTER TABLE app.notification DROP CONSTRAINT notification_channel_nn;
```

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
| Logical export | — | Weekly `pg_dump -Fc` of `app` to S3 (Object Lock) for long-term evidence (`consent_record`, `ai_decision_log`). With no hash chain in v4 this export is the only way to notice a removed evidence row |
| Ledger anchor | — | **Deferred** (the ledger and `ledger_head` are removed in v4, see [08-deferred-tables](../03-design/08-deferred-tables.md)); returns with the hash chain |
| **Restore test** | Once before the demo | **Monthly**: PITR to a scratch instance, run `../03-design/sql/seed-and-tests.sql`'s read-only checks + row counts vs prod (including `consent_record` and `ai_decision_log`, which must never shrink); record the measured RTO |

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
| `parksmart_readonly` | yes | `zone`, view `app.kpi_daily_v` (analysts) |

Separate login roles per process (`parksmart_api`, `parksmart_worker`, … `IN ROLE parksmart_app`) are
recommended so `pg_stat_activity` and connection limits are per process.

**Secrets**: DB passwords in SSM SecureString (ADR-0009), rotated every 90 days; prefer RDS IAM authentication
for `migrator`. Plate encryption uses app-side AES-256-GCM with KMS envelope keys and a separate HMAC (blind-index) key
(D-07, [ADR-0005 amendment](../03-design/09-adr-0005-amendment-proposal.md)); no key ever reaches the DB or the repo.

**Row-level security**: enabled on the zone- and household-owned tables (see schema.sql; only `zone` deliberately has none in v4 — the 22 other tables have RLS); context set with `SET LOCAL` per transaction (ADR-0005).
Integration tests must cover: BQL zone A vs zone B, resident vs other resident, chain operator aggregates only,
no-context = nothing (all present in 08 §8).

**PII handling**

| Data | Protection |
|------|-----------|
| Plates | Encrypted (`plate_ciphertext`, column-revoked), HMAC for matching, masked for display. **MVP shows masked plates only** (AC-12 holds because no original is shown); a reveal function + `plate_access_log` must exist before any screen shows an original plate (deferred) |
| Names, phones, emails | Stored clear (needed for login/contact); RLS limits visibility; pseudonymised before LLM calls in `agent/infrastructure` (BR-14) |
| Unit numbers (`asset.code`) | RLS to the owning zone only (BR-17) |
| Photos | S3 (SSE-KMS), original keys column-revoked, masked copies for tickets |
| Logs/traces | No parameter values in spans (ADR-0005); `log_min_duration_statement` logs statement text with `$n` placeholders only; never `log_statement = all` |

**Not in MVP: retention and data-subject requests.** `retention_rule`, `purge_expired`,
`drop_expired_lpr_partitions`, `privacy_request` and `erase_user` are removed from the MVP schema (D-31; 23 tables since D-32). The
targets stay as the requirement for the day real user data exists (PDPL 91/2025/QH15, Decree 356/2025/ND-CP):

| Target | Source | Where it returns |
|--------|--------|------------------|
| Retention periods per data class (LPR 90 days, sessions 180 days, logs 5 years incl. `ai_decision_log`, notifications 180 days, confirmation evidence and payments 10 years, never by job) | D-05, D-06 | [08-deferred-tables](../03-design/08-deferred-tables.md): `retention_rule`, `purge_expired`, LPR partitioning |
| Data-subject requests with legal deadlines (access/rectify 10 days, withdraw/restrict/object 15, delete 20; confirm against the official Decree 356 text) | D-14, D-15 | `privacy_request` |
| Erasure that keeps ids so the append-only `consent_record` evidence stays valid; refuses while bookings are live | D-14 | `erase_user` |

Until then: no personal data beyond synthetic demo accounts; `consent_record` and `ai_decision_log` are strictly append-only (no purge path);
only `notification` (and `knowledge_chunk`) can be trimmed by a plain DELETE job when volume needs it (the app role has DELETE on those two; see
schema.sql grants). There are no token or OTP tables to trim in v4: OTP keys expire in Redis. See risks R-21 and R-29 in [06](../03-design/06-risks-edge-cases.md).

**AI decision log and consent evidence (v4, D-32).** `ai_decision_log` and `consent_record` are append-only: the statement trigger
`reject_mutation()` rejects UPDATE/DELETE/TRUNCATE (also for the owner) and the app role has INSERT + SELECT only. Operating rules:

| Topic | Rule |
|-------|------|
| Content | Hashes and ids only (`user_hash` HMAC, `input_hash`/`output_hash` SHA-256, `trace_id`); never write a prompt, an output, a name or a plate into these tables. Debugging detail goes to OTel with PII filtering (ADR-0008) |
| Retention | **Not enforced; the target must be decided before real data.** Proposal: 5 years for `ai_decision_log` (D-06 logs), 10 years for `consent_record`. A purge needs a privileged one-off job that drops the trigger inside a reviewed migration; there is no purge function. `user_hash` is personal data under PDPL, so a data-subject erasure rule is needed too (D-14) |
| Growth | About one row per AI step: watch the table size and `idempotency_key` index size monthly; partition by `created_at` only past ~50 M rows (see §5) |
| Integrity | No hash chain in v4: protection = trigger + grants + backups. Keep the weekly logical export (§2); never grant UPDATE/DELETE to any application role |
| Access | BQL reads rows of its own zone (RLS `zone_manager_read`); users cannot read `ai_decision_log`; `system` writes. `parksmart_readonly` has no grant on either table |

**Agent schema (`agent`, LangGraph checkpointer) — D-12**. RLS cannot inspect serialized state, so:
(1) isolation — `parksmart_app` has no access to `agent`, `parksmart_checkpointer` none to `app` (tested in 08, agent-schema section);
(2) content rule — state may hold ids, pseudonyms (`NT-7`), pseudonymised text and enum values only; never names,
phones, plates, raw user messages or the pseudonym map in clear. Keep the pseudonym map in Redis with a TTL, or
use the library's encrypted serializer if the pinned version provides one (**not verified**); add a unit test
that serialises a finished state and asserts no plate/phone pattern appears;
(3) retention — purging finished threads after 30 days (`app.purge_agent_checkpoints`) is **deferred**; until it exists,
finished threads accumulate. The default privileges that let `parksmart_owner` SELECT/DELETE checkpointer tables stay
so the job can be added without a grant change.

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

**Autovacuum tuning** for high-churn tables (`booking` statuses, `agent_thread`, `recovery_case`,
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
| Outbox lag | **Deferred** with `outbox` (ADR-0011); metric `outbox_lag_seconds` returns with it | app metric |
| Ledger integrity | **Deferred** with the hash chain (ADR-0011); in v4 compare `consent_record` / `ai_decision_log` row counts after each restore | runbook |
| AI decision log | no `ai_decision_log` row for a day with agent traffic; share of `outcome = 'failed'` or `'degraded'` > 10 % in 15 min | SQL check on `ai_decision_log` (nightly) or a Grafana panel |
| Backup | latest automated backup older than 26 h; restore test overdue | AWS Backup / runbook |
| Failed logins spike | `auth_login_attempts_total{result="invalid"}` × 5 baseline | app metric (ADR-0006). No `auth_token_refresh_total` / `auth_refresh_reuse_detected_total` in the demo (no refresh token) |

## 5. Scaling (only when the numbers demand it)

| Lever | Trigger to act | Action |
|-------|----------------|--------|
| Bigger instance | CPU > 60 % sustained at peak, or working set > RAM (buffer cache hit < 99 %) | `db.t4g.small` → `db.m7g.large` (no burst credits) |
| Index/query fixes | Before any architectural change | `pg_stat_statements` top 10 by total time |
| PgBouncer / RDS Proxy | > 2 app hosts or > 150 connections | Transaction pooling |
| Read replica | Reporting/dashboards > 10 % of primary CPU | Route `reporting` reads to the replica; RLS still applies |
| Materialised views | `app.kpi_daily_v` or another dashboard query > 500 ms | Replace the view with an MV refreshed by N7 `CONCURRENTLY` (needs a unique index) |
| Partitioning | `lpr_event` before real LPR feeds; `notification` or `ai_decision_log` > 50 M rows | Monthly range partitions + drop instead of delete (partition recipes and retention are deferred, see [08-deferred-tables](../03-design/08-deferred-tables.md)) |
| Cache | Same reference data (`slot_pool`, `zone_policy` incl. prices) read > 1 k/s | In-process cache keyed by policy version (immutable rows → trivial invalidation) |
| ANN index for RAG | > 50 k chunks or retrieval p95 > 100 ms | `CREATE INDEX … USING hnsw (embedding vector_cosine_ops)` |
| Sharding by zone | Only if a single primary cannot hold write load after all of the above (> ~5 k write tx/s); not expected at AS-01 scale | Zone is the natural shard key: every table already carries `zone_id` and transactions are single-zone |
