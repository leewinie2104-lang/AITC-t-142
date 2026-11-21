# 01 — Database operations: migrations, backup

> Database operations: [01 migrations, backup](01-database-operations.md) · [02 security](02-database-security.md) · [03 monitoring, scaling](03-database-monitoring-scaling.md)

Context: written for the target design: RDS PostgreSQL 16 (`db.t4g.small`, ADR-0005), app on EC2 (ADR-0004), secrets in
SSM (ADR-0009), OpenTelemetry → LGTM (ADR-0008). **Today** (ADR-0012, ADR-0013): Postgres 16 in a container on one
Lightsail for the demo (nightly `pg_dump` to S3), and on the CI runner for dev; RDS-only items (PITR, Performance
Insights, IAM auth, RDS Proxy) apply when moving back to RDS. Roles, RLS and migration rules apply everywhere.

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

**Worked examples** (executed on PostgreSQL 17.10, check e): `booking` add column + index `CONCURRENTLY` + FK `NOT VALID` / `VALIDATE`;
`notification` NOT NULL in steps. Full SQL: `git show feff7b5:docs/06-operations/01-database-operations.md`.

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
