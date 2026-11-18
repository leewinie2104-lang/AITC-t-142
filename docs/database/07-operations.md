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
| FK on a **partitioned** table (`lpr_event`) | PostgreSQL rejects `NOT VALID` here ("cannot add NOT VALID foreign key on partitioned table", verified on PG17, D-29). Either add the FK on the parent in a low-traffic window (it scans every partition under a SHARE ROW EXCLUSIVE lock), or add it per partition (`ALTER TABLE app.lpr_event_YYYYMM ADD CONSTRAINT … NOT VALID` + `VALIDATE`) and to each new partition in `ensure_lpr_partitions` |
| Add index | `CREATE INDEX CONCURRENTLY` in a revision that sets `transaction_per_migration` / uses `op.get_context().autocommit_block()`; check `pg_index.indisvalid` afterwards, drop and retry if invalid |
| Index on a partitioned table | `CREATE INDEX … ON ONLY app.lpr_event`, then `CREATE INDEX CONCURRENTLY` per partition, then `ALTER INDEX … ATTACH PARTITION` |
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

-- 3) lpr_event (partitioned): index per partition, then attach
ALTER TABLE app.lpr_event ADD COLUMN lane text;
CREATE INDEX lpr_event_lane_idx ON ONLY app.lpr_event (lane);                  -- invalid until all attached
CREATE INDEX CONCURRENTLY lpr_event_202611_lane_idx ON app.lpr_event_202611 (lane);   -- repeat per partition
ALTER INDEX app.lpr_event_lane_idx ATTACH PARTITION app.lpr_event_202611_lane_idx;   -- repeat per partition
-- after the last ATTACH the parent index becomes valid (verified)
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
for `migrator`. Plate encryption uses app-side AES-256-GCM with KMS envelope keys and a separate HMAC (blind-index) key
(D-07, [ADR-0005 amendment](adr-proposals/ADR-0005-amendment.md)); no key ever reaches the DB or the repo.

**Row-level security**: enabled on 48 tables (02 §20); context set with `SET LOCAL` per transaction (ADR-0005).
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

**Retention (D-05, D-06, D-12 — table `app.retention_rule`)**. Periods are data; changing one needs no migration.

| Data class | Keep | Enforced by | Basis |
|-----------|------|-------------|-------|
| `lpr_event` (plate reads) | 90 days | `app.drop_expired_lpr_partitions()` daily | Location trail, minimisation; forecasts use `occupancy_hourly` |
| `parking_session` | 180 days | `app.purge_expired()` | Overstay / reconciliation claims |
| `occupancy_hourly` (no personal data) | 3 years | `app.purge_expired()` | N4 forecasts across 3 Tết seasons |
| Dispute photos (S3) | 1 year after ticket closure | S3 lifecycle + key rows by `purge_expired()` | Complaint window |
| `plate_access_log`, `audit_log` | 5 years | `app.purge_expired()` (only path allowed by the append-only trigger) | Decree 356 processing records ≥ 5 years |
| `privacy_request` | 5 years after completion | `app.purge_expired()` | Proof of handling |
| Ledger, agreements, payments | 10 years, never by job | Manual archive + `pg_dump` to S3 Object Lock | Accounting documents (Decree 174/2016) |
| Notifications / published outbox / idempotency keys / expired tokens & OTP | 180 / 7 / 30 / 30 days | `app.purge_expired()` | Operational only |
| LangGraph checkpoints of finished threads | 30 days | `app.purge_agent_checkpoints()` | D-12 |

Schedule (owner role, daily, in this order): `ensure_lpr_partitions(2)` → N4 aggregation into `occupancy_hourly`
→ `drop_expired_lpr_partitions()` → `purge_expired()` → `purge_agent_checkpoints()`. Alert if any returns an error
or the default LPR partition holds rows.

**Data-subject requests (D-14, D-15; PDPL 91/2025/QH15, Decree 356/2025/ND-CP)**. Each request is a row in
`app.privacy_request`; the app sets `due_at` by kind and an N-job alerts the zone's DPO contact 3 days before:

| Kind | Acknowledge | Complete within |
|------|-------------|-----------------|
| `access`, `rectify` | 2 working days | 10 days |
| `withdraw_consent`, `restrict`, `object` | 2 working days | 15 days (20 with a processor) |
| `delete` | 2 working days | 20 days (30 with a processor) |

Deadlines come from secondary summaries of Decree 356 Art. 5 — confirm against the official text (10-decision-log
D-15). **Erasure** = `app.erase_user(user, request)` as a system job: refuses while the person has live bookings;
scrubs name, phone, email, password hash, plate ciphertext and hash, notes and dispute descriptions; withdraws
consents; deletes tokens, OTPs and notifications; keeps ids so the immutable ledger (ids and amounts only) stays
valid. Withdrawing the plate/photo consent alone deactivates the person's vehicles (no LPR matching) without
deleting the account.

**Agent schema (`agent`, LangGraph checkpointer) — D-12**. RLS cannot inspect serialized state, so:
(1) isolation — `parksmart_app` has no access to `agent`, `parksmart_checkpointer` none to `app` (tested in 08 §9.9);
(2) content rule — state may hold ids, pseudonyms (`NT-7`), pseudonymised text and enum values only; never names,
phones, plates, raw user messages or the pseudonym map in clear. Keep the pseudonym map in Redis with a TTL, or
use the library's encrypted serializer if the pinned version provides one (**not verified**); add a unit test
that serialises a finished state and asserts no plate/phone pattern appears;
(3) retention — finished threads purged after 30 days. Default privileges grant `parksmart_owner` SELECT/DELETE on
tables the checkpointer creates so the purge job can run.

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
