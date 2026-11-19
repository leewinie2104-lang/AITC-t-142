# 03 — Data dictionary

> Generated from the catalog of a database built with [sql/schema.sql](sql/schema.sql) v4 (PostgreSQL 17.10, pgvector column absent in that build; the column `knowledge_chunk.embedding vector(1024)` is not counted below),
> so types, nullability, defaults and constraints match the DDL exactly: **23 tables, 281 columns** (plus the view `kpi_daily_v`). Meanings are hand-written.
> Regenerate after schema changes rather than editing the type columns by hand.

Conventions: all tables live in schema `app`. `RLS` = row-level security enabled. Times are `timestamptz` (UTC);
ranges are half-open `[start, end)`. Money is `bigint` VND. Enum values are listed in [sql/schema.sql §1](sql/schema.sql).

## Contents

- **Facility & pools (M2, M3)**: [`zone`](#zone) · [`building`](#building) · [`slot_pool`](#slot_pool) · [`slot`](#slot)
- **Identity (M1)**: [`app_user`](#app_user) · [`vehicle`](#vehicle)
- **Eligibility (M1)**: [`asset`](#asset) · [`eligibility`](#eligibility) · [`slot_holding`](#slot_holding)
- **Policy & configuration (M3)**: [`zone_policy`](#zone_policy)
- **Sharing & booking (M4, M5)**: [`share_window`](#share_window) · [`parking_request`](#parking_request) · [`booking`](#booking) · [`recovery_case`](#recovery_case)
- **Agreement & confirmation evidence (M6)**: [`agreement`](#agreement) · [`consent_record`](#consent_record)
- **Payment (M7)**: [`payment`](#payment)
- **Access / LPR (M8)**: [`lpr_event`](#lpr_event)
- **Approvals (M12)**: [`approval_request`](#approval_request)
- **Notifications (M13)**: [`notification`](#notification)
- **Agent & AI audit (M14)**: [`agent_thread`](#agent_thread) · [`ai_decision_log`](#ai_decision_log)
- **Knowledge base (W7)**: [`knowledge_chunk`](#knowledge_chunk)
- **Views**: [`kpi_daily_v`](#kpi_daily_v)
- **Removed in v4**: 8 tables of the v3 design (`staff_zone`, `refresh_token`, `otp_challenge`, `ledger_head`, `ledger_entry`, `outbox`, `idempotency_keys`, `audit_log`) are not in this dictionary; see [ADR-0011](../10-adr/ADR-0011-mvp-simplifications.md), [D-32](07-db-decision-log.md#d-32) and [08-deferred-tables.md](08-deferred-tables.md).
- **Removed in v3**: 30 tables of the v2 design (`chain`, `subzone`, `basement`, `voucher`, `dispute_*`, `swap_*`, `kpi_daily` …) are not in this dictionary either; see [08-deferred-tables.md](08-deferred-tables.md) for the list and how to bring each back.

## Facility & pools (M2, M3)

### zone

Khu đô thị. Unit of data ownership, RLS, pricing, approvals (BR-18). `code` is globally unique (one operator; the `chain` table is not in the MVP).  
RLS: **no**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `code` | text | no |  | Business code, unique within its parent. |
| `name` | text | no |  | Display name. |
| `timezone` | text | no | 'Asia/Ho_Chi_Minh'::text | IANA zone for local business days (reconciliation, expiry on day D). |
| `is_active` | boolean | no | true | Soft retire flag; rows stay referenced by history. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Last update (trigger `set_updated_at`). |

<details><summary>Constraints and indexes</summary>

- CHECK `zone_code_check`: `CHECK (code ~ '^[A-Z0-9_-]{1,32}$'::text)`
- CHECK `zone_name_check`: `CHECK (btrim(name) <> ''::text)`
- PK `zone_pkey`: `PRIMARY KEY (id)`
- UNIQUE `zone_code_key`: `UNIQUE (code)`

</details>

### building

Tòa / cụm shophouse / bãi công cộng. A public lot is a building of kind `public_lot`. The optional phân khu is a plain code, not a table.  
RLS: **yes** (policies: `manage_zone`, `read_authenticated`)

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `subzone_code` | text | yes |  | Optional phân khu code (`^[A-Z0-9_-]{1,32}$`); replaces the removed `subzone` table. |
| `code` | text | no |  | Business code, unique within its parent. |
| `name` | text | no |  | Display name. |
| `kind` | app.building_kind | no |  | residential_tower · lowrise_cluster · public_lot. |
| `is_active` | boolean | no | true | Soft retire flag; rows stay referenced by history. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Last update (trigger `set_updated_at`). |

<details><summary>Constraints and indexes</summary>

- CHECK `building_name_check`: `CHECK (btrim(name) <> ''::text)`
- CHECK `building_subzone_code_check`: `CHECK (subzone_code ~ '^[A-Z0-9_-]{1,32}$'::text)`
- FK `building_zone_id_fkey`: `FOREIGN KEY (zone_id) REFERENCES app.zone(id) ON DELETE RESTRICT`
- PK `building_pkey`: `PRIMARY KEY (id)`
- UNIQUE `building_id_zone_id_key`: `UNIQUE (id, zone_id)`
- UNIQUE `building_zone_id_code_key`: `UNIQUE (zone_id, code)`

</details>

### slot_pool

Pool of slots of one type with its open scope (FR-26). TH1 per building, TH2/TH3 per zone.  
RLS: **yes** (policies: `chain_operator_manage`, `manage_zone`, `read_authenticated`)

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `building_id` | uuid | yes |  | Set for TH1 pools; NULL for zone-wide TH2/TH3 pools. → `building`. |
| `slot_type` | app.slot_type | no |  | Value from the fixed set of its type / CHECK (see constraints). |
| `max_open_scope` | app.open_scope | no |  | Widest scope allowed by the rules (TH1 ≤ zone, TH2 ≤ chain, TH3 = public). |
| `investor_consent_at` | timestamp with time zone | yes |  | BR-02 one-time developer consent; required for TH2. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Last update (trigger `set_updated_at`). |

<details><summary>Constraints and indexes</summary>

- CHECK `slot_pool_scope_by_type`: `CHECK (((slot_type = 'TH1'::app.slot_type) AND (building_id IS NOT NULL) AND (max_open_scope = ANY (ARRAY['building'::app.open_scope, 'zone'::app.open_scope]))) OR ((slot_type = 'TH2'::app.slot_type) AND (max_open_scope = ANY (ARRAY['zone'::app.open_scope, 'chain'::app.open_scope])) AND (investor_consent_at IS NOT NULL)) OR ((slot_type = 'TH3'::app.slot_type) AND (max_open_scope = 'public'::app.open_scope)))`
- FK `slot_pool_building_id_zone_id_fkey`: `FOREIGN KEY (building_id, zone_id) REFERENCES app.building(id, zone_id) ON DELETE RESTRICT`
- FK `slot_pool_zone_id_fkey`: `FOREIGN KEY (zone_id) REFERENCES app.zone(id) ON DELETE RESTRICT`
- PK `slot_pool_pkey`: `PRIMARY KEY (id)`
- UNIQUE `slot_pool_id_slot_type_zone_id_key`: `UNIQUE (id, slot_type, zone_id)`
- UNIQUE `slot_pool_zone_id_building_id_slot_type_key`: `UNIQUE NULLS NOT DISTINCT (zone_id, building_id, slot_type)`

</details>

### slot

Ô đỗ. Type TH1/TH2/TH3 is denormalised from the pool and kept consistent by composite FK. `operational_status` says whether the slot can be booked at all.  
RLS: **yes** (policies: `manage_zone`, `read_authenticated`)

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `building_id` | uuid | no |  | Optional building scope; NULL = zone-wide. |
| `pool_id` | uuid | no |  | Pool that defines type and scope. → `slot_pool`. |
| `slot_type` | app.slot_type | no |  | TH1 / TH2 / TH3 (copy of the pool's type). |
| `level_code` | text | no |  | Parking level of the slot, e.g. `B2`, `G` (`^[A-Z0-9]{1,8}$`); replaces the removed `basement` table. |
| `code` | text | no |  | Business code, unique within its parent. |
| `size_class` | app.size_class | no |  | Largest vehicle class the slot takes: S < M < L < XL (ordered enum). BR-11: `vehicle.size_class <= slot.size_class`. |
| `operational_status` | app.slot_operational_status | no | 'active'::slot_operational_status | `active` (bookable) · `maintenance` · `blocked`. `booking_validate` refuses any slot that is not `active`. Replaces `is_active`. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Last update (trigger `set_updated_at`). |

<details><summary>Constraints and indexes</summary>

- CHECK `slot_level_code_check`: `CHECK (level_code ~ '^[A-Z0-9]{1,8}$'::text)`
- FK `slot_building_id_zone_id_fkey`: `FOREIGN KEY (building_id, zone_id) REFERENCES app.building(id, zone_id) ON DELETE RESTRICT`
- FK `slot_pool_id_slot_type_zone_id_fkey`: `FOREIGN KEY (pool_id, slot_type, zone_id) REFERENCES app.slot_pool(id, slot_type, zone_id) ON DELETE RESTRICT`
- PK `slot_pkey`: `PRIMARY KEY (id)`
- UNIQUE `slot_building_id_code_key`: `UNIQUE (building_id, code)`
- UNIQUE `slot_id_zone_id_key`: `UNIQUE (id, zone_id)`
- UNIQUE `slot_id_zone_id_slot_type_key`: `UNIQUE (id, zone_id, slot_type)`
- INDEX: `btree (building_id)`
- INDEX: `btree (pool_id)`
- INDEX: `btree (zone_id, slot_type) WHERE operational_status = 'active'::app.slot_operational_status`

</details>

## Identity (M1)

### app_user

One account for the whole chain (FR-23). Soft-deleted. A BQL member or guard is tied to one zone through `staff_zone_id`. Consent for plate/photo processing is a row in `consent_record`, not a column here (A-03, BR-09).  
RLS: **yes** (policies: `auth_and_system`, `self`, `zone_manager_read`)

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `full_name` | text | no |  | PII. Pseudonymised before any LLM call (BR-14). |
| `phone_e164` | text | yes |  | Login id, E.164. Unique among non-deleted users. |
| `email` | text | yes |  | PII, optional; unique case-insensitively among live users. |
| `password_hash` | text | no |  | argon2id hash only (CHECK). |
| `role` | app.user_role | no | 'resident'::user_role | Application role (ADR-0006). Eligibility is separate and never in the token. |
| `status` | app.user_status | no | 'active'::user_status | Value from the fixed set of its type / CHECK (see constraints). |
| `failed_logins` | smallint | no | 0 | Counter for temporary lock. |
| `locked_until` | timestamp with time zone | yes |  | Temporary lock after repeated failed logins. |
| `deleted_at` | timestamp with time zone | yes |  | Soft delete marker; equals status = deleted. |
| `staff_zone_id` | uuid | yes |  | The one zone a BQL member (`zone_manager`) or guard works for; source of the JWT claim `zone_ids` = `{staff_zone_id}`. NULL for residents, renters and the chain operator. CHECK `app_user_staff_zone_role`: only `guard` / `zone_manager` may set it. Replaces the `staff_zone` junction (ADR-0011). |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Last update (trigger `set_updated_at`). |

<details><summary>Constraints and indexes</summary>

- CHECK `app_user_deleted_consistent`: `CHECK ((status = 'deleted'::app.user_status) = (deleted_at IS NOT NULL))`
- CHECK `app_user_email_check`: `CHECK ((email IS NULL) OR (email ~ '^[^@\s]+@[^@\s]+$'::text))`
- CHECK `app_user_failed_logins_check`: `CHECK (failed_logins >= 0)`
- CHECK `app_user_full_name_check`: `CHECK ((btrim(full_name) <> ''::text) AND (length(full_name) <= 200))`
- CHECK `app_user_password_hash_check`: `CHECK (password_hash ~~ '$argon2id$%'::text)`
- CHECK `app_user_phone_e164_check`: `CHECK (phone_e164 ~ '^\+[1-9][0-9]{7,14}$'::text)`
- CHECK `app_user_phone_required`: `CHECK ((status = 'deleted'::app.user_status) OR (phone_e164 IS NOT NULL))`
- CHECK `app_user_staff_zone_role`: `CHECK ((staff_zone_id IS NULL) OR (role = ANY (ARRAY['guard'::app.user_role, 'zone_manager'::app.user_role])))`
- FK `app_user_staff_zone_id_fkey`: `FOREIGN KEY (staff_zone_id) REFERENCES app.zone(id) ON DELETE RESTRICT`
- PK `app_user_pkey`: `PRIMARY KEY (id)`
- UNIQUE INDEX: `btree (lower(email)) WHERE (deleted_at IS NULL) AND (email IS NOT NULL)`
- UNIQUE INDEX: `btree (phone_e164) WHERE deleted_at IS NULL`
- INDEX: `btree (staff_zone_id) WHERE staff_zone_id IS NOT NULL`

</details>

### vehicle

A user's vehicle. Plate stored encrypted + keyed hash + masked; the ciphertext is column-revoked from the app role (MVP shows masked plates only).  
RLS: **yes** (policies: `own_or_system`, `zone_staff_read`)

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `user_id` | uuid | no |  | References `app_user`. |
| `plate_ciphertext` | bytea | yes |  | Encrypted plate. Not selectable by the app role (column grant). |
| `plate_key_version` | smallint | no | 1 | Key version for rotation. |
| `plate_hash` | bytea | yes |  | HMAC-SHA256 of the normalised plate with a secret pepper; LPR matching. |
| `plate_masked` | text | no |  | Display form, e.g. 30A-•••.45. |
| `size_class` | app.size_class | no |  | Vehicle size class (S < M < L < XL); must be `<=` the slot's class to book (BR-11). |
| `is_active` | boolean | no | true | Soft retire flag; rows stay referenced by history. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Last update (trigger `set_updated_at`). |

<details><summary>Constraints and indexes</summary>

- CHECK `vehicle_active_has_plate`: `CHECK ((NOT is_active) OR (plate_ciphertext IS NOT NULL))`
- CHECK `vehicle_plate_hash_check`: `CHECK (length(plate_hash) = 32)`
- CHECK `vehicle_plate_key_version_check`: `CHECK (plate_key_version > 0)`
- CHECK `vehicle_plate_masked_check`: `CHECK (btrim(plate_masked) <> ''::text)`
- CHECK `vehicle_plate_pair`: `CHECK ((plate_ciphertext IS NULL) = (plate_hash IS NULL))`
- FK `vehicle_user_id_fkey`: `FOREIGN KEY (user_id) REFERENCES app.app_user(id) ON DELETE RESTRICT`
- PK `vehicle_pkey`: `PRIMARY KEY (id)`
- UNIQUE `vehicle_id_user_id_key`: `UNIQUE (id, user_id)`
- INDEX: `btree (plate_hash) WHERE is_active`
- UNIQUE INDEX: `btree (user_id, plate_hash) WHERE is_active`

</details>

## Eligibility (M1)

### asset

Property that confers eligibility (apartment, shophouse, office…). Unit code never leaves its zone (BR-17).  
RLS: **yes** (policies: `holder_read`, `zone_staff`)

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `building_id` | uuid | yes |  | NULL for a low-rise shophouse outside any tower (A-10 → L2). → `building`. |
| `kind` | app.asset_kind | no |  | Value from the fixed set of its type / CHECK (see constraints). |
| `code` | text | no |  | Unit number. Visible only inside its zone. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Last update (trigger `set_updated_at`). |

<details><summary>Constraints and indexes</summary>

- FK `asset_building_id_zone_id_fkey`: `FOREIGN KEY (building_id, zone_id) REFERENCES app.building(id, zone_id) ON DELETE RESTRICT`
- FK `asset_zone_id_fkey`: `FOREIGN KEY (zone_id) REFERENCES app.zone(id) ON DELETE RESTRICT`
- PK `asset_pkey`: `PRIMARY KEY (id)`
- UNIQUE `asset_id_zone_id_key`: `UNIQUE (id, zone_id)`
- UNIQUE `asset_zone_id_code_key`: `UNIQUE (zone_id, code)`
- INDEX: `btree (building_id) WHERE building_id IS NOT NULL`

</details>

### eligibility

Tư cách = (asset, role, validity), verified by the BQL of the asset's zone. Source of L1–L4.  
RLS: **yes** (policies: `holder_claim`, `holder_read`, `zone_staff`)

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `user_id` | uuid | no |  | References `app_user`. |
| `asset_id` | uuid | no |  | References `asset`. |
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `role` | app.eligibility_role | no |  | owner · tenant · authorized · employee. |
| `valid_during` | tstzrange | no |  | Validity `[from, until)`; open upper = no expiry. Checked at use time (BR-16). |
| `status` | app.eligibility_status | no | 'pending'::eligibility_status | pending → verified → revoked/expired. |
| `verified_by` | uuid | yes |  | BQL who verified (required when verified). → `app_user`. |
| `verified_at` | timestamp with time zone | yes |  | Time of the event the name describes (UTC); NULL = not happened. |
| `revoked_at` | timestamp with time zone | yes |  | Time of the event the name describes (UTC); NULL = not happened. |
| `revoke_reason` | text | yes |  | As named. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Last update (trigger `set_updated_at`). |

<details><summary>Constraints and indexes</summary>

- CHECK `eligibility_check`: `CHECK ((status <> 'verified'::app.eligibility_status) OR ((verified_by IS NOT NULL) AND (verified_at IS NOT NULL)))`
- CHECK `eligibility_check1`: `CHECK ((status <> 'revoked'::app.eligibility_status) OR (revoked_at IS NOT NULL))`
- CHECK `eligibility_valid_during_check`: `CHECK ((NOT isempty(valid_during)) AND (NOT lower_inf(valid_during)))`
- FK `eligibility_asset_id_zone_id_fkey`: `FOREIGN KEY (asset_id, zone_id) REFERENCES app.asset(id, zone_id) ON DELETE RESTRICT`
- FK `eligibility_user_id_fkey`: `FOREIGN KEY (user_id) REFERENCES app.app_user(id) ON DELETE RESTRICT`
- FK `eligibility_verified_by_fkey`: `FOREIGN KEY (verified_by) REFERENCES app.app_user(id) ON DELETE RESTRICT`
- PK `eligibility_pkey`: `PRIMARY KEY (id)`
- EXCLUDE `eligibility_no_overlap`: `EXCLUDE USING gist (user_id WITH =, asset_id WITH =, role WITH =, valid_during WITH &&) WHERE status = ANY (ARRAY['pending'::app.eligibility_status, 'verified'::app.eligibility_status])`
- INDEX: `btree (asset_id)`
- INDEX: `btree (upper(valid_during)) WHERE (status = 'verified'::app.eligibility_status) AND (NOT upper_inf(valid_during))`
- INDEX: `btree (zone_id, status)`
- INDEX: `gist (user_id, valid_during) WHERE status = 'verified'::app.eligibility_status`

</details>

### slot_holding

Who holds the usage right of a TH1/TH2 slot over time (owner or lessee). Needed to share.  
RLS: **yes** (policies: `holder_read`, `zone_staff`)

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `slot_id` | uuid | no |  | References `slot`. |
| `slot_type` | app.slot_type | no |  | Value from the fixed set of its type / CHECK (see constraints). |
| `user_id` | uuid | no |  | References `app_user`. |
| `kind` | app.holding_kind | no |  | owner (TH1) · lessee (TH2). |
| `held_during` | tstzrange | no |  | Holding period; no overlap per slot (EXCLUDE). |
| `voided_at` | timestamp with time zone | yes |  | Set when the holding was entered by mistake; voided rows stop blocking the slot. |
| `void_reason` | text | yes |  | Mandatory reason when voided. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |

<details><summary>Constraints and indexes</summary>

- CHECK `slot_holding_check`: `CHECK ((voided_at IS NULL) = (void_reason IS NULL))`
- CHECK `slot_holding_held_during_check`: `CHECK ((NOT isempty(held_during)) AND (NOT lower_inf(held_during)))`
- CHECK `slot_holding_type_kind`: `CHECK (((slot_type = 'TH1'::app.slot_type) AND (kind = 'owner'::app.holding_kind)) OR ((slot_type = 'TH2'::app.slot_type) AND (kind = 'lessee'::app.holding_kind)))`
- CHECK `slot_holding_void_reason_check`: `CHECK ((void_reason IS NULL) OR (btrim(void_reason) <> ''::text))`
- FK `slot_holding_slot_id_zone_id_slot_type_fkey`: `FOREIGN KEY (slot_id, zone_id, slot_type) REFERENCES app.slot(id, zone_id, slot_type) ON DELETE RESTRICT`
- FK `slot_holding_user_id_fkey`: `FOREIGN KEY (user_id) REFERENCES app.app_user(id) ON DELETE RESTRICT`
- PK `slot_holding_pkey`: `PRIMARY KEY (id)`
- EXCLUDE `slot_holding_no_overlap`: `EXCLUDE USING gist (slot_id WITH =, held_during WITH &&) WHERE voided_at IS NULL`
- INDEX: `btree (user_id)`

</details>

## Policy & configuration (M3)

### zone_policy

Versioned zone rules: buffers, thresholds, TTLs, OCR review threshold, price table and agreement template. Agreements pin the version used.  
RLS: **yes** (policies: `manage_zone`, `read_authenticated`)

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `version` | integer | no |  | Monotonic per zone; a change is a new row. |
| `effective_from` | timestamp with time zone | no |  | Start of validity of this version. |
| `buffer_before` | interval | no | '00:15:00'::interval | Buffer at the start of a share window (FR-06). |
| `buffer_after` | interval | no | '00:30:00'::interval | Buffer before the owner returns (BR-07). |
| `approval_threshold_vnd` | bigint | no | 1000000 | Above this, an agreement needs BQL approval (BR-12). |
| `hold_ttl` | interval | no | '00:10:00'::interval | Life of a temporary hold. |
| `agreement_confirm_ttl` | interval | no | '00:30:00'::interval | Time both parties have to confirm. |
| `eligibility_grace_max` | interval | yes | '7 days'::interval | BR-16 maximum carry-over of a running booking after expiry (TBD; NULL = until booking end). |
| `early_return_cost_rule` | text | no | 'renter_pays_th3_relocated'::text | Who pays when the owner returns early; only renter_pays_th3_relocated is implemented (D-09). |
| `ocr_review_threshold` | numeric(4,3) | no | 0.800 | Plates read below this OCR confidence go to manual review (0–1, default 0.800; D-21). |
| `prices` | jsonb | no |  | Price table as a JSON object, shape `{"TH1":{"L1":{"hour":10000,"day":50000},…},…}` (slot type → eligibility level → unit prices, VND). Validated by the rule engine (Pydantic), not by SQL beyond `jsonb_typeof = 'object'`. |
| `agreement_template_md` | text | no |  | Markdown agreement template of this policy version (non-blank); versioned with the policy, so an agreement that pins `zone_policy_id` also pins its text. |
| `created_by` | uuid | yes |  | References `app_user`. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |

<details><summary>Constraints and indexes</summary>

- CHECK `zone_policy_agreement_confirm_ttl_check`: `CHECK (agreement_confirm_ttl > '00:00:00'::interval)`
- CHECK `zone_policy_agreement_template_md_check`: `CHECK (btrim(agreement_template_md) <> ''::text)`
- CHECK `zone_policy_approval_threshold_vnd_check`: `CHECK (approval_threshold_vnd >= 0)`
- CHECK `zone_policy_buffer_after_check`: `CHECK (buffer_after >= '00:00:00'::interval)`
- CHECK `zone_policy_buffer_before_check`: `CHECK (buffer_before >= '00:00:00'::interval)`
- CHECK `zone_policy_early_return_cost_rule_check`: `CHECK (early_return_cost_rule = 'renter_pays_th3_relocated'::text)`
- CHECK `zone_policy_eligibility_grace_max_check`: `CHECK ((eligibility_grace_max IS NULL) OR (eligibility_grace_max >= '00:00:00'::interval))`
- CHECK `zone_policy_hold_ttl_check`: `CHECK (hold_ttl > '00:00:00'::interval)`
- CHECK `zone_policy_ocr_review_threshold_check`: `CHECK ((ocr_review_threshold >= (0)::numeric) AND (ocr_review_threshold <= (1)::numeric))`
- CHECK `zone_policy_prices_check`: `CHECK (jsonb_typeof(prices) = 'object'::text)`
- CHECK `zone_policy_version_check`: `CHECK (version > 0)`
- FK `zone_policy_created_by_fkey`: `FOREIGN KEY (created_by) REFERENCES app.app_user(id) ON DELETE SET NULL`
- FK `zone_policy_zone_id_fkey`: `FOREIGN KEY (zone_id) REFERENCES app.zone(id) ON DELETE RESTRICT`
- PK `zone_policy_pkey`: `PRIMARY KEY (id)`
- UNIQUE `zone_policy_id_zone_id_key`: `UNIQUE (id, zone_id)`
- UNIQUE `zone_policy_zone_id_version_key`: `UNIQUE (zone_id, version)`
- INDEX: `btree (zone_id, effective_from DESC)`

</details>

## Sharing & booking (M4, M5)

### share_window

Owner publishes an away window; `bookable_period` = window minus buffers (FR-05/06).  
RLS: **yes** (policies: `open_read`, `owner`, `zone_staff`)

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `slot_id` | uuid | no |  | References `slot`. |
| `owner_user_id` | uuid | no |  | References `app_user`. |
| `period` | tstzrange | no |  | Window the owner is away. |
| `bookable_period` | tstzrange | no |  | Period minus buffers; bookings must lie inside it. |
| `open_scope` | app.open_scope | no |  | Owner-chosen scope ≤ pool max (AC-23). |
| `status` | app.share_status | no | 'open'::share_status | Value from the fixed set of its type / CHECK (see constraints). |
| `returned_at` | timestamp with time zone | yes |  | Early return time (W3). |
| `idempotency_key` | text | no |  | Replay guard for the publish step (check d). |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Last update (trigger `set_updated_at`). |

<details><summary>Constraints and indexes</summary>

- CHECK `share_window_bookable_period_check`: `CHECK (app.is_finite_range(bookable_period))`
- CHECK `share_window_check`: `CHECK (period @> bookable_period)`
- CHECK `share_window_check1`: `CHECK ((status = 'closed_early'::app.share_status) = (returned_at IS NOT NULL))`
- CHECK `share_window_open_scope_check`: `CHECK (open_scope <> 'public'::app.open_scope)`
- CHECK `share_window_period_check`: `CHECK (app.is_finite_range(period))`
- FK `share_window_owner_user_id_fkey`: `FOREIGN KEY (owner_user_id) REFERENCES app.app_user(id) ON DELETE RESTRICT`
- FK `share_window_slot_id_zone_id_fkey`: `FOREIGN KEY (slot_id, zone_id) REFERENCES app.slot(id, zone_id) ON DELETE RESTRICT`
- PK `share_window_pkey`: `PRIMARY KEY (id)`
- UNIQUE `share_window_id_slot_id_owner_user_id_key`: `UNIQUE (id, slot_id, owner_user_id)`
- UNIQUE `share_window_idempotency_key_key`: `UNIQUE (idempotency_key)`
- EXCLUDE `share_window_no_overlap`: `EXCLUDE USING gist (slot_id WITH =, period WITH &&) WHERE status = 'open'::app.share_status`
- INDEX: `btree (owner_user_id, lower(period) DESC)`
- INDEX: `gist (zone_id, bookable_period) WHERE status = 'open'::app.share_status`

</details>

### parking_request

Every request with its derived level and outcome, including blocked ones (KPI, AC-03).  
RLS: **yes** (policies: `requester`, `zone_staff`)

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `building_id` | uuid | no |  | References `building`. |
| `requester_user_id` | uuid | no |  | References `app_user`. |
| `vehicle_id` | uuid | no |  | References `vehicle`. |
| `requested_period` | tstzrange | no |  | Requested time range; at most 31 days. |
| `computed_level` | app.eligibility_level | no |  | Level derived at request time (L1–L4). |
| `outcome` | app.request_outcome | no |  | matched · redirected_th3 · redirected_public · blocked · no_match. |
| `block_reason` | text | yes |  | Rule that blocked it (BR-xx), required iff blocked. |
| `channel` | text | no | 'app'::text | Value from the fixed set of its type / CHECK (see constraints). |
| `idempotency_key` | text | no |  | Caller-supplied key (`thread_id:step`); replays hit the UNIQUE constraint. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |

<details><summary>Constraints and indexes</summary>

- CHECK `parking_request_block_reason_check`: `CHECK (block_reason ~ '^BR-[0-9]{2}$'::text)`
- CHECK `parking_request_channel_check`: `CHECK (channel = ANY (ARRAY['app'::text, 'chat'::text]))`
- CHECK `parking_request_check`: `CHECK ((outcome = 'blocked'::app.request_outcome) = (block_reason IS NOT NULL))`
- CHECK `parking_request_requested_period_check`: `CHECK (app.is_finite_range(requested_period) AND ((upper(requested_period) - lower(requested_period)) <= '31 days'::interval))`
- FK `parking_request_building_id_zone_id_fkey`: `FOREIGN KEY (building_id, zone_id) REFERENCES app.building(id, zone_id) ON DELETE RESTRICT`
- FK `parking_request_requester_user_id_fkey`: `FOREIGN KEY (requester_user_id) REFERENCES app.app_user(id) ON DELETE RESTRICT`
- FK `parking_request_vehicle_id_requester_user_id_fkey`: `FOREIGN KEY (vehicle_id, requester_user_id) REFERENCES app.vehicle(id, user_id) ON DELETE RESTRICT`
- PK `parking_request_pkey`: `PRIMARY KEY (id)`
- UNIQUE `parking_request_idempotency_key_key`: `UNIQUE (idempotency_key)`
- INDEX: `btree (requester_user_id, created_at DESC)`
- INDEX: `btree (zone_id, created_at, outcome)`

</details>

### booking

A reservation of a slot for a period. EXCLUDE constraint makes double booking impossible. `checked_in_at` / `checked_out_at` record the physical stay (set by N1 from a matched `lpr_event`).  
RLS: **yes** (policies: `parties_read`, `zone_staff`)

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `ref_no` | bigint | no | identity | Human-readable number shown in the UI (GD-/TC-/HD- prefixes). |
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `slot_id` | uuid | no |  | References `slot`. |
| `request_id` | uuid | yes |  | References `parking_request`. |
| `share_window_id` | uuid | yes |  | Window used (TH1/TH2); NULL for TH3. → `share_window`. |
| `provider_user_id` | uuid | yes |  | Slot holder (= window owner, by composite FK). |
| `renter_user_id` | uuid | no |  | References `app_user`. |
| `vehicle_id` | uuid | no |  | References `vehicle`. |
| `period` | tstzrange | no |  | Reserved period `[start, end)`. |
| `eligibility_level` | app.eligibility_level | no |  | Renter level at the slot; re-derived and checked by trigger. |
| `price_vnd` | bigint | no |  | Price from the rule engine, integer VND. |
| `status` | app.booking_status | no | 'held'::booking_status | held → pending_agreement → pending_approval → confirmed → completed; or relocated/cancelled/expired/rejected. |
| `hold_expires_at` | timestamp with time zone | yes |  | Required while held. |
| `checked_in_at` | timestamp with time zone | yes |  | When the vehicle entered, set by N1 from an `lpr_event` whose `matched_booking_id` is this booking. NULL = not arrived yet. A separate `parking_session` table returns with W4 overstay. |
| `checked_out_at` | timestamp with time zone | yes |  | When the vehicle left (same source). Only set after `checked_in_at` and not earlier than it (CHECK `booking_check_times`). |
| `relocated_from_booking_id` | uuid | yes |  | Original booking when this is a TH3 replacement after early return. → `booking`. |
| `idempotency_key` | text | no |  | Caller-supplied key (`thread_id:step`); replays hit the UNIQUE constraint. |
| `version` | integer | no | 1 | Optimistic lock for user-driven edits. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Last update (trigger `set_updated_at`). |

<details><summary>Constraints and indexes</summary>

- CHECK `booking_check`: `CHECK ((share_window_id IS NULL) = (provider_user_id IS NULL))`
- CHECK `booking_check1`: `CHECK ((provider_user_id IS NULL) OR (provider_user_id <> renter_user_id))`
- CHECK `booking_check2`: `CHECK ((status <> 'held'::app.booking_status) OR (hold_expires_at IS NOT NULL))`
- CHECK `booking_check_times`: `CHECK ((checked_out_at IS NULL) OR ((checked_in_at IS NOT NULL) AND (checked_out_at >= checked_in_at)))`
- CHECK `booking_period_check`: `CHECK (app.is_finite_range(period))`
- CHECK `booking_price_vnd_check`: `CHECK (price_vnd >= 0)`
- FK `booking_relocated_from_booking_id_fkey`: `FOREIGN KEY (relocated_from_booking_id) REFERENCES app.booking(id) ON DELETE RESTRICT`
- FK `booking_renter_user_id_fkey`: `FOREIGN KEY (renter_user_id) REFERENCES app.app_user(id) ON DELETE RESTRICT`
- FK `booking_request_id_fkey`: `FOREIGN KEY (request_id) REFERENCES app.parking_request(id) ON DELETE RESTRICT`
- FK `booking_share_window_id_slot_id_provider_user_id_fkey`: `FOREIGN KEY (share_window_id, slot_id, provider_user_id) REFERENCES app.share_window(id, slot_id, owner_user_id) ON DELETE RESTRICT`
- FK `booking_slot_id_zone_id_fkey`: `FOREIGN KEY (slot_id, zone_id) REFERENCES app.slot(id, zone_id) ON DELETE RESTRICT`
- FK `booking_vehicle_id_renter_user_id_fkey`: `FOREIGN KEY (vehicle_id, renter_user_id) REFERENCES app.vehicle(id, user_id) ON DELETE RESTRICT`
- PK `booking_pkey`: `PRIMARY KEY (id)`
- UNIQUE `booking_id_zone_id_key`: `UNIQUE (id, zone_id)`
- UNIQUE `booking_idempotency_key_key`: `UNIQUE (idempotency_key)`
- UNIQUE `booking_ref_no_key`: `UNIQUE (ref_no)`
- EXCLUDE `booking_no_overlap`: `EXCLUDE USING gist (slot_id WITH =, period WITH &&) WHERE status = ANY (ARRAY['held'::app.booking_status, 'pending_agreement'::app.booking_status, 'pending_approval'::app.booking_status, 'confirmed'::app.booking_status])`
- INDEX: `btree (hold_expires_at) WHERE status = 'held'::app.booking_status`
- INDEX: `btree (provider_user_id, lower(period) DESC) WHERE provider_user_id IS NOT NULL`
- INDEX: `btree (relocated_from_booking_id) WHERE relocated_from_booking_id IS NOT NULL`
- INDEX: `btree (renter_user_id, lower(period) DESC)`
- INDEX: `btree (request_id) WHERE request_id IS NOT NULL`
- INDEX: `btree (share_window_id) WHERE share_window_id IS NOT NULL`
- INDEX: `btree (vehicle_id)`
- INDEX: `btree (zone_id, upper(period)) WHERE status = 'confirmed'::app.booking_status`

</details>

### recovery_case

W3 (owner returns early, Ưu tiên 2): the case that finds the renter another slot. The rule engine fills `options` (candidate slots and prices); the LLM only words the proposal (BR-14). At most one open case per booking. New in v4.  
RLS: **yes** (policies: `parties_read`, `zone_staff`)

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7). |
| `zone_id` | uuid | no |  | Zone of the booking; drives RLS. Composite FKs keep every linked row in the same zone. |
| `booking_id` | uuid | no |  | The booking hit by the early return. → `booking` (with `zone_id`). |
| `trigger` | app.recovery_trigger | no | 'owner_early_return'::recovery_trigger | What opened the case; only `owner_early_return` in the MVP. |
| `new_return_at` | timestamp with time zone | no |  | The owner's new, earlier return time. |
| `options` | jsonb | no | '[]'::jsonb | JSON array of candidate slots and prices computed by the rule engine; `[]` until computed. |
| `chosen_slot_id` | uuid | yes |  | Slot the renter picked among the options. → `slot` (with `zone_id`). |
| `relocated_booking_id` | uuid | yes |  | The replacement booking created for the renter. → `booking`. Required when `status = resolved`. |
| `approval_request_id` | uuid | yes |  | Escalation to the BQL. → `approval_request`. Required when `status = escalated`. |
| `status` | app.recovery_status | no | 'open'::recovery_status | `open` · `options_ready` · `awaiting_consent` · `resolved` · `escalated` · `cancelled`. `resolved` and `cancelled` close the case. |
| `deadline_at` | timestamp with time zone | no |  | Time by which the case must be settled (before the owner arrives). |
| `resolution_note` | text | yes |  | Free-text note on how the case ended (no PII). |
| `idempotency_key` | text | no |  | Caller-supplied key (`thread_id:step`); replays hit the UNIQUE constraint. |
| `version` | integer | no | 1 | Optimistic lock for edits. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Last update (trigger `set_updated_at`). |

<details><summary>Constraints and indexes</summary>

- CHECK `recovery_case_escalated_has_approval`: `CHECK ((status <> 'escalated'::app.recovery_status) OR (approval_request_id IS NOT NULL))`
- CHECK `recovery_case_options_check`: `CHECK (jsonb_typeof(options) = 'array'::text)`
- CHECK `recovery_case_resolved_has_booking`: `CHECK ((status <> 'resolved'::app.recovery_status) OR (relocated_booking_id IS NOT NULL))`
- FK `recovery_case_approval_request_id_zone_id_fkey`: `FOREIGN KEY (approval_request_id, zone_id) REFERENCES app.approval_request(id, zone_id) ON DELETE RESTRICT`
- FK `recovery_case_booking_id_zone_id_fkey`: `FOREIGN KEY (booking_id, zone_id) REFERENCES app.booking(id, zone_id) ON DELETE RESTRICT`
- FK `recovery_case_chosen_slot_id_zone_id_fkey`: `FOREIGN KEY (chosen_slot_id, zone_id) REFERENCES app.slot(id, zone_id) ON DELETE RESTRICT`
- FK `recovery_case_relocated_booking_id_zone_id_fkey`: `FOREIGN KEY (relocated_booking_id, zone_id) REFERENCES app.booking(id, zone_id) ON DELETE RESTRICT`
- PK `recovery_case_pkey`: `PRIMARY KEY (id)`
- UNIQUE `recovery_case_id_zone_id_key`: `UNIQUE (id, zone_id)`
- UNIQUE `recovery_case_idempotency_key_key`: `UNIQUE (idempotency_key)`
- INDEX: `btree (approval_request_id) WHERE approval_request_id IS NOT NULL`
- UNIQUE INDEX: `btree (booking_id) WHERE status <> ALL (ARRAY['resolved'::app.recovery_status, 'cancelled'::app.recovery_status])`
- INDEX: `btree (chosen_slot_id) WHERE chosen_slot_id IS NOT NULL`
- INDEX: `btree (relocated_booking_id) WHERE relocated_booking_id IS NOT NULL`
- INDEX: `btree (zone_id, deadline_at) WHERE status <> ALL (ARRAY['resolved'::app.recovery_status, 'cancelled'::app.recovery_status])`

</details>

## Agreement & confirmation evidence (M6)

### agreement

Electronic agreement for a TH1/TH2 booking (FR-08); effective only after both confirmations (+ approval if over threshold). Each confirmation also writes a `consent_record` row (FR-09). The confirmation OTP is kept in Redis, not here.  
RLS: **yes** (policies: `parties_read`, `zone_staff`)

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `booking_id` | uuid | no |  | References `booking`. |
| `zone_policy_id` | uuid | no |  | Policy version that priced it. → `zone_policy`. |
| `provider_user_id` | uuid | no |  | References `app_user`. |
| `renter_user_id` | uuid | no |  | References `app_user`. |
| `price_vnd` | bigint | no |  | Amount in VND (integer, ≥ 0). |
| `body_rendered` | text | no |  | Exact text both parties confirmed. |
| `body_sha256` | bytea | no |  | Hash of the rendered text (`hash nội dung thỏa thuận`); copied into `consent_record.evidence.body_sha256` when each party confirms. |
| `status` | app.agreement_status | no | 'pending_confirmation'::agreement_status | Value from the fixed set of its type / CHECK (see constraints). |
| `requires_approval` | boolean | no |  | Set by the rule engine when price > threshold. |
| `approval_request_id` | uuid | yes |  | References `approval_request`. |
| `confirm_deadline` | timestamp with time zone | no |  | After this, the agreement expires. |
| `provider_confirmed_at` | timestamp with time zone | yes |  | Time of the event the name describes (UTC); NULL = not happened. |
| `renter_confirmed_at` | timestamp with time zone | yes |  | Time of the event the name describes (UTC); NULL = not happened. |
| `effective_at` | timestamp with time zone | yes |  | Time of the event the name describes (UTC); NULL = not happened. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Last update (trigger `set_updated_at`). |

<details><summary>Constraints and indexes</summary>

- CHECK `agreement_body_sha256_check`: `CHECK (length(body_sha256) = 32)`
- CHECK `agreement_check`: `CHECK ((status <> 'effective'::app.agreement_status) OR ((provider_confirmed_at IS NOT NULL) AND (renter_confirmed_at IS NOT NULL) AND (effective_at IS NOT NULL) AND ((NOT requires_approval) OR (approval_request_id IS NOT NULL))))`
- CHECK `agreement_check1`: `CHECK ((status <> 'pending_approval'::app.agreement_status) OR (requires_approval AND (approval_request_id IS NOT NULL)))`
- CHECK `agreement_price_vnd_check`: `CHECK (price_vnd >= 0)`
- FK `agreement_approval_request_id_zone_id_fkey`: `FOREIGN KEY (approval_request_id, zone_id) REFERENCES app.approval_request(id, zone_id) ON DELETE RESTRICT`
- FK `agreement_booking_id_zone_id_fkey`: `FOREIGN KEY (booking_id, zone_id) REFERENCES app.booking(id, zone_id) ON DELETE RESTRICT`
- FK `agreement_provider_user_id_fkey`: `FOREIGN KEY (provider_user_id) REFERENCES app.app_user(id) ON DELETE RESTRICT`
- FK `agreement_renter_user_id_fkey`: `FOREIGN KEY (renter_user_id) REFERENCES app.app_user(id) ON DELETE RESTRICT`
- FK `agreement_zone_policy_id_zone_id_fkey`: `FOREIGN KEY (zone_policy_id, zone_id) REFERENCES app.zone_policy(id, zone_id) ON DELETE RESTRICT`
- PK `agreement_pkey`: `PRIMARY KEY (id)`
- UNIQUE `agreement_booking_id_key`: `UNIQUE (booking_id)`
- UNIQUE `agreement_id_zone_id_key`: `UNIQUE (id, zone_id)`
- INDEX: `btree (approval_request_id) WHERE approval_request_id IS NOT NULL`
- INDEX: `btree (confirm_deadline) WHERE status = 'pending_confirmation'::app.agreement_status`
- INDEX: `btree (provider_user_id)`
- INDEX: `btree (renter_user_id)`
- INDEX: `btree (zone_policy_id)`

</details>

### consent_record

Append-only evidence of consent and confirmation (A-03, BR-09, FR-09, AC-07). One row when a user accepts the registration terms or plate processing, when each party confirms an agreement, and when a renter accepts a relocation. Replaces `app_user.consent_*` and the evidence role of the removed ledger. Never updated or deleted (trigger `reject_mutation()`; the app role has INSERT + SELECT only).  
RLS: **yes** (policies: `own`, `own_insert`, `system_all`, `zone_manager_read`)

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | bigint | no | identity | Primary key (identity); also the order of events. |
| `user_id` | uuid | no |  | Who consented or confirmed. → `app_user`. |
| `zone_id` | uuid | yes |  | Zone of the subject; NULL for chain-wide terms such as registration. → `zone`. The BQL of that zone reads the row. |
| `action` | app.consent_action | no |  | `registration_terms` · `plate_processing` · `agreement_confirm` · `accept_relocation`. |
| `subject_type` | text | no |  | Kind of record the consent is about: `app_user`, `agreement` or `recovery_case` (CHECK). |
| `subject_id` | uuid | no |  | Id of that record (polymorphic by design: an evidence log, no FK). |
| `terms_version` | text | no |  | Version of the terms or agreement text that was shown. |
| `decision` | app.consent_decision | no |  | `accepted` · `rejected` · `withdrawn`. |
| `evidence` | jsonb | no | '{}'::jsonb | JSON object with ids, hashes and amounts only, e.g. `body_sha256` (hash nội dung thỏa thuận), price, policy version. No names, no plates. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |

<details><summary>Constraints and indexes</summary>

- CHECK `consent_record_evidence_check`: `CHECK (jsonb_typeof(evidence) = 'object'::text)`
- CHECK `consent_record_subject_type_check`: `CHECK (subject_type = ANY (ARRAY['app_user'::text, 'agreement'::text, 'recovery_case'::text]))`
- CHECK `consent_record_terms_version_check`: `CHECK (btrim(terms_version) <> ''::text)`
- FK `consent_record_user_id_fkey`: `FOREIGN KEY (user_id) REFERENCES app.app_user(id) ON DELETE RESTRICT`
- FK `consent_record_zone_id_fkey`: `FOREIGN KEY (zone_id) REFERENCES app.zone(id) ON DELETE RESTRICT`
- PK `consent_record_pkey`: `PRIMARY KEY (id)`
- UNIQUE `consent_record_natural_uq`: `UNIQUE (user_id, action, subject_id, terms_version, decision)`
- INDEX: `btree (subject_type, subject_id)`
- INDEX: `btree (zone_id, created_at DESC) WHERE zone_id IS NOT NULL`

</details>

## Payment (M7)

### payment

Simulated VietQR payment (A-05). `amount_vnd` is the plain charge or refund amount (no vouchers in the MVP).  
RLS: **yes** (policies: `payer`, `zone_staff`)

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `booking_id` | uuid | no |  | References `booking`. |
| `payer_user_id` | uuid | no |  | References `app_user`. |
| `kind` | app.payment_kind | no |  | Value from the fixed set of its type / CHECK (see constraints). |
| `amount_vnd` | bigint | no |  | Amount in VND (integer, ≥ 0); the direction column says whether it is a charge or a refund. |
| `direction` | text | yes | 
CASE
    WHEN (kind = 'early_return_refund'::payment_kind) THEN 'refund'::text
    ELSE 'charge'::text
END | Generated: refund for early_return_refund, else charge (D-09). |
| `provider` | text | no | 'vietqr_mock'::text | Only `vietqr_mock` (A-05). |
| `status` | app.payment_status | no | 'pending'::payment_status | Value from the fixed set of its type / CHECK (see constraints). |
| `idempotency_key` | text | no |  | Caller-supplied key (`thread_id:step`); replays hit the UNIQUE constraint. |
| `paid_at` | timestamp with time zone | yes |  | Time of the event the name describes (UTC); NULL = not happened. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Last update (trigger `set_updated_at`). |

<details><summary>Constraints and indexes</summary>

- CHECK `payment_amount_vnd_check`: `CHECK (amount_vnd >= 0)`
- CHECK `payment_check`: `CHECK ((status = 'paid_simulated'::app.payment_status) = (paid_at IS NOT NULL))`
- CHECK `payment_provider_check`: `CHECK (provider = 'vietqr_mock'::text)`
- FK `payment_booking_id_zone_id_fkey`: `FOREIGN KEY (booking_id, zone_id) REFERENCES app.booking(id, zone_id) ON DELETE RESTRICT`
- FK `payment_payer_user_id_fkey`: `FOREIGN KEY (payer_user_id) REFERENCES app.app_user(id) ON DELETE RESTRICT`
- PK `payment_pkey`: `PRIMARY KEY (id)`
- UNIQUE `payment_idempotency_key_key`: `UNIQUE (idempotency_key)`
- INDEX: `btree (booking_id)`
- UNIQUE INDEX: `btree (booking_id, kind) WHERE status = 'paid_simulated'::app.payment_status`
- INDEX: `btree (payer_user_id, created_at DESC)`

</details>

## Access / LPR (M8)

### lpr_event

Normalised LPR event. Plain (unpartitioned) table; deduplicated per `(zone_id, source_code, source_event_id)` (BR-13).  
RLS: **yes** (policies: `zone_staff`)

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | bigint | no | identity | Primary key (UUIDv7 unless the type says bigint). |
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `source_code` | text | no |  | Code of the LPR source / vendor system that sent the event (`^[A-Z0-9_-]{1,32}$`); part of the dedupe key. |
| `source_event_id` | text | no |  | Vendor event id; dedupe key with zone and source (BR-13). |
| `gate_code` | text | no |  | Code of the gate that saw the plate (`^[A-Z0-9_-]{1,32}$`); replaces the removed `gate` table. |
| `direction` | app.gate_direction | no |  | Value from the fixed set of its type / CHECK (see constraints). |
| `occurred_at` | timestamp with time zone | no |  | Event time at the gate. |
| `received_at` | timestamp with time zone | no | now() | Time of the event the name describes (UTC); NULL = not happened. |
| `plate_ciphertext` | bytea | yes |  | Encrypted plate read; column-restricted. |
| `plate_hash` | bytea | yes |  | SHA-256 digest (32 bytes); the clear value is never stored. |
| `plate_masked` | text | yes |  | Display form of the read plate. |
| `ocr_confidence` | numeric(4,3) | no |  | 0–1. |
| `status` | app.lpr_status | no |  | accepted · pending_review · confirmed_manual · unreadable. |
| `matched_vehicle_id` | uuid | yes |  | References `vehicle`. |
| `matched_booking_id` | uuid | yes |  | References `booking`. |
| `reviewed_by` | uuid | yes |  | References `app_user`. |
| `reviewed_at` | timestamp with time zone | yes |  | Time of the event the name describes (UTC); NULL = not happened. |

<details><summary>Constraints and indexes</summary>

- CHECK `lpr_event_check`: `CHECK ((plate_ciphertext IS NULL) = (plate_hash IS NULL))`
- CHECK `lpr_event_check1`: `CHECK ((status <> ALL (ARRAY['confirmed_manual'::app.lpr_status, 'unreadable'::app.lpr_status])) OR ((reviewed_by IS NOT NULL) AND (reviewed_at IS NOT NULL)))`
- CHECK `lpr_event_gate_code_check`: `CHECK (gate_code ~ '^[A-Z0-9_-]{1,32}$'::text)`
- CHECK `lpr_event_ocr_confidence_check`: `CHECK ((ocr_confidence >= (0)::numeric) AND (ocr_confidence <= (1)::numeric))`
- CHECK `lpr_event_plate_hash_check`: `CHECK ((plate_hash IS NULL) OR (length(plate_hash) = 32))`
- CHECK `lpr_event_source_code_check`: `CHECK ((btrim(source_code) <> ''::text) AND (length(source_code) <= 64))`
- CHECK `lpr_event_source_event_id_check`: `CHECK ((length(source_event_id) >= 1) AND (length(source_event_id) <= 128))`
- FK `lpr_event_matched_booking_id_fkey`: `FOREIGN KEY (matched_booking_id) REFERENCES app.booking(id) ON DELETE SET NULL`
- FK `lpr_event_matched_vehicle_id_fkey`: `FOREIGN KEY (matched_vehicle_id) REFERENCES app.vehicle(id) ON DELETE SET NULL`
- FK `lpr_event_reviewed_by_fkey`: `FOREIGN KEY (reviewed_by) REFERENCES app.app_user(id) ON DELETE RESTRICT`
- FK `lpr_event_zone_id_fkey`: `FOREIGN KEY (zone_id) REFERENCES app.zone(id) ON DELETE RESTRICT`
- PK `lpr_event_pkey`: `PRIMARY KEY (id)`
- UNIQUE `lpr_event_zone_id_source_code_source_event_id_key`: `UNIQUE (zone_id, source_code, source_event_id)`
- INDEX: `btree (matched_booking_id) WHERE matched_booking_id IS NOT NULL`
- INDEX: `btree (matched_vehicle_id) WHERE matched_vehicle_id IS NOT NULL`
- INDEX: `btree (plate_hash, occurred_at DESC) WHERE plate_hash IS NOT NULL`
- INDEX: `btree (zone_id, occurred_at DESC)`
- INDEX: `btree (zone_id, occurred_at) WHERE status = 'pending_review'::app.lpr_status`

</details>

## Approvals (M12)

### approval_request

HITL queue item for the BQL of the slot's zone; carries the LangGraph `thread_id` (FK to `agent_thread`) to resume.  
RLS: **yes** (policies: `zone_staff`)

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `kind` | app.approval_kind | no |  | Value from the fixed set of its type / CHECK (see constraints). |
| `subject_id` | uuid | no |  | Agreement or booking under review (by `kind`). |
| `thread_id` | text | no |  | LangGraph thread resumed after the decision. → `agent_thread`. |
| `status` | app.approval_status | no | 'pending'::approval_status | Value from the fixed set of its type / CHECK (see constraints). |
| `summary` | text | yes |  | As named. |
| `requested_at` | timestamp with time zone | no | now() | Time of the event the name describes (UTC); NULL = not happened. |
| `due_at` | timestamp with time zone | yes |  | Time of the event the name describes (UTC); NULL = not happened. |
| `decided_by` | uuid | yes |  | References `app_user`. |
| `decided_at` | timestamp with time zone | yes |  | Time of the event the name describes (UTC); NULL = not happened. |
| `decision_note` | text | yes |  | As named. |
| `updated_at` | timestamp with time zone | no | now() | Last update (trigger `set_updated_at`). |

<details><summary>Constraints and indexes</summary>

- CHECK `approval_request_check`: `CHECK ((status = ANY (ARRAY['approved'::app.approval_status, 'rejected'::app.approval_status])) = ((decided_by IS NOT NULL) AND (decided_at IS NOT NULL)))`
- FK `approval_request_decided_by_fkey`: `FOREIGN KEY (decided_by) REFERENCES app.app_user(id) ON DELETE RESTRICT`
- FK `approval_request_thread_id_fkey`: `FOREIGN KEY (thread_id) REFERENCES app.agent_thread(thread_id) ON DELETE RESTRICT`
- FK `approval_request_zone_id_fkey`: `FOREIGN KEY (zone_id) REFERENCES app.zone(id) ON DELETE RESTRICT`
- PK `approval_request_pkey`: `PRIMARY KEY (id)`
- UNIQUE `approval_request_id_zone_id_key`: `UNIQUE (id, zone_id)`
- UNIQUE INDEX: `btree (kind, subject_id) WHERE status = 'pending'::app.approval_status`
- INDEX: `btree (thread_id)`
- INDEX: `btree (zone_id, requested_at) WHERE status = 'pending'::app.approval_status`

</details>

## Notifications (M13)

### notification

In-app notification (M13). Inserted in the same transaction as the business change; idempotent through its `idempotency_key`. Realtime push happens after commit.  
RLS: **yes** (policies: `own_or_system`)

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `user_id` | uuid | no |  | References `app_user`. |
| `zone_id` | uuid | yes |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `kind` | text | no |  | Value from the fixed set of its type / CHECK (see constraints). |
| `title` | text | no |  | As named. |
| `body` | text | no |  | As named. |
| `link` | jsonb | yes |  | Deep link target, e.g. {"type":"agreement","id":…}. |
| `idempotency_key` | text | no |  | Caller-supplied key (`thread_id:step`); replays hit the UNIQUE constraint. |
| `read_at` | timestamp with time zone | yes |  | Time of the event the name describes (UTC); NULL = not happened. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |

<details><summary>Constraints and indexes</summary>

- CHECK `notification_kind_check`: `CHECK (kind ~ '^[a-z_]{2,60}$'::text)`
- CHECK `notification_link_check`: `CHECK ((link IS NULL) OR (jsonb_typeof(link) = 'object'::text))`
- FK `notification_user_id_fkey`: `FOREIGN KEY (user_id) REFERENCES app.app_user(id) ON DELETE CASCADE`
- FK `notification_zone_id_fkey`: `FOREIGN KEY (zone_id) REFERENCES app.zone(id) ON DELETE RESTRICT`
- PK `notification_pkey`: `PRIMARY KEY (id)`
- UNIQUE `notification_idempotency_key_key`: `UNIQUE (idempotency_key)`
- INDEX: `btree (user_id) WHERE read_at IS NULL`
- INDEX: `btree (user_id, created_at DESC, id DESC)`

</details>

## Agent & AI audit (M14)

### agent_thread

One row per LangGraph thread (M14): who talks to the agent, which workflow (W0–W7), where it waits. The graph state lives in the checkpointer (schema `agent`). No raw message text (BR-14, D-12); `pending_card` is the pseudonymised confirmation card only. Replaces the role of the removed `workflow_run`.  
RLS: **yes** (policies: `owner`, `system_all`, `zone_manager_read`)

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `thread_id` | text | no |  | Primary key; equals the LangGraph thread id (1–200 chars). |
| `user_id` | uuid | no |  | The user who owns the conversation. → `app_user`. |
| `zone_id` | uuid | yes |  | Zone of the slot once the thread is routed; NULL before that. → `zone`. Lets the BQL of the zone see threads in `awaiting_manager`. |
| `workflow` | app.workflow_code | no |  | Which workflow runs in the thread: W0 … W7 (enum `workflow_code`). |
| `status` | app.thread_status | no | 'active'::thread_status | `active` · `awaiting_user` · `awaiting_manager` · `completed` · `failed`. |
| `pending_card` | jsonb | yes |  | Pseudonymised confirmation card shown to the user or BQL (JSON object; NULL when nothing is pending). No names, phones or plates (D-12). |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Last update (trigger `set_updated_at`). |

<details><summary>Constraints and indexes</summary>

- CHECK `agent_thread_pending_card_check`: `CHECK ((pending_card IS NULL) OR (jsonb_typeof(pending_card) = 'object'::text))`
- CHECK `agent_thread_thread_id_check`: `CHECK ((length(thread_id) >= 1) AND (length(thread_id) <= 200))`
- FK `agent_thread_user_id_fkey`: `FOREIGN KEY (user_id) REFERENCES app.app_user(id) ON DELETE RESTRICT`
- FK `agent_thread_zone_id_fkey`: `FOREIGN KEY (zone_id) REFERENCES app.zone(id) ON DELETE RESTRICT`
- PK `agent_thread_pkey`: `PRIMARY KEY (thread_id)`
- INDEX: `btree (user_id, updated_at DESC)`
- INDEX: `btree (zone_id) WHERE status = 'awaiting_manager'::app.thread_status`

</details>

### ai_decision_log

Append-only log with one row per AI decision or suggestion step, for the BQL audit screen and the organisers' audit requirement. Only hashes and ids: no raw prompt, output or user id (BR-14). Complements, never replaces, OTel traces (ADR-0008). No purge job in the MVP.  
RLS: **yes** (policies: `system_all`, `zone_manager_read`)

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | bigint | no | identity | Primary key (identity). |
| `thread_id` | text | yes |  | LangGraph thread of the step; NULL for steps outside a thread. → `agent_thread`. |
| `zone_id` | uuid | yes |  | Zone the decision concerns. → `zone`. Drives the BQL read policy. |
| `user_hash` | bytea | no |  | HMAC-SHA256 (32 bytes) of the user id; the raw id is never stored. |
| `workflow` | app.workflow_code | no |  | Workflow of the step (W0 … W7). |
| `step` | text | no |  | Graph node name. |
| `model_version` | text | yes |  | Model identifier; NULL for deterministic (rule-engine) steps. |
| `input_hash` | bytea | no |  | SHA-256 of the step input (32 bytes). |
| `output_hash` | bytea | no |  | SHA-256 of the step output (32 bytes). |
| `risk_level` | app.ai_risk_level | no |  | `low` · `medium` · `high`. |
| `outcome` | app.ai_outcome | no |  | `suggested` · `auto_applied` · `blocked_by_rule` · `sent_to_human` · `failed` · `degraded`. |
| `human_approved` | boolean | yes |  | NULL = no approval needed; true / false = the human decision. |
| `approval_request_id` | uuid | yes |  | Approval that gated the step. → `approval_request`. |
| `trace_id` | text | yes |  | OTel trace id, to jump to Tempo. |
| `latency_ms` | integer | yes |  | Duration of the step in milliseconds (≥ 0). |
| `idempotency_key` | text | no |  | `thread_id:checkpoint_id:node` (ADR-0010): a node replayed after `interrupt()` or a retry logs the decision once. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |

<details><summary>Constraints and indexes</summary>

- CHECK `ai_decision_log_input_hash_check`: `CHECK (length(input_hash) = 32)`
- CHECK `ai_decision_log_latency_ms_check`: `CHECK ((latency_ms IS NULL) OR (latency_ms >= 0))`
- CHECK `ai_decision_log_output_hash_check`: `CHECK (length(output_hash) = 32)`
- CHECK `ai_decision_log_step_check`: `CHECK (btrim(step) <> ''::text)`
- CHECK `ai_decision_log_user_hash_check`: `CHECK (length(user_hash) = 32)`
- FK `ai_decision_log_approval_request_id_fkey`: `FOREIGN KEY (approval_request_id) REFERENCES app.approval_request(id) ON DELETE RESTRICT`
- FK `ai_decision_log_thread_id_fkey`: `FOREIGN KEY (thread_id) REFERENCES app.agent_thread(thread_id) ON DELETE RESTRICT`
- FK `ai_decision_log_zone_id_fkey`: `FOREIGN KEY (zone_id) REFERENCES app.zone(id) ON DELETE RESTRICT`
- PK `ai_decision_log_pkey`: `PRIMARY KEY (id)`
- UNIQUE `ai_decision_log_idempotency_key_key`: `UNIQUE (idempotency_key)`
- INDEX: `btree (approval_request_id) WHERE approval_request_id IS NOT NULL`
- INDEX: `btree (thread_id)`
- INDEX: `btree (zone_id, created_at DESC)`

</details>

## Knowledge base (W7)

### knowledge_chunk

Rule-document chunks for RAG, scoped to zone / building, with document metadata inline + `embedding vector(1024)` (pgvector). Exact scan; no ANN index at this size.  
RLS: **yes** (policies: `manage_zone`, `read_authenticated`)

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `zone_id` | uuid | yes |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `building_id` | uuid | yes |  | Optional building scope; NULL = zone-wide. |
| `doc_title` | text | no |  | Title of the source document this chunk belongs to. |
| `source_uri` | text | no |  | Where the source document lives (URI or path); with `doc_version` and `ordinal` identifies the chunk. |
| `doc_version` | integer | no | 1 | Version of the source document, increasing; old versions are kept and switched off with `is_active`. |
| `is_active` | boolean | no | true | False once the document version is superseded or retired; retrieval reads active chunks only. |
| `ordinal` | integer | no |  | As named. |
| `content` | text | no |  | Chunk text retrieved for W7 answers. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |

<details><summary>Constraints and indexes</summary>

- CHECK `knowledge_chunk_check`: `CHECK ((building_id IS NULL) OR (zone_id IS NOT NULL))`
- CHECK `knowledge_chunk_content_check`: `CHECK (btrim(content) <> ''::text)`
- CHECK `knowledge_chunk_doc_title_check`: `CHECK (btrim(doc_title) <> ''::text)`
- CHECK `knowledge_chunk_doc_version_check`: `CHECK (doc_version > 0)`
- CHECK `knowledge_chunk_ordinal_check`: `CHECK (ordinal >= 0)`
- FK `knowledge_chunk_building_id_zone_id_fkey`: `FOREIGN KEY (building_id, zone_id) REFERENCES app.building(id, zone_id) ON DELETE RESTRICT`
- FK `knowledge_chunk_zone_id_fkey`: `FOREIGN KEY (zone_id) REFERENCES app.zone(id) ON DELETE RESTRICT`
- PK `knowledge_chunk_pkey`: `PRIMARY KEY (id)`
- UNIQUE `knowledge_chunk_source_uri_doc_version_ordinal_key`: `UNIQUE (source_uri, doc_version, ordinal)`
- INDEX: `btree (zone_id, building_id) WHERE is_active`

</details>

## Views

### kpi_daily_v

Daily request outcomes per zone for the KPI dashboard (replaces the v2 table `kpi_daily`). Aggregates `parking_request` joined to `zone`, grouped by `zone_id` and the local day.  
Options: `security_barrier = true`

| Column | Type | Meaning |
|---|---|---|
| `zone_id` | uuid | Zone the requests belong to. |
| `day` | date | Local business day: `(created_at AT TIME ZONE zone.timezone)::date`. |
| `requests_total` | bigint | All parking requests of the day. |
| `matched` | bigint | Requests with outcome `matched`. |
| `redirected_th3` | bigint | Requests with outcome `redirected_th3`. |
| `redirected_public` | bigint | Requests with outcome `redirected_public`. |
| `blocked` | bigint | Requests with outcome `blocked`. |
| `no_match` | bigint | Requests with outcome `no_match`. |

Row filter inside the view: `app.ctx_role() = 'chain_operator' OR (app.ctx_role() IN ('zone_manager','system') AND zone_id = ANY (app.ctx_zone_ids()))`. So a chain operator sees every zone, a BQL (or the system role) sees only the zones in its context, and a resident or guard sees no row. The view runs with owner rights on purpose: it exposes aggregates only (PRD §9), never rows of `parking_request`. `parksmart_readonly` is granted `zone` and `kpi_daily_v`.
