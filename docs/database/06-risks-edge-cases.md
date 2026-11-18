# 06 — Edge cases and risks

"Enforced by" names the object that makes the database itself refuse the bad state; the matching test in
[08-seed-and-tests.sql](08-seed-and-tests.sql) is cited as **T:** where one exists.

## 1. Edge cases specific to ParkSmart

| # | Edge case | Impact if unhandled | Mitigation / enforced by |
|---|-----------|---------------------|--------------------------|
| E-01 | **NULL validity end** on an entitlement (owners never expire) | `upper(valid_during) < now()` is NULL → owners silently excluded or included by mistake | Unbounded range = no expiry; checks use `valid_during @> now()` (NULL-safe). Expiry index excludes `upper_inf`. T: "L4 guest has no expiry" |
| E-02 | Empty / inverted / infinite time ranges | Zero-length bookings, `[x, -∞)`, never-ending holds | `app.is_finite_range()` CHECK on every booking/window/request range. T: "empty / inverted booking period" |
| E-03 | Blank strings (`'   '`) for names, codes, reasons | Unusable records, fake "reason" for plate views | `btrim(x) <> ''` CHECKs; plate-view reason ≥ 5 chars. T: "blank name", "reveal without a reason" |
| E-04 | Optional email | Two NULL emails collide or empty string stored | Partial unique index only `WHERE email IS NOT NULL`; app stores NULL, never `''` |
| E-05 | Duplicate phone on re-registration after account deletion | Deleted user blocks the number forever | Partial unique `WHERE deleted_at IS NULL`. T: "duplicate live phone number" |
| E-06 | Same plate on two family accounts | Uniqueness either blocks families or allows impersonation | Unique per `(user_id, plate_hash)` only; LPR match may return several vehicles → treated as ambiguous → review queue (Q13 to confirm) |
| E-07 | Plate formats: `30A-123.45`, `30a12345`, spaces, Unicode dashes | Same car hashes differently → LPR misses | App normalises before HMAC: NFKC, uppercase, strip everything except `[A-Z0-9]`. One function, unit-tested, used by registration and N1 |
| E-08 | Vietnamese names, sorting and search (`Đ`, tones) | Wrong order, search misses `Đỗ` for `do` | Store as entered (UTF8). Sort with ICU collation `COLLATE "vi-VN-x-icu"` in queries that sort by name; fuzzy search later with `unaccent` + `pg_trgm` |
| E-09 | Time zones: DB in UTC, users in UTC+7, "expires on day D", daily reconciliation | Off-by-7-hours expiry; reconciliation day split wrong | All `timestamptz`; `zone.timezone` decides local day; seed and app compute "end of day D" as `(D + 1) 00:00` in the zone's TZ. KPI `day` is a local `date`. Vietnam has no DST (no ambiguous hours) |
| E-10 | Half-open ranges: booking 08:00–12:00 then 12:00–14:00 | Back-to-back bookings rejected as overlapping, or real overlaps accepted | `tstzrange` default `[)`; `&&` treats adjacent ranges as non-overlapping |
| E-11 | Money rounding: hourly price × 1 h 20 min, overstay prorata | Fractions of đồng; inconsistent totals | All amounts `bigint` VND. Rule engine rounds once per line item (round half up to 1 đ, or to a configured step such as 1 000 đ) and stores the result; DB never derives money from floats. `amount_vnd` is generated from integers |
| E-12 | Integer overflow | `ref_no`, counters overflow | `bigint` ids/sequences; `smallint` only for bounded counters with CHECKs (attempts ≤ 10, hour 0–23) |
| E-13 | Empty lists: zone with no TH3 left, user with no entitlement, no forecast history | NULL aggregates, crashes | `eligibility_level_at` always returns one row (L4 fallback); matching returns 0 rows → `no_match` outcome stored; forecast keeps `sample_days` so the UI can say "not enough data" |
| E-14 | Vehicle bigger than any slot of the zone | Endless no-match | Rule engine returns `no_match`, W1 suggests other zones (FR-27); DB still refuses a mis-sized booking. T: "BR-11 XL pickup" |
| E-15 | Entitlement expires during an active booking | Renter evicted mid-period, or new bookings allowed | Level is checked at booking time (start of period). Running bookings continue (BR-16); `zone_policy.eligibility_grace_max` caps the carry-over when defined. T: "BR-16 expired tenant claims L1" |
| E-16 | Owner returns early and TH3 is full | Renter left without a slot | Transaction commits nothing; W3 suggests other zones or escalates to BQL (`approval_kind = early_return_escalation`) |
| E-17 | Hold expired but sweeper not yet run | Slot looks booked; seekers turned away | Booking transaction first expires stale holds on that slot (05 §1); sweeper every minute |
| E-18 | Agreement deadline passes with one confirmation | Booking blocks the slot forever | Confirm UPDATE requires `confirm_deadline > now()`; sweeper expires agreement + booking (`agreement_deadline_idx`) |
| E-19 | Unintended cascading deletes | Deleting a zone/user wipes bookings, ledger, disputes | `ON DELETE RESTRICT` on every business FK; CASCADE only for owned auxiliaries (01 §4). T: "deleting a user with history", "deleting a zone" |
| E-20 | Orphans: event ids in `parking_session`, polymorphic `ledger_entry.subject_id`, `approval_request.subject_id` | Dangling references | Written in the same transaction as their subject; N3 reconciliation reports orphans. Reverse FKs exist where integrity matters (`agreement.approval_request_id`, `swap_proposal.approval_request_id`) |
| E-21 | Retries / repeated requests: double click, LangGraph replay after `interrupt()`, arq retry, vendor re-send | Two holds, two ledger entries, two payments, duplicate LPR | UNIQUE `idempotency_key` on booking, request, payment, ticket, swap, notification, ledger; ON CONFLICT for LPR; `idempotency_keys` table for other steps. T: "replayed booking idempotency key", "ledger_append is idempotent", "LPR duplicate" |
| E-22 | Imported / legacy data (resident lists from each BQL, A-09) | Bad imports bypass app rules | Imports load into a staging table, then `INSERT … SELECT` into `asset`/`eligibility` as `pending`; the same constraints apply; a BQL verifies. Never `session_replication_role = replica` (it disables triggers) |
| E-23 | Cross-zone references (slot of zone A in a zone C booking, cross-zone swap) | Data visible to the wrong BQL; BR-10 broken | Composite FKs `(x_id, zone_id)`. T: "booking a zone-A slot under zone C", "BR-10 swap leg" |
| E-24 | LPR clock skew / out-of-order events / far-future timestamps | Rows in the wrong partition, exit before entry | Default partition catches out-of-range rows (alert if non-empty); exit without open session is kept and reported by N3 |
| E-25 | OCR confidence edge values (exactly the threshold, > 1, NULL) | Wrong routing to review | `ocr_confidence NOT NULL CHECK 0..1`; rule `< threshold → review` (equal passes). T: "OCR confidence above 1" |
| E-26 | Voucher misuse (TH1 booking, double redemption, expired) | Guests upgrade to TH1/TH2; money leak | CHECK + trigger (TH3 only), UNIQUE `payment.voucher_id`, conditional redeem UPDATE. T: "AC-16 voucher on a TH1 share booking", "voucher redeemed twice" |
| E-27 | A user books their own shared slot | Self-dealing, KPI inflation | CHECK `provider_user_id <> renter_user_id` |
| E-28 | `jsonb` key order / whitespace in ledger payload | Hash differs on re-verification | `jsonb::text` is canonical (sorted keys, normalised spacing); time hashed as epoch microseconds; verified by `ledger_verify` |

## 2. Risks

| # | Risk | Impact | Mitigation |
|---|------|--------|------------|
| R-01 | App connects without setting the RLS context | Empty results (safe) or, if a role bypasses RLS, a data leak | Missing settings resolve to "no access" (test "no context → nothing visible"); app role is `NOBYPASSRLS` and not the owner; single `unit_of_work` helper; integration test per policy |
| R-02 | `system` role context is broad (jobs) | A job for zone A reads zone B | `system` is still scoped by `app.zone_ids`; jobs run per zone (ADR-0005); N7/N8 read only `kpi_daily` |
| R-03 | `SECURITY DEFINER` functions abused | Privilege escalation, IDOR | Fixed `search_path = pg_catalog, app`; role/zone checks inside; `EXECUTE` revoked from PUBLIC; IDOR test on `eligibility_level_at` |
| R-04 | Plate key leak (pgcrypto variant: key in SQL text) | Plates decryptable | Prefer app-side AES-GCM with KMS; never `log_statement = all`; `pg_stat_statements` stores normalised text only; key rotation via `plate_key_version` |
| R-05 | LangGraph checkpoints (schema `agent`) contain PII (pseudonym maps, user text) outside RLS | Cross-zone leak via checkpointer tables | Separate role `parksmart_checkpointer` with rights on `agent` only; keep pseudonym maps out of persisted state or encrypt them; retention purge of finished threads (07 §3) |
| R-06 | Ledger tampering by a DBA | Integrity claim broken | Hash chain + `ledger_verify` detects edits (test "tampered seq 1 is reported"); periodically export each zone's head hash to S3 with Object Lock so a rewrite of the whole chain is also detectable |
| R-07 | `lpr_event` default partition fills (missing future partition) | Later `CREATE PARTITION` fails for that range | Daily `ensure_lpr_partitions(2)`; alert when default partition has rows |
| R-08 | Hot row `ledger_head` | Append latency under load | One row per zone, lock held for one INSERT + UPDATE; far below AS-01 rates. Revisit only above ~500 appends/s per zone |
| R-09 | Trigger logic diverges from the rule engine | Valid bookings refused or rule engine bypassed | Triggers enforce only hard invariants with explicit BR ids; the parametrised rule tests (L1–L4 × scope × type) also run against the DB in integration tests |
| R-10 | Two Postgres drivers (asyncpg + psycopg 3), three processes | Connection exhaustion on `db.t4g.small` | Per-process pool budgets + PgBouncer in transaction mode (07 §4); note `SET LOCAL` works with transaction pooling, plain `SET` does not |
| R-11 | Enum evolution | `ALTER TYPE … ADD VALUE` cannot be used in the same transaction that uses the new value | Separate migration for the enum change; never remove values (deprecate in code) |
| R-12 | Long migrations lock hot tables | Outage during deploy | Expand → migrate → contract, `CONCURRENTLY`, `NOT VALID` + `VALIDATE`, `lock_timeout` (07 §1) |
| R-13 | Single-AZ RDS (ADR-0005) | Hours of downtime on AZ failure | Acceptable for demo; Multi-AZ before real data (07 §2) |
| R-14 | BR-05 (free guest parking at the resident's own building) is not modelled as data | Paid guest arrangements outside the platform | Out of demo scope beyond TH3/voucher; rule engine blocks paid "guest" transactions; add a `guest_pass` table if the product needs it |
| R-15 | Docs disagree on stack (Supabase in backlog vs RDS/JWT in ADRs) | Team builds against the wrong platform | ADRs win (AS-17); flag to docs-keeper |
| R-16 | Values marked TBD (thresholds, buffers, fees, retention) | Wrong behaviour in production | All are data in `zone_policy`/`lpr_source`; demo values in seed; listed in 00 §5 |
| R-17 | Schema verified on PG 17.10, target is PG 16; pgvector column not executed | A PG16-only incompatibility or vector DDL error at first deploy | DDL avoids PG17 features (identity on partitioned tables replaced by a sequence); run both scripts on `pgvector:pg16` in CI before the first migration lands |
