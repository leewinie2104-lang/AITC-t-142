# 08 — Deferred tables (v2 → v3 → v4 MVP)

> **Status:** v4, 2026-11-18. The MVP schema has **23 tables** ([D-32](07-db-decision-log.md#d-32),
> [ADR-0011](../10-adr/ADR-0011-mvp-simplifications.md)). This file lists **38 deferred tables**: the **30 tables removed
> from the v2 design (57 tables) in v3** ([D-31](07-db-decision-log.md#0-mvp-scope-decision-d-31), groups a–c) plus the
> **8 tables removed from v3 in v4** (group d). For each: why it was cut, which feature it serves, what replaces it now
> and what migration brings it back. The last section lists designs from the team's alternative DBML proposal to reuse
> when the matching feature returns.
>
> Two of the 30 v2 tables have a **successor with a different design** in v4: `workflow_run` (role taken by
> `agent_thread`) and `consent` (role taken by `consent_record`). They stay in the lists below because their v2 design
> is not restored as such.
>
> **Recover the v2 DDL** (tables, enums, triggers, RLS, grants, comments):
> `git show 333b85b:docs/database/02-schema.sql` (tests: `git show 333b85b:docs/database/08-seed-and-tests.sql`).
> The v2 dictionary, ERD and operations notes are at the same commit.

**Migration kinds.** *New table only*: nothing in the 23 tables holds the data yet, so a plain Alembic revision
creates the table (plus RLS, grants, triggers copied from v2). *New table + backfill*: the data currently lives in
a merged column; the revision creates the table, copies the data, then (optionally, in a later revision) drops
the merged column.

**Order.** Bring tables back in the order of the groups below. Group (c) is required before real user data;
within group (b), `plate_access_log` comes first.

## (a) Data quality and configuration (v2 tables 28–39)

Small tables whose job was normalisation. In v3 they are columns, enums or JSON. Bring them back when the merged
column causes real pain (typos in codes, per-zone config that must be versioned or queried).

| Removed table | Problem it solves | Serves | v3 replacement | Migration |
|---------------|-------------------|--------|----------------|-----------|
| `consent` | Versioned consent records and withdrawal history per user and kind | A-03, PDPL consent proof | v3: `app_user.consent_text_version`, `consented_at`. **v4:** `consent_record` (append-only, `accepted`/`rejected`/`withdrawn`, per action and terms version; those `app_user` columns are removed) | Largely delivered by `consent_record`; restore the v2 table only if a separate per-kind catalogue is needed (new table + backfill from `consent_record`) |
| `knowledge_doc` | One row per source document (title, URI, version, active flag); chunks reference it | W7 RAG | `knowledge_chunk.doc_title`, `source_uri`, `doc_version`, `is_active` | New table + backfill: one row per distinct `(source_uri, doc_version)` of `knowledge_chunk`, add FK, drop the doc columns |
| `workflow_run` | Per-run record of an agent workflow (status, initiator) for audit | ADR-0010 HITL, W0–W7 | v3: LangGraph checkpointer, `approval_request.thread_id`, OTel traces. **v4:** `agent_thread` (one row per thread: user, zone, workflow, status, `pending_card`) and `ai_decision_log` (one row per decision step) | Largely delivered by `agent_thread` + `ai_decision_log`; a per-run table is only needed for run-level metrics (new table only) |
| `kpi_daily` | Materialised daily KPIs, including metrics that need disputes and swaps | Scope §6 KPIs, N3 | view `app.kpi_daily_v` over `parking_request` | New table + backfill by running the view's query per day; then N-job fills it |
| `price_rule` | Prices by slot type × level × unit, versioned per policy | BR-19, FR-21 | `zone_policy.prices` jsonb | New table + backfill by exploding `zone_policy.prices` (one row per slot type, level, unit) |
| `agreement_template` | Versioned agreement text per zone, referenced by `agreement.template_id` | FR-08, AC-07 | `zone_policy.agreement_template_md` (versioned with the policy; `agreement` already pins `zone_policy_id`) | New table + backfill from `agreement_template_md`; add `agreement.template_id` and fill from the pinned policy |
| `subzone` | Sub-areas of a zone (khu nhỏ) as rows with names | PRD §2 hierarchy | `building.subzone_code text NULL` | New table + backfill from distinct `(zone_id, building.subzone_code)`, then FK |
| `basement` | Levels/basements as rows (name, capacity) | slot location, UX | `slot.level_code text NOT NULL` (e.g. `B2`, `G`) | New table + backfill from distinct `(building/zone, slot.level_code)`, then FK |
| `size_class` | Vehicle size catalogue with rank, editable by data | BR-11, FR-07 | ordered enum `app.size_class` (`S`, `M`, `L`, `XL`) | New table + backfill from the enum values (rank = enum order); columns become FKs |
| `chain` | The operator (chain) as a row; zones belong to a chain | PRD §2 (one operator, N zones) | dropped; `zone.code` is globally UNIQUE | New table + one row, add `zone.chain_id`, backfill to that row. Needed only for multi-operator |
| `lpr_source` | Camera/adapter registry with kind and per-source OCR threshold | FR-19, BR-13 | `lpr_event.source_code text NOT NULL`; threshold in `zone_policy.ocr_review_threshold` | New table + backfill from distinct `(zone_id, source_code)`; threshold copied from the zone policy |
| `gate` | Gates of a zone as rows | LPR screens, N-jobs | `lpr_event.gate_code text NOT NULL` | New table + backfill from distinct `(zone_id, gate_code)`, then FK |

## (b) Ưu tiên 3 features (v2 tables 40–53)

Each group serves a feature the backlog puts in Ưu tiên 3. Bring a group back together with its module.

| Removed table | Problem it solves | Serves | Migration |
|---------------|-------------------|--------|-----------|
| `plate_access_log` | Append-only log of every reveal of an original plate (who, why, when). **Must come first** if any screen shows an original plate | AC-12, BR-09, PRD §9, D-06 (5 years) | New table only, together with `reveal_lpr_plate` / `reveal_vehicle_plate` (see functions below) |
| `password_reset_token` | Single-use, expiring token for forgot-password | ADR-0006 (reset flow) | New table only |
| `holiday` | Holiday calendar per zone (`day_kind`) for forecasts and pricing windows | FR-20, N3/N4 | New table only (seed from the official calendar) |
| `parking_session` | Actual stay from LPR in/out, matched to a booking | FR-11, W4, BR-08 | New table only (needs `lpr_event`, which exists) |
| `overstay_case` | A detected overstay with reminders and the fee decision | FR-11/12, BR-08, D-03 | New table only, together with the `zone_policy` columns `overstay_grace`, `overstay_fee_per_hour_vnd`, `overstay_reminder_every` and payment kind `overstay_fee` (the v2 ledger type is not needed: there is no ledger in v4) |
| `voucher` | Free-use voucher for shophouse guests, bound to TH3 | BR-06, FR-22, AC-16 | New table only; re-add `payment.voucher_id`, `payment.discount_vnd`, `gross_vnd`, trigger `payment_validate_voucher`. Existing `payment.amount_vnd` rows stay valid (`gross_vnd = amount_vnd`) |
| `dispute_category` | Catalogue of dispute reasons | FR-13…16, M10 | New table only |
| `dispute_ticket` | A dispute ticket routed to the slot zone's BQL, with AI suggestion fields | FR-13…16, BR-18, BR-14 | New table only |
| `dispute_party` | Parties of a ticket (reporter, counterparty, masked plates) | FR-14, BR-09 | New table only |
| `dispute_evidence` | Photo hash, LPR event snapshot, evidence reference (v2: ledger entry; v4: a `consent_record` or agreement) | FR-15, D-05 (snapshot instead of raw LPR row) | New table only; see also the 2-table design below |
| `swap_need` | A resident's request to swap slots | FR-17, M11, BR-10 | New table only |
| `swap_proposal` | A proposed swap and its BQL decision | FR-17/18, BR-10, D-10 | New table only; re-add `slot_holding.swap_proposal_id`, `holding_kind = 'swap_usage'`, `approval_kind` value, trigger `swap_proposal_validate`, `zone_policy.swap_requires_party_consent` |
| `swap_leg` | Each party's side of a swap with `accepted_at` (consent) | FR-18, D-10 | New table only |
| `reconciliation_report` | N3 end-of-day reconciliation document | N3, Scope §6 | New table only |

## (c) Before real user data (v2 tables 54–57)

Compliance and forecasting tables. The MVP can run on demo data without them; it **must not** hold real user
data until `privacy_request` and `retention_rule` (and the functions that use them) exist. Legal basis: PDPL
91/2025/QH15 and Decree 356/2025/ND-CP (D-22).

| Removed table | Problem it solves | Serves | Migration |
|---------------|-------------------|--------|-----------|
| `retention_rule` | Retention period per data class, read by the purge job | D-05 (LPR 90 days), D-06 (logs 5 years, notifications 180 days, outbox 7 days, keys 30 days; v4: outbox and key tables are gone, `ai_decision_log` is the new log to cover), D-12 (agent checkpoints 30 days) | New table only; seed the periods from the decision log; re-add `purge_expired`, `purge_agent_checkpoints`, and the `purgeable` branch of `reject_mutation()` |
| `privacy_request` | Tracks data-subject requests with `due_at` (ack 2 working days, access/rectify 10, withdraw 15, delete 20 days) | D-14, D-15, PDPL, Decree 356 Art. 5 | New table only, together with `erase_user`; `vehicle.plate_*` and `app_user.phone_e164` are already nullable with CHECKs in v3, so no column change is needed |
| `occupancy_hourly` | Hourly occupancy history with no personal data, kept after raw LPR is purged | FR-20, N3/N4, D-05 | New table only (history starts when the table ships) |
| `vacancy_forecast` | Forecast of free slots per zone and hour | FR-05, FR-20, N4 | New table only |

## (d) Dropped in v4 (8 tables, D-32)

The v3 schema (27 tables) kept these for long-term operations; the 4-week demo does not need them
([ADR-0011](../10-adr/ADR-0011-mvp-simplifications.md)). The v3 DDL is in the git history of
`docs/03-design/sql/schema.sql` (before the v4 change), and the v3 tests in `seed-and-tests.sql`.

| Removed table | Problem it solves | Serves | v4 replacement | Migration (how to bring it back) |
|---------------|-------------------|--------|----------------|----------------------------------|
| `staff_zone` | A BQL member or guard working for several zones; source of the JWT claim `zone_ids` as a list | ADR-0006, BR-18 | `app_user.staff_zone_id` (one zone per staff member; CHECK: only `guard` / `zone_manager`); claim `zone_ids` = `{staff_zone_id}` | New table + backfill: one `(user_id, staff_zone_id)` row per user whose `staff_zone_id` is set; switch the claim builder and the RLS policies (`vehicle`, `app_user` zone-staff reads) to the junction; keep or drop the column in a later revision. Needed when one staff member serves two zones |
| `refresh_token` | Rotating hashed refresh tokens with reuse detection and family revocation; allows a short access token | ADR-0006 | Access JWT only, **8 h** lifetime, no revocation | New table only (no data to migrate; users log in again). Ship before real users, together with a 15-minute access token and the rotation recipe in [05-concurrency §9](05-concurrency.md) |
| `otp_challenge` | Hashed, expiring, attempt-limited OTP for agreement confirmation, stored in the DB | ADR-0006, AC-07 | Redis keys (hash, TTL, attempt counter); the DB keeps `agreement.*_confirmed_at` and a `consent_record` row | New table only, if OTP state must survive a Redis loss or be audited (OTP rows are short-lived: no backfill) |
| `ledger_entry`, `ledger_head` | Append-only, hash-chained ledger per zone with a verifiable chain, written by `ledger_append`, checked by `ledger_verify` | FR-09 (original wording), PRD §9 | FR-09 rewritten as confirmation evidence: `consent_record` (append-only by trigger and grants; no chain) | New tables + functions `ledger_hash`, `ledger_append`, `ledger_verify` + enum `ledger_entry_type` + backfill: replay `consent_record` rows per zone in `id` order to build the chain from a genesis hash (payments and early-return events before the cut-over have no ledger payload). Needed on a legal or operational requirement for tamper detection |
| `outbox` | Transactional outbox: events written in the business transaction, relayed at least once; carries `traceparent` | ADR-0005, ADR-0010 | `notification` inserted in the same transaction, realtime push after commit through the `platform.publish()` port | New table only, plus the relay job (`FOR UPDATE SKIP LOCKED`, [05-concurrency §11](05-concurrency.md)); implement it behind `platform.publish()` so use cases do not change. Needed when Ưu tiên 3 background jobs trigger Agent workflows |
| `idempotency_keys` | A shared table of keys for steps without a target row; purge after 30 days | ADR-0005, guide ch.7 | UNIQUE `idempotency_key` column on `booking`, `payment`, `share_window`, `parking_request`, `notification`, `recovery_case`, `ai_decision_log`; natural key on `consent_record` | New table only; keep the columns. Needed for a step that has no target row of its own |
| `audit_log` | Trigger-written history of config, eligibility, holding and approval changes | PRD §9, D-06 (5 years) | None. `zone_policy` is versioned (history of prices and rules); AI decisions are in `ai_decision_log` (a different table, not a replacement) | New table + function `audit_row()` + triggers on `zone_policy`, `eligibility`, `slot_holding`, `approval_request`; no backfill (history starts when it ships). Ưu tiên 3 |

## Designs to reuse from the alternative DBML proposal

The team also drew an 18-table DBML design. Three of its tables were adopted in v4 (`agent_thread`, `recovery_case`,
`consent_record`, rewritten to this repo's conventions: UUIDv7, enums instead of `varchar` statuses, composite FKs for
zone consistency, `idempotency_key`, RLS). The ideas below were **not** adopted now; each fits a feature that is
Ưu tiên 3, so adopt it **together with that module** and use it instead of the matching v2 tables. The DBML file itself is
not tracked in this repository: take field-level details from the team's copy and keep the conventions above.

| Alternative table | Idea | Why not now | Adopt with | Instead of |
|-------------------|------|-------------|------------|------------|
| `slot_usage_claims` | One table for every **temporary** use of a slot over a period (source = sharing reservation, temporary swap, relocation, maintenance), with one EXCLUDE rule as the single overlap arbiter; long-term rights stay in their own table | `slot_holding` + `share_window` + `booking` already carry rights; a second table now would create two sources of truth | Swaps (M11, W6): replaces `slot_holding.swap_proposal_id` / `holding_kind = 'swap_usage'` | The v2 `swap_usage` holding kind |
| `swap_proposals` | A **single table** for a two-party swap (initiator, both parties, both slots, period, status through `awaiting_consent` → `awaiting_manager` → `confirmed`); each party's consent is a separate evidence row (here: `consent_record`, action for swaps) | M11 is Ưu tiên 3 | Swaps (M11): one table instead of `swap_need` + `swap_proposal` + `swap_leg`; keep per-party `accepted_at` (D-10) and the BQL approval through `approval_request` | `swap_need`, `swap_proposal`, `swap_leg` |
| `dispute_cases` + `dispute_evidence` | A **two-table** dispute design; evidence rows carry a `confidence_label` and a kind `ai_vision_extraction` (a photo read by the vision model, shown as a suggestion with its confidence; the BQL decides, BR-14) | M10 is Ưu tiên 3 | Disputes (M10, W5): two tables instead of `dispute_category`, `dispute_ticket`, `dispute_party`, `dispute_evidence`; a plain enum or text code for the category | The 4 v2 dispute tables |
| `parking_sessions` | Physical occupancy (entry and exit from LPR) kept separate from usage rights | v4 holds `booking.checked_in_at` / `checked_out_at` for the demo | Overstay (W4, N2): add the table when there is more than one entry/exit per booking or an overstay case needs it | v2 `parking_session` (same idea) |

**Not adopted at all:** `households` / `memberships` (covered by `asset` + `eligibility`, which also give L1–L4), a vehicle
quota (not in the specs), and `varchar` status columns (this repo uses enums).

## Functions removed

| Function | Comes back with |
|----------|-----------------|
| `app.reveal_lpr_plate`, `app.reveal_vehicle_plate` | `plate_access_log` (group b) |
| `app.payment_validate_voucher` | `voucher` (group b) |
| `app.swap_proposal_validate` | `swap_proposal`, `swap_leg` (group b) |
| `app.ensure_lpr_partitions`, `app.drop_expired_lpr_partitions` | `lpr_event` partitioning ([01-data-model §4.8](01-data-model.md)); needs the copy-and-swap migration of a populated table |
| `app.purge_expired` | `retention_rule` (group c) |
| `app.erase_user` | `privacy_request` (group c) |
| `app.purge_agent_checkpoints` | `retention_rule` (group c) |
| `app.ledger_hash`, `app.ledger_append`, `app.ledger_verify` (removed in v4) | `ledger_entry`, `ledger_head` (group d) |
| `app.audit_row()` and its triggers (removed in v4) | `audit_log` (group d) |

`reject_mutation()` also lost its `purgeable` branch: from v3 on, append-only tables accept no DELETE at all (v4:
`consent_record` and `ai_decision_log`).
Enums trimmed in v3 (`holding_kind`, `approval_kind`, `payment_kind`; `ledger_entry_type` was trimmed in v3 and dropped in v4) get their values back
with the feature that uses them; enums dropped entirely (`voucher_status`, `lpr_source_kind`, `overstay_status`,
the `dispute_*`, `swap_*`, `workflow_*`, `privacy_request_*` families, `evidence_kind`, `need_status`,
`day_kind`, `consent_kind`) are in the v2 DDL.

## How to restore a table

1. Copy the table, its indexes, RLS policies, grants, triggers and comments from the v2 DDL
   (`git show 333b85b:docs/database/02-schema.sql`); for a group (d) table use the v3 version of `sql/schema.sql` from
   the git history of this folder.
2. Add the columns it needs on surviving tables (see the "Migration" cells above), as an Alembic revision in
   plain SQL (ADR-0005, skill `new-migration`).
3. For *new table + backfill*, copy data from the merged column, verify counts, then drop the merged column in a
   later revision.
4. Extend `sql/seed-and-tests.sql` with the v2 tests for that table (same commit) and update 03 and the diagram.
