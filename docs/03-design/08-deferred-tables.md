# 08 — Deferred tables (v2 → v3 MVP)

> **Status:** v3, 2026-11-18. The MVP schema has **27 tables** ([D-31](07-db-decision-log.md)). This file lists the
> **30 tables removed from the v2 design (57 tables)**, why each one was cut, which feature it serves, and what
> migration brings it back.
>
> **Recover the v2 DDL** (tables, enums, triggers, RLS, grants, comments):
> `git show 333b85b:docs/database/02-schema.sql` (tests: `git show 333b85b:docs/database/08-seed-and-tests.sql`).
> The v2 dictionary, ERD and operations notes are at the same commit.

**Migration kinds.** *New table only*: nothing in the 27 tables holds the data yet, so a plain Alembic revision
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
| `consent` | Versioned consent records and withdrawal history per user and kind | A-03, PDPL consent proof | `app_user.consent_text_version`, `consented_at` (CHECK both null or both set) | New table + backfill from `app_user.consent_*` (one `granted` row per user) |
| `knowledge_doc` | One row per source document (title, URI, version, active flag); chunks reference it | W7 RAG | `knowledge_chunk.doc_title`, `source_uri`, `doc_version`, `is_active` | New table + backfill: one row per distinct `(source_uri, doc_version)` of `knowledge_chunk`, add FK, drop the doc columns |
| `workflow_run` | Per-run record of an agent workflow (status, initiator) for audit | ADR-0010 HITL, W0–W7 | LangGraph checkpointer, `approval_request.thread_id`, OTel traces | New table only (runs before the cut-over are not reconstructable) |
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
| `overstay_case` | A detected overstay with reminders and the fee decision | FR-11/12, BR-08, D-03 | New table only, together with the `zone_policy` columns `overstay_grace`, `overstay_fee_per_hour_vnd`, `overstay_reminder_every` and ledger/payment kind `overstay_fee` |
| `voucher` | Free-use voucher for shophouse guests, bound to TH3 | BR-06, FR-22, AC-16 | New table only; re-add `payment.voucher_id`, `payment.discount_vnd`, `gross_vnd`, trigger `payment_validate_voucher`. Existing `payment.amount_vnd` rows stay valid (`gross_vnd = amount_vnd`) |
| `dispute_category` | Catalogue of dispute reasons | FR-13…16, M10 | New table only |
| `dispute_ticket` | A dispute ticket routed to the slot zone's BQL, with AI suggestion fields | FR-13…16, BR-18, BR-14 | New table only |
| `dispute_party` | Parties of a ticket (reporter, counterparty, masked plates) | FR-14, BR-09 | New table only |
| `dispute_evidence` | Photo hash, LPR event snapshot, ledger reference | FR-15, D-05 (snapshot instead of raw LPR row) | New table only |
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
| `retention_rule` | Retention period per data class, read by the purge job | D-05 (LPR 90 days), D-06 (logs 5 years, notifications 180 days, outbox 7 days, keys 30 days), D-12 (agent checkpoints 30 days) | New table only; seed the periods from the decision log; re-add `purge_expired`, `purge_agent_checkpoints`, and the `purgeable` branch of `reject_mutation()` |
| `privacy_request` | Tracks data-subject requests with `due_at` (ack 2 working days, access/rectify 10, withdraw 15, delete 20 days) | D-14, D-15, PDPL, Decree 356 Art. 5 | New table only, together with `erase_user`; `vehicle.plate_*` and `app_user.phone_e164` are already nullable with CHECKs in v3, so no column change is needed |
| `occupancy_hourly` | Hourly occupancy history with no personal data, kept after raw LPR is purged | FR-20, N3/N4, D-05 | New table only (history starts when the table ships) |
| `vacancy_forecast` | Forecast of free slots per zone and hour | FR-05, FR-20, N4 | New table only |

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

`reject_mutation()` also lost its `purgeable` branch: in v3, `audit_log` and the ledger accept no DELETE at all.
Enums trimmed in v3 (`holding_kind`, `approval_kind`, `ledger_entry_type`, `payment_kind`) get their values back
with the feature that uses them; enums dropped entirely (`voucher_status`, `lpr_source_kind`, `overstay_status`,
the `dispute_*`, `swap_*`, `workflow_*`, `privacy_request_*` families, `evidence_kind`, `need_status`,
`day_kind`, `consent_kind`) are in the v2 DDL.

## How to restore a table

1. Copy the table, its indexes, RLS policies, grants, triggers and comments from the v2 DDL
   (`git show 333b85b:docs/database/02-schema.sql`).
2. Add the columns it needs on surviving tables (see the "Migration" cells above), as an Alembic revision in
   plain SQL (ADR-0005, skill `new-migration`).
3. For *new table + backfill*, copy data from the merged column, verify counts, then drop the merged column in a
   later revision.
4. Extend `sql/seed-and-tests.sql` with the v2 tests for that table (same commit) and update 03 and the diagram.
