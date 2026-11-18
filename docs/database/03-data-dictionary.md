# 03 — Data dictionary

> Generated from the catalog of a database built with [02-schema.sql](02-schema.sql) v3 (PostgreSQL 17.10, pgvector column absent in that build; the column `knowledge_chunk.embedding vector(1024)` is not counted below),
> so types, nullability, defaults and constraints match the DDL exactly: **27 tables, 285 columns** (plus the view `kpi_daily_v`). Meanings are hand-written.
> Regenerate after schema changes rather than editing the type columns by hand.

Conventions: all tables live in schema `app`. `RLS` = row-level security enabled. Times are `timestamptz` (UTC);
ranges are half-open `[start, end)`. Money is `bigint` VND. Enum values are listed in [02-schema.sql §1](02-schema.sql).

## Contents

- **Facility & pools (M2, M3)**: [`zone`](#zone) · [`building`](#building) · [`slot_pool`](#slot_pool) · [`slot`](#slot)
- **Identity (M1)**: [`app_user`](#app_user) · [`staff_zone`](#staff_zone) · [`refresh_token`](#refresh_token) · [`vehicle`](#vehicle)
- **Eligibility (M1)**: [`asset`](#asset) · [`eligibility`](#eligibility) · [`slot_holding`](#slot_holding)
- **Policy & configuration (M3)**: [`zone_policy`](#zone_policy)
- **Sharing & booking (M4, M5)**: [`share_window`](#share_window) · [`parking_request`](#parking_request) · [`booking`](#booking)
- **Agreement & ledger (M6)**: [`agreement`](#agreement) · [`otp_challenge`](#otp_challenge) · [`ledger_head`](#ledger_head) · [`ledger_entry`](#ledger_entry)
- **Payment (M7)**: [`payment`](#payment)
- **Access / LPR (M8)**: [`lpr_event`](#lpr_event)
- **Approvals (M12)**: [`approval_request`](#approval_request)
- **Notifications (M13)**: [`notification`](#notification)
- **Platform (ADR-0005, ADR-0010)**: [`outbox`](#outbox) · [`idempotency_keys`](#idempotency_keys) · [`audit_log`](#audit_log)
- **Knowledge base (W7)**: [`knowledge_chunk`](#knowledge_chunk)
- **Views**: [`kpi_daily_v`](#kpi_daily_v)
- **Removed in v3**: 30 tables of the v2 design (`chain`, `subzone`, `basement`, `voucher`, `dispute_*`, `swap_*`, `kpi_daily` …) are not in this dictionary; see [11-deferred-tables.md](11-deferred-tables.md) for the list and how to bring each back.

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

Ô đỗ. Type TH1/TH2/TH3 is denormalised from the pool and kept consistent by composite FK.  
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
| `is_active` | boolean | no | true | Soft retire flag; rows stay referenced by history. |
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
- INDEX: `btree (zone_id, slot_type) WHERE is_active`

</details>

## Identity (M1)

### app_user

One account for the whole chain (FR-23). Soft-deleted. Holds the single consent record for plate/photo processing (A-03, BR-09).  
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
| `consent_text_version` | text | yes |  | Version of the consent text the user accepted; set together with `consented_at` (both NULL or both set). |
| `consented_at` | timestamp with time zone | yes |  | When the user accepted the consent text; NULL = no consent recorded. Withdrawal history is deferred. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Last update (trigger `set_updated_at`). |

<details><summary>Constraints and indexes</summary>

- CHECK `app_user_consent_pair`: `CHECK ((consent_text_version IS NULL) = (consented_at IS NULL))`
- CHECK `app_user_deleted_consistent`: `CHECK ((status = 'deleted'::app.user_status) = (deleted_at IS NOT NULL))`
- CHECK `app_user_email_check`: `CHECK ((email IS NULL) OR (email ~ '^[^@\s]+@[^@\s]+$'::text))`
- CHECK `app_user_failed_logins_check`: `CHECK (failed_logins >= 0)`
- CHECK `app_user_full_name_check`: `CHECK ((btrim(full_name) <> ''::text) AND (length(full_name) <= 200))`
- CHECK `app_user_password_hash_check`: `CHECK (password_hash ~~ '$argon2id$%'::text)`
- CHECK `app_user_phone_e164_check`: `CHECK (phone_e164 ~ '^\+[1-9][0-9]{7,14}$'::text)`
- CHECK `app_user_phone_required`: `CHECK ((status = 'deleted'::app.user_status) OR (phone_e164 IS NOT NULL))`
- PK `app_user_pkey`: `PRIMARY KEY (id)`
- UNIQUE INDEX: `btree (lower(email)) WHERE (deleted_at IS NULL) AND (email IS NOT NULL)`
- UNIQUE INDEX: `btree (phone_e164) WHERE deleted_at IS NULL`

</details>

### staff_zone

Zones a BQL or guard works for (source of the JWT `zone_ids` claim). M:N junction.  
RLS: **yes** (policies: `own_or_system`)

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `user_id` | uuid | no |  | References `app_user`. |
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `granted_at` | timestamp with time zone | no | now() | Time of the event the name describes (UTC); NULL = not happened. |

<details><summary>Constraints and indexes</summary>

- FK `staff_zone_user_id_fkey`: `FOREIGN KEY (user_id) REFERENCES app.app_user(id) ON DELETE CASCADE`
- FK `staff_zone_zone_id_fkey`: `FOREIGN KEY (zone_id) REFERENCES app.zone(id) ON DELETE RESTRICT`
- PK `staff_zone_pkey`: `PRIMARY KEY (user_id, zone_id)`
- INDEX: `btree (zone_id)`

</details>

### refresh_token

Hashed rotating refresh tokens (ADR-0006). `family_id` lets reuse revoke the whole chain.  
RLS: **yes** (policies: `own_or_system`)

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `user_id` | uuid | no |  | References `app_user`. |
| `family_id` | uuid | no |  | Rotation chain id; reuse of an old token revokes the family. |
| `token_hash` | bytea | no |  | SHA-256 of the opaque token. |
| `issued_at` | timestamp with time zone | no | now() | Time of the event the name describes (UTC); NULL = not happened. |
| `expires_at` | timestamp with time zone | no |  | Time of the event the name describes (UTC); NULL = not happened. |
| `used_at` | timestamp with time zone | yes |  | Set on rotation; a second use is a reuse attack → revoke family. |
| `revoked_at` | timestamp with time zone | yes |  | Time of the event the name describes (UTC); NULL = not happened. |

<details><summary>Constraints and indexes</summary>

- CHECK `refresh_token_check`: `CHECK (expires_at > issued_at)`
- CHECK `refresh_token_token_hash_check`: `CHECK (length(token_hash) = 32)`
- FK `refresh_token_user_id_fkey`: `FOREIGN KEY (user_id) REFERENCES app.app_user(id) ON DELETE CASCADE`
- PK `refresh_token_pkey`: `PRIMARY KEY (id)`
- UNIQUE `refresh_token_token_hash_key`: `UNIQUE (token_hash)`
- INDEX: `btree (family_id) WHERE revoked_at IS NULL`
- INDEX: `btree (user_id)`

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

A reservation of a slot for a period. EXCLUDE constraint makes double booking impossible.  
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
| `relocated_from_booking_id` | uuid | yes |  | Original booking when this is a TH3 replacement after early return. → `booking`. |
| `idempotency_key` | text | no |  | Caller-supplied key (`thread_id:step`); replays hit the UNIQUE constraint. |
| `version` | integer | no | 1 | Optimistic lock for user-driven edits. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Last update (trigger `set_updated_at`). |

<details><summary>Constraints and indexes</summary>

- CHECK `booking_check`: `CHECK ((share_window_id IS NULL) = (provider_user_id IS NULL))`
- CHECK `booking_check1`: `CHECK ((provider_user_id IS NULL) OR (provider_user_id <> renter_user_id))`
- CHECK `booking_check2`: `CHECK ((status <> 'held'::app.booking_status) OR (hold_expires_at IS NOT NULL))`
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

## Agreement & ledger (M6)

### agreement

Electronic agreement for a TH1/TH2 booking (FR-08); effective only after both confirmations (+ approval if over threshold).  
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
| `body_sha256` | bytea | no |  | Hash of the rendered text (put into the ledger payload). |
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

### otp_challenge

OTP used to confirm an agreement (ADR-0006): hashed, expiring, limited attempts.  
RLS: **yes** (policies: `own_or_system`)

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `user_id` | uuid | no |  | References `app_user`. |
| `purpose` | text | no |  | Value from the fixed set of its type / CHECK (see constraints). |
| `subject_id` | uuid | no |  | Agreement being confirmed. |
| `code_hash` | bytea | no |  | Hash of the 6-digit code. |
| `expires_at` | timestamp with time zone | no |  | Time of the event the name describes (UTC); NULL = not happened. |
| `attempts` | smallint | no | 0 | Retry/attempt counter. |
| `max_attempts` | smallint | no | 5 | As named. |
| `consumed_at` | timestamp with time zone | yes |  | Time of the event the name describes (UTC); NULL = not happened. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |

<details><summary>Constraints and indexes</summary>

- CHECK `otp_challenge_check`: `CHECK ((attempts >= 0) AND (attempts <= max_attempts))`
- CHECK `otp_challenge_code_hash_check`: `CHECK (length(code_hash) = 32)`
- CHECK `otp_challenge_max_attempts_check`: `CHECK ((max_attempts >= 1) AND (max_attempts <= 10))`
- CHECK `otp_challenge_purpose_check`: `CHECK (purpose = 'agreement_confirm'::text)`
- FK `otp_challenge_user_id_fkey`: `FOREIGN KEY (user_id) REFERENCES app.app_user(id) ON DELETE CASCADE`
- PK `otp_challenge_pkey`: `PRIMARY KEY (id)`
- UNIQUE INDEX: `btree (user_id, purpose, subject_id) WHERE consumed_at IS NULL`

</details>

### ledger_head

Per-zone tip of the hash chain (last seq + hash). Row-locked by `app.ledger_append`; no app grants.  
RLS: **no**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `last_seq` | bigint | no | 0 | Seq of the newest entry of the zone. |
| `last_hash` | bytea | no | decode(repeat('00'::text, 32), 'hex'::text) | Hash of the newest entry of the zone. |

<details><summary>Constraints and indexes</summary>

- CHECK `ledger_head_last_seq_check`: `CHECK (last_seq >= 0)`
- FK `ledger_head_zone_id_fkey`: `FOREIGN KEY (zone_id) REFERENCES app.zone(id) ON DELETE RESTRICT`
- PK `ledger_head_pkey`: `PRIMARY KEY (zone_id)`

</details>

### ledger_entry

Append-only, hash-chained ledger per zone (PRD §9). Written only via `app.ledger_append`.  
RLS: **yes** (policies: `zone_staff_read`)

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `seq` | bigint | no |  | Gap-free sequence per zone. |
| `entry_type` | app.ledger_entry_type | no |  | Value from the fixed set of its type / CHECK (see constraints). |
| `subject_type` | text | no |  | Kind of record referenced (polymorphic by design; the ledger is a log). |
| `subject_id` | uuid | no |  | As named. |
| `payload` | jsonb | no |  | Ids and amounts only, no names or plates. |
| `idempotency_key` | text | no |  | Caller-supplied key (`thread_id:step`); replays hit the UNIQUE constraint. |
| `created_at` | timestamp with time zone | no |  | Insert time (UTC). |
| `prev_hash` | bytea | no |  | Hash of the previous entry of the zone (32 zero bytes for the first). |
| `hash` | bytea | no |  | sha256(prev_hash ‖ canonical fields). |

<details><summary>Constraints and indexes</summary>

- CHECK `ledger_entry_hash_check`: `CHECK (length(hash) = 32)`
- CHECK `ledger_entry_payload_check`: `CHECK (jsonb_typeof(payload) = 'object'::text)`
- CHECK `ledger_entry_prev_hash_check`: `CHECK (length(prev_hash) = 32)`
- CHECK `ledger_entry_seq_check`: `CHECK (seq > 0)`
- CHECK `ledger_entry_subject_type_check`: `CHECK (subject_type = ANY (ARRAY['agreement'::text, 'booking'::text, 'payment'::text]))`
- FK `ledger_entry_zone_id_fkey`: `FOREIGN KEY (zone_id) REFERENCES app.zone(id) ON DELETE RESTRICT`
- PK `ledger_entry_pkey`: `PRIMARY KEY (zone_id, seq)`
- UNIQUE `ledger_entry_idempotency_key_key`: `UNIQUE (idempotency_key)`
- INDEX: `btree (subject_type, subject_id)`
- INDEX: `btree (zone_id, created_at)`

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
| `direction` | text | yes | generated | Generated: refund for early_return_refund, else charge (D-09). |
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

HITL queue item for the BQL of the slot's zone; carries the LangGraph `thread_id` to resume.  
RLS: **yes** (policies: `zone_staff`)

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `kind` | app.approval_kind | no |  | Value from the fixed set of its type / CHECK (see constraints). |
| `subject_id` | uuid | no |  | Agreement or booking under review (by `kind`). |
| `thread_id` | text | no |  | LangGraph thread resumed after the decision. |
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
- FK `approval_request_zone_id_fkey`: `FOREIGN KEY (zone_id) REFERENCES app.zone(id) ON DELETE RESTRICT`
- PK `approval_request_pkey`: `PRIMARY KEY (id)`
- UNIQUE `approval_request_id_zone_id_key`: `UNIQUE (id, zone_id)`
- UNIQUE INDEX: `btree (kind, subject_id) WHERE status = 'pending'::app.approval_status`
- INDEX: `btree (zone_id, requested_at) WHERE status = 'pending'::app.approval_status`

</details>

## Notifications (M13)

### notification

In-app notification (M13). Idempotent per outbox event.  
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

## Platform (ADR-0005, ADR-0010)

### outbox

Transactional outbox (ADR-0010). Payload holds ids, never PII.  
RLS: **no**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | bigint | no | identity | Primary key (UUIDv7 unless the type says bigint). |
| `event_type` | text | no |  | As named. |
| `zone_id` | uuid | yes |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `payload` | jsonb | no |  | Event data: ids and amounts only. |
| `traceparent` | text | yes |  | W3C trace context (ADR-0008). |
| `attempts` | integer | no | 0 | Retry/attempt counter. |
| `last_error` | text | yes |  | Last relay error, for the dead-letter view. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |
| `published_at` | timestamp with time zone | yes |  | NULL until the relay publishes it. |

<details><summary>Constraints and indexes</summary>

- CHECK `outbox_attempts_check`: `CHECK (attempts >= 0)`
- CHECK `outbox_event_type_check`: `CHECK (event_type ~ '^[A-Za-z][A-Za-z0-9_.]{1,80}$'::text)`
- CHECK `outbox_payload_check`: `CHECK (jsonb_typeof(payload) = 'object'::text)`
- FK `outbox_zone_id_fkey`: `FOREIGN KEY (zone_id) REFERENCES app.zone(id) ON DELETE RESTRICT`
- PK `outbox_pkey`: `PRIMARY KEY (id)`
- INDEX: `btree (id) WHERE published_at IS NULL`
- INDEX: `btree (published_at) WHERE published_at IS NOT NULL`

</details>

### idempotency_keys

Generic idempotency store (`thread_id:step`, `source:event_id`); rows are deleted by a TTL job.  
RLS: **no**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `key` | text | no |  | `thread_id:step` (workflows) or `source:event_id` (jobs). |
| `result` | jsonb | yes |  | Result returned to a replay of the same key. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |

<details><summary>Constraints and indexes</summary>

- CHECK `idempotency_keys_key_check`: `CHECK ((length(key) >= 1) AND (length(key) <= 200))`
- PK `idempotency_keys_pkey`: `PRIMARY KEY (key)`
- INDEX: `btree (created_at)`

</details>

### audit_log

Trigger-written history of config, eligibility, holding and approval changes. Append-only.  
RLS: **yes** (policies: `zone_manager_read`)

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | bigint | no | identity | Primary key (UUIDv7 unless the type says bigint). |
| `zone_id` | uuid | yes |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `actor_user_id` | uuid | yes |  | As named. |
| `actor_role` | text | no |  | app.role at the time of change. |
| `table_name` | text | no |  | As named. |
| `row_id` | text | no |  | As named. |
| `action` | text | no |  | Value from the fixed set of its type / CHECK (see constraints). |
| `old_row` | jsonb | yes |  | Row before the change (jsonb snapshot). |
| `new_row` | jsonb | yes |  | Row after the change (jsonb snapshot). |
| `at` | timestamp with time zone | no | now() | As named. |

<details><summary>Constraints and indexes</summary>

- CHECK `audit_log_action_check`: `CHECK (action = ANY (ARRAY['INSERT'::text, 'UPDATE'::text, 'DELETE'::text]))`
- PK `audit_log_pkey`: `PRIMARY KEY (id)`
- INDEX: `btree (table_name, row_id)`
- INDEX: `btree (zone_id, at DESC)`

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
