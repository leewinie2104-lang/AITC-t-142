# 02 — Entity-relationship diagrams

Three diagrams, one per area, so each stays readable. They cover the **27 tables** of the v3 MVP schema. Only keys and
the columns that explain a relationship are shown; the full column list is in
[03-data-dictionary](03-data-dictionary.md), and a column-level drawing of every table is in
[diagrams/schema-diagram.html](diagrams/schema-diagram.html). `zone_id` appears on almost every table: it is the RLS key, and composite
FKs `(x_id, zone_id)` keep it consistent with the parent (see
[01-data-model §4.3](01-data-model.md#43-zone-denormalised-everywhere-kept-honest-by-composite-fks)).

The 30 tables of v2 that are not in the MVP (chain, subzone, basement, gate, voucher, disputes, swaps, reporting
tables and others) are listed with their replacement in [08-deferred-tables](08-deferred-tables.md); they do not
appear below.

## 1. Facility, people and entitlements

```mermaid
erDiagram
    zone ||--|{ building : has
    zone ||--|{ slot_pool : configures
    building |o--o{ slot_pool : "TH1 pool of"
    building ||--|{ slot : contains
    slot_pool ||--|{ slot : groups

    app_user ||--o{ vehicle : owns
    app_user ||--o{ eligibility : holds
    asset ||--o{ eligibility : "grants"
    zone ||--o{ asset : contains
    building |o--o{ asset : "located in (NULL = low-rise)"
    app_user ||--o{ slot_holding : "holds usage right"
    slot ||--o{ slot_holding : "held by (TH1/TH2)"
    app_user ||--o{ staff_zone : "works for"
    zone ||--o{ staff_zone : staffed
    app_user ||--o{ refresh_token : has

    zone {
        uuid id PK
        text code UK "globally unique (one operator)"
        text timezone
    }
    building {
        uuid id PK
        uuid zone_id FK
        text subzone_code "nullable, replaces subzone"
        building_kind kind
    }
    slot_pool {
        uuid id PK
        uuid zone_id FK
        uuid building_id FK "TH1 only"
        slot_type slot_type
        open_scope max_open_scope
        timestamptz investor_consent_at "TH2 BR-02"
    }
    slot {
        uuid id PK
        uuid zone_id FK
        uuid building_id FK
        uuid pool_id FK
        slot_type slot_type "copy of pool type"
        text level_code "B2, G (replaces basement)"
        size_class size_class "S < M < L < XL"
    }
    app_user {
        uuid id PK
        text phone_e164 UK
        text password_hash "argon2id"
        user_role role
        text consent_text_version "with consented_at"
    }
    asset {
        uuid id PK
        uuid zone_id FK
        uuid building_id FK "nullable"
        asset_kind kind
    }
    eligibility {
        uuid id PK
        uuid user_id FK
        uuid asset_id FK
        uuid zone_id FK
        eligibility_role role
        tstzrange valid_during
        eligibility_status status
    }
    slot_holding {
        uuid id PK
        uuid slot_id FK
        uuid user_id FK
        holding_kind kind "owner or lessee"
        tstzrange held_during "EXCLUDE overlap"
    }
    vehicle {
        uuid id PK
        uuid user_id FK
        bytea plate_ciphertext "column-revoked"
        bytea plate_hash "HMAC"
        text plate_masked
        size_class size_class
    }
    staff_zone {
        uuid user_id PK,FK
        uuid zone_id PK,FK
    }
    refresh_token {
        uuid id PK
        uuid user_id FK
        uuid family_id
        bytea token_hash
    }
```

**Relationships.**
* **Zone → Building → Slot** is the facility tree from PRD §2. The subzone and the basement level are plain columns
  (`building.subzone_code`, `slot.level_code`), and the size class is an ordered enum, so BR-11 is
  `vehicle.size_class <= slot.size_class`. All links are `ON DELETE RESTRICT`: facilities are retired with
  `is_active = false`, never deleted, because bookings and the ledger point at them.
* **Slot pool** carries the open scope. A slot's type must equal its pool's type (composite FK
  `(pool_id, slot_type, zone_id)`), and the pool CHECK enforces the PRD §4 table (TH1 ≤ zone, TH2 ≤ chain with
  developer consent, TH3 = public).
* **Eligibility** is the M:N relationship between `app_user` and `asset`, carrying role and validity. An EXCLUDE
  constraint forbids two live entitlements for the same (user, asset, role) over overlapping time.
* **Slot holding** is the M:N-over-time relationship between `app_user` and `slot` (who may share a TH1/TH2
  slot). TH3 slots cannot have holders (CHECK on `slot_type`). A holding is closed (`voided_at`) and a new one opened,
  so the history stays.
* **Staff zone** is the M:N between staff users and zones (JWT `zone_ids`).
* User-owned children (`staff_zone`, `refresh_token`) cascade on user delete. Users are soft-deleted in practice, so
  the cascade only matters for test data.

## 2. Sharing, booking, agreement, ledger, money

```mermaid
erDiagram
    slot ||--o{ share_window : "shared in"
    app_user ||--o{ share_window : "owner"
    building ||--o{ parking_request : "requested at"
    app_user ||--o{ parking_request : requests
    parking_request |o--o{ booking : "results in"
    slot ||--o{ booking : reserves
    share_window |o--o{ booking : "TH1/TH2 only"
    app_user ||--o{ booking : "renter"
    vehicle ||--o{ booking : "parks"
    booking |o--o| booking : "relocated_from (W3)"
    booking ||--o| agreement : "covered by"
    zone_policy ||--o{ agreement : "pins prices + template"
    approval_request |o--o| agreement : "approves (BR-12)"
    app_user ||--o{ otp_challenge : "confirms with"
    zone ||--|| ledger_head : "chain tip"
    zone ||--o{ ledger_entry : "hash chain"
    booking ||--o{ payment : "paid by"

    share_window {
        uuid id PK
        uuid slot_id FK
        uuid owner_user_id FK
        tstzrange period
        tstzrange bookable_period "period minus buffers"
        open_scope open_scope "<= pool max"
        share_status status
    }
    booking {
        uuid id PK
        uuid zone_id FK
        uuid slot_id FK
        uuid share_window_id FK "NULL for TH3"
        uuid provider_user_id FK "= window owner"
        uuid renter_user_id FK
        uuid vehicle_id FK "owned by renter"
        tstzrange period "EXCLUDE overlap"
        eligibility_level eligibility_level
        bigint price_vnd
        booking_status status
        text idempotency_key UK
    }
    agreement {
        uuid id PK
        uuid booking_id FK,UK
        uuid zone_policy_id FK "prices + agreement_template_md"
        uuid approval_request_id FK
        bytea body_sha256
        agreement_status status
    }
    otp_challenge {
        uuid id PK
        uuid user_id FK
        uuid subject_id "agreement"
        bytea code_hash
        smallint attempts
    }
    ledger_head {
        uuid zone_id PK,FK
        bigint last_seq
        bytea last_hash
    }
    ledger_entry {
        uuid zone_id PK,FK
        bigint seq PK
        ledger_entry_type entry_type
        text subject_type "agreement, booking, payment"
        uuid subject_id
        jsonb payload
        bytea prev_hash
        bytea hash
    }
    payment {
        uuid id PK
        uuid booking_id FK
        bigint amount_vnd
        payment_status status
        text idempotency_key UK
    }
```

**Relationships.**
* **share_window → booking**: a TH1/TH2 booking references the window through `(share_window_id, slot_id,
  provider_user_id)`, so the slot and the provider are guaranteed to be those of the window. A TH3 booking has
  no window and no provider (CHECK + trigger).
* **booking → booking** (`relocated_from_booking_id`): the TH3 replacement created when an owner returns early
  points at the booking it replaces.
* **booking 1–0..1 agreement** (UNIQUE `booking_id`): only shared TH1/TH2 bookings have an agreement; TH3 visits
  are zone-operated receipts (PRD §7).
* **agreement → zone_policy**: pins the exact rule version used. The price table (`zone_policy.prices`) and the
  agreement text (`zone_policy.agreement_template_md`) live in the policy row, so a later policy change does not
  alter a signed agreement.
* **otp_challenge** is linked to a user only; `subject_id` points at the agreement without an FK (polymorphic by
  `purpose`).
* **ledger_entry** is deliberately *not* FK-linked to its subject (`subject_type`, `subject_id`). It is an
  immutable log that must outlive and describe any row; a polymorphic reference is the standard trade-off here.
  `ledger_head` holds the chain tip per zone and is the row lock that serialises appends.

## 3. Operations: LPR, approvals, platform, reporting

```mermaid
erDiagram
    zone ||--o{ lpr_event : "seen in"
    vehicle |o--o{ lpr_event : "matched"
    booking |o--o{ lpr_event : "matched"
    app_user |o--o{ lpr_event : "reviewed by"

    zone ||--o{ approval_request : "approval queue"
    zone ||--o{ zone_policy : "versions"
    app_user ||--o{ notification : receives
    zone ||--o{ outbox : "events"
    zone ||--o{ audit_log : "row changes"
    zone |o--o{ knowledge_chunk : "scoped to"
    building |o--o{ knowledge_chunk : "scoped to"
    parking_request }o--|| zone : "aggregated by"

    lpr_event {
        bigint id PK "identity, not partitioned"
        uuid zone_id FK
        text source_code "replaces lpr_source"
        text source_event_id "UNIQUE with zone_id + source_code"
        text gate_code "replaces gate"
        numeric ocr_confidence
        lpr_status status
    }
    approval_request {
        uuid id PK
        uuid zone_id FK
        approval_kind kind "agreement_over_threshold, early_return_escalation"
        uuid subject_id
        text thread_id "LangGraph resume"
        approval_status status
    }
    zone_policy {
        uuid id PK
        uuid zone_id FK
        integer version
        jsonb prices "object, checked by the rule engine"
        text agreement_template_md
        numeric ocr_review_threshold "default 0.800"
    }
    knowledge_chunk {
        uuid id PK
        uuid zone_id FK "nullable"
        uuid building_id FK "nullable"
        text doc_title
        text source_uri "UNIQUE with doc_version + ordinal"
        integer doc_version
        boolean is_active
    }
    kpi_daily_v {
        uuid zone_id
        date day
        bigint requests_total
        bigint matched
        bigint no_match
    }
```

`outbox`, `idempotency_keys` and `audit_log` have no business FKs beyond `zone_id`/`user_id` and are drawn only by
their `zone_id` link. `kpi_daily_v` is a view over `parking_request` and `zone` (not a table): it replaces the v2
table `kpi_daily` and applies its own row filter by role and zone.

**Relationships.**
* **lpr_event** is a plain table (no partitioning in the MVP). Its dedupe key is
  `(zone_id, source_code, source_event_id)` (BR-13 / AC-10a). Gate and source are text codes, and the OCR review
  threshold is read from `zone_policy.ocr_review_threshold`. Plates are stored as ciphertext, hash and mask; the MVP
  shows the mask only.
* **approval_request.subject_id** is polymorphic by `kind` (agreement over the threshold, early-return escalation).
  The reverse FK `agreement.approval_request_id` gives referential integrity where it matters.
* **knowledge_chunk** carries its document fields (`doc_title`, `source_uri`, `doc_version`) itself; the v2 table
  `knowledge_doc` is gone. `zone_id` and `building_id` are real FKs.
* Removed with their tables: LPR sessions and overstay, plate-access log, disputes, swaps, vacancy forecast,
  occupancy, reconciliation, privacy requests, retention rules and workflow runs. See
  [08-deferred-tables](08-deferred-tables.md).

## 4. ON DELETE policy (summary)

| Policy | Where | Why |
|--------|-------|-----|
| `RESTRICT` (default for business FKs) | facility tree, users referenced by history, bookings, agreements, ledger, approvals | Business history must never disappear through a cascade. Retire with `is_active` / soft delete. |
| `CASCADE` | user-private auxiliaries (`refresh_token`, `otp_challenge`, `notification`, `staff_zone`) | Children have no meaning without the parent. |
| `SET NULL` | `lpr_event.matched_vehicle_id/matched_booking_id`, `zone_policy.created_by` | Optional context links on logs; losing the link must not block deleting test data. |

`lpr_event.reviewed_by` stays `RESTRICT` because a CHECK requires it on reviewed rows (D-27).
