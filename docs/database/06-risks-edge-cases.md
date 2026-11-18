# 06 — Edge cases and risks

"Enforced by" names the object that makes the database itself refuse the bad state; the matching test in
[08-seed-and-tests.sql](08-seed-and-tests.sql) is cited as **T:** where one exists.

## 1. Edge cases specific to ParkSmart

| # | Edge case | Impact if unhandled | Mitigation / enforced by |
|---|-----------|---------------------|--------------------------|
| E-01 | **NULL validity end** on an entitlement (owners never expire) | `upper(valid_during) < now()` is NULL → owners silently excluded or included by mistake | Unbounded range = no expiry; checks use `valid_during @> now()` (NULL-safe). Expiry index excludes `upper_inf`. T: "L4 guest has no expiry" |
| E-02 | Empty / inverted / infinite time ranges | Zero-length bookings, `[x, -∞)`, never-ending holds | `app.is_finite_range()` CHECK on every booking/window/request range. T: "empty / inverted booking period" |
| E-03 | Blank strings (`'   '`) for names, codes, reasons | Unusable records, fake "reason" for decisions | `btrim(x) <> ''` CHECKs (also `agreement_template_md`, `level_code`). T: "blank name" |
| E-04 | Optional email | Two NULL emails collide or empty string stored | Partial unique index only `WHERE email IS NOT NULL`; app stores NULL, never `''` |
| E-05 | Duplicate phone on re-registration after account deletion | Deleted user blocks the number forever | Partial unique `WHERE deleted_at IS NULL`. T: "duplicate live phone number" |
| E-06 | Same plate on two family accounts | Uniqueness either blocks families or allows impersonation | Unique per `(user_id, plate_hash)` only; LPR match may return several vehicles → treated as ambiguous → review queue (Q13 to confirm) |
| E-07 | Plate formats: `30A-123.45`, `30a12345`, spaces, Unicode dashes | Same car hashes differently → LPR misses | App normalises before HMAC: NFKC, uppercase, strip everything except `[A-Z0-9]`. One function, unit-tested, used by registration and N1 |
| E-08 | Vietnamese names, sorting and search (`Đ`, tones) | Wrong order, search misses `Đỗ` for `do` | Store as entered (UTF8). Sort with ICU collation `COLLATE "vi-VN-x-icu"` in queries that sort by name; fuzzy search later with `unaccent` + `pg_trgm` |
| E-09 | Time zones: DB in UTC, users in UTC+7, "expires on day D", daily reconciliation | Off-by-7-hours expiry; reconciliation day split wrong | All `timestamptz`; `zone.timezone` decides local day; seed and app compute "end of day D" as `(D + 1) 00:00` in the zone's TZ. KPI `day` is a local `date`. Vietnam has no DST (no ambiguous hours) |
| E-10 | Half-open ranges: booking 08:00–12:00 then 12:00–14:00 | Back-to-back bookings rejected as overlapping, or real overlaps accepted | `tstzrange` default `[)`; `&&` treats adjacent ranges as non-overlapping |
| E-11 | Money rounding: hourly price × 1 h 20 min | Fractions of đồng; inconsistent totals | All amounts `bigint` VND. Rule engine rounds once per line item (round half up to 1 đ, or to a configured step such as 1 000 đ) and stores the result; DB never derives money from floats. `payment.amount_vnd` is a plain `bigint CHECK (>= 0)`; prices in `zone_policy.prices` are integers validated by the rule engine |
| E-12 | Integer overflow | `ref_no`, counters overflow | `bigint` ids/sequences; `smallint` only for bounded counters with CHECKs (attempts ≤ 10, hour 0–23) |
| E-13 | Empty lists: zone with no TH3 left, user with no entitlement | NULL aggregates, crashes | `eligibility_level_at` always returns one row (L4 fallback); matching returns 0 rows → `no_match` outcome stored (counted by `kpi_daily_v`) |
| E-14 | Vehicle bigger than any slot of the zone | Endless no-match | Rule engine returns `no_match`, W1 suggests other zones (FR-27); DB still refuses a mis-sized booking (`vehicle.size_class <= slot.size_class` on the ordered enum `app.size_class`, BR-11). T: "BR-11 XL pickup" |
| E-15 | Entitlement expires during an active booking | Renter evicted mid-period, or new bookings allowed | Level is checked at booking time (start of period). A running booking continues for at most `zone_policy.eligibility_grace_max` (default 7 days, D-04), never past its end; N6 closes it and notifies both parties. T: "BR-16 expired tenant claims L1" |
| E-16 | Owner returns early and TH3 is full | Renter left without a slot | Transaction commits nothing; W3 suggests other zones or escalates to BQL (`approval_kind = early_return_escalation`) |
| E-17 | Hold expired but sweeper not yet run | Slot looks booked; seekers turned away | Booking transaction first expires stale holds on that slot (05 §1); sweeper every minute |
| E-18 | Agreement deadline passes with one confirmation | Booking blocks the slot forever | Confirm UPDATE requires `confirm_deadline > now()`; sweeper expires agreement + booking (`agreement_deadline_idx`) |
| E-19 | Unintended cascading deletes | Deleting a zone/user wipes bookings, ledger | `ON DELETE RESTRICT` on every business FK; CASCADE only for owned auxiliaries (01 §4). T: "deleting a user with history", "deleting a zone" |
| E-20 | Orphans: polymorphic `ledger_entry.subject_id`, `approval_request.subject_id` | Dangling references | Written in the same transaction as their subject; `ledger_entry.subject_type` CHECK limits it to `agreement`, `booking`, `payment`. Reverse FK exists where integrity matters (`agreement.approval_request_id`). Orphan reconciliation report is deferred |
| E-21 | Retries / repeated requests: double click, LangGraph replay after `interrupt()`, arq retry, vendor re-send | Two holds, two ledger entries, two payments, duplicate LPR | UNIQUE `idempotency_key` on booking, request, payment, notification, ledger, share_window; `UNIQUE (zone_id, source_code, source_event_id)` + ON CONFLICT for LPR; `idempotency_keys` table for other steps. T: "replayed booking idempotency key", "ledger_append is idempotent", "LPR duplicate" |
| E-22 | Imported / legacy data (resident lists from each BQL, A-09) | Bad imports bypass app rules | Imports load into a staging table, then `INSERT … SELECT` into `asset`/`eligibility` as `pending`; the same constraints apply; a BQL verifies. Never `session_replication_role = replica` (it disables triggers) |
| E-23 | Cross-zone references (slot of zone A in a zone C booking) | Data visible to the wrong BQL; BR-10 broken | Composite FKs `(x_id, zone_id)`. T: "booking a zone-A slot under zone C" |
| E-24 | LPR clock skew / out-of-order events / far-future timestamps | Misleading event order | Events keep both `occurred_at` and `created_at`; no partition-range failure any more (plain table). Entry/exit pairing is deferred with `parking_session` |
| E-25 | OCR confidence edge values (exactly the threshold, > 1, NULL) | Wrong routing to review | `ocr_confidence NOT NULL CHECK 0..1`; rule `< threshold → review` (equal passes). T: "OCR confidence above 1" |
| E-27 | A user books their own shared slot | Self-dealing, KPI inflation | CHECK `provider_user_id <> renter_user_id` |
| E-28 | `jsonb` key order / whitespace in ledger payload | Hash differs on re-verification | `jsonb::text` is canonical (sorted keys, normalised spacing); time hashed as epoch microseconds; verified by `ledger_verify` |
| E-31 | A holding entered by mistake (wrong owner) | Slot blocked for the real holder by the EXCLUDE constraint | `slot_holding.voided_at` + mandatory `void_reason`; the EXCLUDE ignores voided rows. T: "(a) voided holding frees the slot" |
| E-33 | Owner returns early and the TH3 price is higher than the share price | Renter pays more for the relocated period | Accepted by D-09 (renter pays the TH3 price, provider pays nothing); the ledger payload records the split so a later policy can refund it. Flag for BQL review |

### Deferred edge cases (see [11-deferred-tables](11-deferred-tables.md))

Their objects are not in the 27-table schema; the v2 text is in git (`333b85b`). Each returns with its table.

| # | Edge case | Returns with |
|---|-----------|--------------|
| E-26 | Voucher misuse (TH1 booking, double redemption, expiry) | `voucher` |
| E-29 | Erasure requested while the person has live bookings or open disputes (`erase_user` refuses, `due_at` alert) | `privacy_request`, `erase_user` |
| E-30 | LPR partition dropped while a dispute still needs the event (evidence `snapshot`) | `dispute_evidence`, LPR partitioning |
| E-32 | BQL approves a swap before a party agreed (`swap_proposal_validate`) | `swap_*` |
| E-34 | Retention purge deleting from append-only logs (only `purge_expired()` may) | `retention_rule`, `purge_expired` |

## 2. Risks

| # | Risk | Impact | Mitigation |
|---|------|--------|------------|
| R-01 | App connects without setting the RLS context | Empty results (safe) or, if a role bypasses RLS, a data leak | Missing settings resolve to "no access" (test "no context → nothing visible"); app role is `NOBYPASSRLS` and not the owner; single `unit_of_work` helper; integration test per policy |
| R-02 | `system` role context is broad (jobs) | A job for zone A reads zone B | `system` is still scoped by `app.zone_ids`; jobs run per zone (ADR-0005); N7/N8 read only `app.kpi_daily_v` |
| R-03 | `SECURITY DEFINER` functions abused | Privilege escalation, IDOR | Fixed `search_path = pg_catalog, app`; role/zone checks inside; `EXECUTE` revoked from PUBLIC; IDOR test on `eligibility_level_at` |
| R-04 | Plate key leak | Plates decryptable | **Decided (D-07):** app-side AES-256-GCM with KMS envelope keys + separate HMAC key; the DB never sees a key. Proposal: `adr-proposals/ADR-0005-amendment.md`. Rotation via `plate_key_version` |
| R-05 | LangGraph checkpoints (schema `agent`) hold personal data outside RLS | Cross-zone leak via checkpointer tables | **D-12:** schema isolation both ways (tested), content rule (ids/pseudonyms only, no pseudonym map in clear). The 30-day checkpoint purge (`purge_agent_checkpoints`) is deferred, so finished threads accumulate until a job exists. Still open: real library table layout and encrypted serializer not verified |
| R-06 | Ledger tampering by a DBA | Integrity claim broken | Hash chain + `ledger_verify` detects edits (test "tampered seq 1 is reported"); periodically export each zone's head hash to S3 with Object Lock so a rewrite of the whole chain is also detectable |
| R-07 | Unpartitioned `lpr_event` grows without bound | Slow scans, no cheap retention | Fine for demo volume. Revisit before real LPR feeds: partition by month + retention (deferred, 11-deferred-tables); the dedupe key would then need the partition column |
| R-08 | Hot row `ledger_head` | Append latency under load | One row per zone, lock held for one INSERT + UPDATE; far below AS-01 rates. Revisit only above ~500 appends/s per zone |
| R-09 | Trigger logic diverges from the rule engine | Valid bookings refused or rule engine bypassed | Triggers enforce only hard invariants with explicit BR ids; the parametrised rule tests (L1–L4 × scope × type) also run against the DB in integration tests |
| R-10 | Two Postgres drivers (asyncpg + psycopg 3), three processes | Connection exhaustion on `db.t4g.small` | Per-process pool budgets + PgBouncer in transaction mode (07 §4); note `SET LOCAL` works with transaction pooling, plain `SET` does not |
| R-11 | Enum evolution | `ALTER TYPE … ADD VALUE` cannot be used in the same transaction that uses the new value; dropping a value is hard (needs a new type + column rewrite) | Add values in a separate migration; never remove values (deprecate in code). Pick enum values carefully now, including the ordered `app.size_class` (a new size in the middle needs `ADD VALUE … BEFORE/AFTER`) |
| R-12 | Long migrations lock hot tables | Outage during deploy | Expand → migrate → contract, `CONCURRENTLY`, `NOT VALID` + `VALIDATE`, `lock_timeout` (07 §1) |
| R-13 | Single-AZ RDS (ADR-0005) | Hours of downtime on AZ failure | Acceptable for demo; Multi-AZ before real data (07 §2) |
| R-14 | BR-05 (free guest parking at the resident's own building) is not modelled as data | Paid guest arrangements outside the platform | Out of demo scope beyond TH3; rule engine blocks paid "guest" transactions; add a `guest_pass` table if the product needs it |
| R-15 | Docs disagree on stack (Supabase in backlog vs RDS/JWT in ADRs) | Team builds against the wrong platform | ADRs win (AS-17); flag to docs-keeper |
| R-16 | Business values were TBD (thresholds, buffers, fees, retention) | Wrong behaviour in production | Researched defaults in `zone_policy` column DEFAULTs and `zone_policy.prices`, each marked "default, confirm with BQL" and listed in 10-decision-log §1 (mostly low confidence). Changing them is a data change |
| R-17 | Never executed on PG 16; pgvector column never executed | A PG16-only incompatibility or vector DDL error at first deploy | DDL avoids PG17-only features. Local Docker cannot start (WSL2 VM crashes with a hardware Machine Check Exception) and downloading PG16 binaries was not permitted, so this stays open (D-30). Run both scripts on `pgvector/pgvector:pg16` in CI before the first migration lands |
| R-18 | Privacy framework changed: Decree 13/2023 no longer in force since 2026-01-01 | Docs and processes cite the wrong law | Design follows PDPL 91/2025/QH15 + Decree 356/2025/ND-CP (D-22); `docs/01-product/03-scope.md` should be updated by docs-keeper |
| R-19 | Cross-border transfer to Bedrock without the impact-assessment dossier | Regulatory sanction | Pseudonymised prompts only (BR-14); file the dossier within 60 days of the first transfer and a DPIA before real data (D-23) |
| R-20 | Index set never checked at realistic volume | Slow matching / queues at scale | Plans were forced on tiny tables (v3) or measured on v1/v2 data. Re-run 04's queries on staging volume before go-live (checklist #35) |
| R-21 | **Retention and erasure are not enforced in the MVP** (no `retention_rule`, `purge_expired`, `erase_user`, `privacy_request`) | Personal data kept past legal limits; erasure requests cannot be served (PDPL 91/2025/QH15, Decree 356/2025/ND-CP) | Demo uses synthetic data only. Must exist before any real user data (D-05/D-06/D-14/D-15 are documented targets, see 07 §3 and 11-deferred-tables) |
| R-22 | **Masked plates only**: `plate_ciphertext` stays column-revoked and no reveal function exists | A screen that shows an original plate would bypass AC-12 | AC-12 holds because no original is ever shown. Any screen with an original plate requires `plate_access_log` + a logged reveal function first (11-deferred-tables) |
| R-23 | **`zone_policy.prices` is JSONB, not constrained by the DB** (only `jsonb_typeof = 'object'`) | Malformed or negative price breaks charging; no FK to `slot_pool`/level codes | Rule engine (Pydantic) validates shape and non-negative integers before INSERT; unit tests on the schema; `payment.amount_vnd >= 0` is the last DB guard. Move to a `price_rule` table if prices need querying or history |
| R-24 | **Unpartitioned `lpr_event`** | See R-07 | Fine for demo volume; revisit before real LPR feeds |
| R-25 | `consent` is two columns on `app_user` | No withdrawal history, no per-purpose consent | Acceptable for MVP; a consent table returns with erasure/consent work (deferred) |
