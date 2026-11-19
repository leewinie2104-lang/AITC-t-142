# 03 — Database operations: monitoring, scaling

> Database operations: [01 migrations, backup](01-database-operations.md) · [02 security](02-database-security.md) · [03 monitoring, scaling](03-database-monitoring-scaling.md)

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
