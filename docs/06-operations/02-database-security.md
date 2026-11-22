# 02 — Database operations: security

> Database operations: [01 migrations, backup](01-database-operations.md) · [02 security](02-database-security.md) · [03 monitoring, scaling](03-database-monitoring-scaling.md)

Context: written for the target design: RDS PostgreSQL 16 (`db.t4g.small`, ADR-0005), app on EC2 (ADR-0004), secrets in
SSM (ADR-0009), OpenTelemetry → LGTM (ADR-0008). **Today** (ADR-0012, ADR-0013): Postgres 16 in a container on one
Lightsail for the demo (nightly `pg_dump` to S3), and on the CI runner for dev; RDS-only items (PITR, Performance
Insights, IAM auth, RDS Proxy) apply when moving back to RDS. Roles, RLS and migration rules apply everywhere.

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

**Row-level security**: enabled on the zone- and household-owned tables (see schema.sql; only `zone` deliberately has none — the 24 other tables have RLS, including `dispute_case` and `dispute_evidence` since v5); context set with `SET LOCAL` per transaction (ADR-0005).
Integration tests must cover: BQL zone A vs zone B, resident vs other resident, chain operator aggregates only,
no-context = nothing (all present in 08 §8).

**PII handling**

| Data | Protection |
|------|-----------|
| Plates | Encrypted (`plate_ciphertext`, column-revoked), HMAC for matching, masked for display. **MVP shows masked plates only** (AC-12 holds because no original is shown); a reveal function + `plate_access_log` must exist before any screen shows an original plate (deferred) |
| Names, phones, emails | Stored clear (needed for login/contact); RLS limits visibility; pseudonymised before LLM calls in `agent/infrastructure` (BR-14) |
| Unit numbers (`asset.code`) | RLS to the owning zone only (BR-17) |
| Photos | S3 (SSE-KMS), original keys column-revoked (`dispute_evidence.object_key_original`, v5), masked copies for disputes; the vision model receives masked photos only (BR-14) |
| Logs/traces | No parameter values in spans (ADR-0005); `log_min_duration_statement` logs statement text with `$n` placeholders only; never `log_statement = all` |

**Not in MVP: retention and data-subject requests.** `retention_rule`, `purge_expired`,
`drop_expired_lpr_partitions`, `privacy_request` and `erase_user` are removed from the MVP schema (D-31; 23 tables since D-32, 25 since D-33). The
targets stay as the requirement for the day real user data exists (PDPL 91/2025/QH15, Decree 356/2025/ND-CP):

| Target | Source | Where it returns |
|--------|--------|------------------|
| Retention periods per data class (LPR 90 days, sessions 180 days, logs 5 years incl. `ai_decision_log`, notifications 180 days, confirmation evidence and payments 10 years, never by job) | D-05, D-06 | [08-deferred-tables](../03-design/08-deferred-tables.md): `retention_rule`, `purge_expired`, LPR partitioning |
| Data-subject requests with legal deadlines (access/rectify 10 days, withdraw/restrict/object 15, delete 20; confirm against the official Decree 356 text) | D-14, D-15 | `privacy_request` |
| Erasure that keeps ids so the append-only `consent_record` evidence stays valid; refuses while bookings are live | D-14 | `erase_user` |

Until then: no personal data beyond synthetic demo accounts; `consent_record`, `ai_decision_log` and `dispute_evidence` are strictly append-only (no purge path);
only `notification` (and `knowledge_chunk`) can be trimmed by a plain DELETE job when volume needs it (the app role has DELETE on those two; see
schema.sql grants). There are no token or OTP tables to trim in v4: OTP keys expire in Redis. See risks R-21 and R-29 in [06](../03-design/06-risks-edge-cases.md).

**AI decision log and consent evidence (v4, D-32).** `ai_decision_log`, `consent_record` and (v5, D-33) `dispute_evidence` are append-only: the statement trigger
`reject_mutation()` rejects UPDATE/DELETE/TRUNCATE (also for the owner) and the app role has INSERT + SELECT only. Operating rules:

| Topic | Rule |
|-------|------|
| Content | Hashes and ids only (`user_hash` HMAC, `input_hash`/`output_hash` SHA-256, `trace_id`); never write a prompt, an output, a name, a plate or a GPS coordinate into these tables (renter ETA is stored as minutes, time and source only). Debugging detail goes to OTel with PII filtering (ADR-0008) |
| Retention | **Not enforced; the target must be decided before real data.** Proposal: 5 years for `ai_decision_log` (D-06 logs), 10 years for `consent_record`. A purge needs a privileged one-off job that drops the trigger inside a reviewed migration; there is no purge function. `user_hash` is personal data under PDPL, so a data-subject erasure rule is needed too (D-14) |
| Growth | About one row per AI step: watch the table size and `idempotency_key` index size monthly; partition by `created_at` only past ~50 M rows (see [03 §5](03-database-monitoring-scaling.md)) |
| Integrity | No hash chain in v4: protection = trigger + grants + backups. Keep the weekly logical export ([01 §2](01-database-operations.md)); never grant UPDATE/DELETE to any application role |
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
