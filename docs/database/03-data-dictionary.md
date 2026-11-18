# 03 — Data dictionary

> Generated from the catalog of a database built with [02-schema.sql](02-schema.sql) (PostgreSQL 17.10, PG16-compatible DDL),
> so types, nullability, defaults and constraints match the DDL exactly. Meanings are hand-written.
> Regenerate after schema changes rather than editing the type columns by hand.

Conventions: all tables live in schema `app`. `RLS` = row-level security enabled. Times are `timestamptz` (UTC);
ranges are half-open `[start, end)`. Money is `bigint` VND. Enum values are listed in [02-schema.sql §1](02-schema.sql).

## Contents

- **Facility & pools (M2, M3)**: [`chain`](#chain) · [`zone`](#zone) · [`subzone`](#subzone) · [`building`](#building) · [`basement`](#basement) · [`size_class`](#size_class) · [`slot_pool`](#slot_pool) · [`slot`](#slot) · [`gate`](#gate)
- **Identity (M1)**: [`app_user`](#app_user) · [`staff_zone`](#staff_zone) · [`consent`](#consent) · [`refresh_token`](#refresh_token) · [`password_reset_token`](#password_reset_token) · [`vehicle`](#vehicle)
- **Eligibility (M1)**: [`asset`](#asset) · [`eligibility`](#eligibility) · [`slot_holding`](#slot_holding)
- **Policy & configuration (M3)**: [`zone_policy`](#zone_policy) · [`price_rule`](#price_rule) · [`agreement_template`](#agreement_template) · [`holiday`](#holiday)
- **Sharing & booking (M4, M5)**: [`share_window`](#share_window) · [`parking_request`](#parking_request) · [`booking`](#booking)
- **Agreement & ledger (M6)**: [`agreement`](#agreement) · [`otp_challenge`](#otp_challenge) · [`ledger_head`](#ledger_head) · [`ledger_entry`](#ledger_entry)
- **Payment & vouchers (M7)**: [`voucher`](#voucher) · [`payment`](#payment)
- **Access / LPR (M8, M9)**: [`lpr_source`](#lpr_source) · [`lpr_event`](#lpr_event) · [`parking_session`](#parking_session) · [`overstay_case`](#overstay_case) · [`plate_access_log`](#plate_access_log)
- **Disputes (M10)**: [`dispute_category`](#dispute_category) · [`dispute_ticket`](#dispute_ticket) · [`dispute_party`](#dispute_party) · [`dispute_evidence`](#dispute_evidence)
- **Swaps (M11)**: [`swap_need`](#swap_need) · [`swap_proposal`](#swap_proposal) · [`swap_leg`](#swap_leg)
- **Approvals (M12)**: [`approval_request`](#approval_request)
- **Notifications (M13)**: [`notification`](#notification)
- **Reporting (M12, N3, N4, N7)**: [`vacancy_forecast`](#vacancy_forecast) · [`kpi_daily`](#kpi_daily) · [`reconciliation_report`](#reconciliation_report)
- **Platform (ADR-0005, ADR-0010)**: [`outbox`](#outbox) · [`idempotency_keys`](#idempotency_keys) · [`workflow_run`](#workflow_run) · [`audit_log`](#audit_log)
- **Knowledge base (W7)**: [`knowledge_doc`](#knowledge_doc) · [`knowledge_chunk`](#knowledge_chunk)

## Facility & pools (M2, M3)

### chain

The operator's chain of urban areas. One row in the demo; kept as a table so N chains need no code change.  
RLS: **no**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `code` | text | no |  | Business code, unique within its parent. |
| `name` | text | no |  | Display name. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Last update (trigger `set_updated_at`). |

<details><summary>Constraints and indexes</summary>

- CHECK `chain_code_check`: `CHECK (code ~ '^[A-Z0-9_-]{2,32}$'::text)`
- CHECK `chain_name_check`: `CHECK (btrim(name) <> ''::text)`
- PK `chain_pkey`: `PRIMARY KEY (id)`
- UNIQUE `chain_code_key`: `UNIQUE (code)`

</details>

### zone

Khu đô thị. Unit of data ownership, RLS, pricing, approvals (BR-18).  
RLS: **no**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `chain_id` | uuid | no |  | References `chain`. |
| `code` | text | no |  | Business code, unique within its parent. |
| `name` | text | no |  | Display name. |
| `timezone` | text | no | 'Asia/Ho_Chi_Minh'::text | IANA zone for local business days (reconciliation, expiry on day D). |
| `is_active` | boolean | no | true | Soft retire flag; rows stay referenced by history. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Last update (trigger `set_updated_at`). |

<details><summary>Constraints and indexes</summary>

- CHECK `zone_code_check`: `CHECK (code ~ '^[A-Z0-9_-]{1,32}$'::text)`
- CHECK `zone_name_check`: `CHECK (btrim(name) <> ''::text)`
- FK `zone_chain_id_fkey`: `FOREIGN KEY (chain_id) REFERENCES app.chain(id) ON DELETE RESTRICT`
- PK `zone_pkey`: `PRIMARY KEY (id)`
- UNIQUE `zone_chain_id_code_key`: `UNIQUE (chain_id, code)`

</details>

### subzone

Phân khu inside a zone.  
RLS: **yes**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `code` | text | no |  | Business code, unique within its parent. |
| `name` | text | no |  | Display name. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Last update (trigger `set_updated_at`). |

<details><summary>Constraints and indexes</summary>

- CHECK `subzone_name_check`: `CHECK (btrim(name) <> ''::text)`
- FK `subzone_zone_id_fkey`: `FOREIGN KEY (zone_id) REFERENCES app.zone(id) ON DELETE RESTRICT`
- PK `subzone_pkey`: `PRIMARY KEY (id)`
- UNIQUE `subzone_id_zone_id_key`: `UNIQUE (id, zone_id)`
- UNIQUE `subzone_zone_id_code_key`: `UNIQUE (zone_id, code)`

</details>

### building

Tòa / cụm shophouse / bãi công cộng. A public lot is a building of kind `public_lot`.  
RLS: **yes**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `subzone_id` | uuid | no |  | References `subzone`. |
| `code` | text | no |  | Business code, unique within its parent. |
| `name` | text | no |  | Display name. |
| `kind` | app.building_kind | no |  | residential_tower · lowrise_cluster · public_lot. |
| `is_active` | boolean | no | true | Soft retire flag; rows stay referenced by history. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Last update (trigger `set_updated_at`). |

<details><summary>Constraints and indexes</summary>

- CHECK `building_name_check`: `CHECK (btrim(name) <> ''::text)`
- FK `building_subzone_id_zone_id_fkey`: `FOREIGN KEY (subzone_id, zone_id) REFERENCES app.subzone(id, zone_id) ON DELETE RESTRICT`
- PK `building_pkey`: `PRIMARY KEY (id)`
- UNIQUE `building_id_zone_id_key`: `UNIQUE (id, zone_id)`
- UNIQUE `building_zone_id_code_key`: `UNIQUE (zone_id, code)`

</details>

### basement

Hầm or parking level of a building (a public lot has one ground level `G`).  
RLS: **yes**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `building_id` | uuid | no |  | References `building`. |
| `code` | text | no |  | Business code, unique within its parent. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |

<details><summary>Constraints and indexes</summary>

- FK `basement_building_id_zone_id_fkey`: `FOREIGN KEY (building_id, zone_id) REFERENCES app.building(id, zone_id) ON DELETE RESTRICT`
- PK `basement_pkey`: `PRIMARY KEY (id)`
- UNIQUE `basement_building_id_code_key`: `UNIQUE (building_id, code)`
- UNIQUE `basement_id_building_id_zone_id_key`: `UNIQUE (id, building_id, zone_id)`

</details>

### size_class

Lookup: vehicle/slot size classes. Fit rule: vehicle.rank ≤ slot.rank (BR-11).  
RLS: **no**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `code` | text | no |  | Business code, unique within its parent. |
| `rank` | smallint | no |  | Ordering used for the fit rule. |
| `label_vi` | text | no |  | As named. |
| `max_length_cm` | integer | yes |  | As named. |
| `max_width_cm` | integer | yes |  | As named. |

<details><summary>Constraints and indexes</summary>

- CHECK `size_class_code_check`: `CHECK (code ~ '^[A-Z0-9_]{1,16}$'::text)`
- CHECK `size_class_max_length_cm_check`: `CHECK (max_length_cm > 0)`
- CHECK `size_class_max_width_cm_check`: `CHECK (max_width_cm > 0)`
- CHECK `size_class_rank_check`: `CHECK (rank >= 1 AND rank <= 100)`
- PK `size_class_pkey`: `PRIMARY KEY (code)`
- UNIQUE `size_class_rank_key`: `UNIQUE (rank)`

</details>

### slot_pool

Pool of slots of one type with its open scope (FR-26). TH1 per building, TH2/TH3 per zone.  
RLS: **yes**

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

- CHECK `slot_pool_scope_by_type`: `CHECK (slot_type = 'TH1'::app.slot_type AND building_id IS NOT NULL AND (max_open_scope = ANY (ARRAY['building'::app.open_scope, 'zone'::app.open_scope])) OR slot_type = 'TH2'::app.slot_type AND (max_open_scope = ANY (ARRAY['zone'::app.open_scope, 'chain'::app.open_scope])) AND investor_consent_at IS NOT NULL OR slot_type = 'TH3'::app.slot_type AND max_open_scope = 'public'::app.open_scope)`
- FK `slot_pool_building_id_zone_id_fkey`: `FOREIGN KEY (building_id, zone_id) REFERENCES app.building(id, zone_id) ON DELETE RESTRICT`
- FK `slot_pool_zone_id_fkey`: `FOREIGN KEY (zone_id) REFERENCES app.zone(id) ON DELETE RESTRICT`
- PK `slot_pool_pkey`: `PRIMARY KEY (id)`
- UNIQUE `slot_pool_id_slot_type_zone_id_key`: `UNIQUE (id, slot_type, zone_id)`
- UNIQUE `slot_pool_zone_id_building_id_slot_type_key`: `UNIQUE NULLS NOT DISTINCT (zone_id, building_id, slot_type)`

</details>

### slot

Ô đỗ. Type TH1/TH2/TH3 is denormalised from the pool and kept consistent by composite FK.  
RLS: **yes**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `building_id` | uuid | no |  | Optional building scope; NULL = zone-wide. |
| `basement_id` | uuid | no |  | References `basement`. |
| `pool_id` | uuid | no |  | Pool that defines type and scope. → `slot_pool`. |
| `slot_type` | app.slot_type | no |  | TH1 / TH2 / TH3 (copy of the pool's type). |
| `code` | text | no |  | Business code, unique within its parent. |
| `size_class_code` | text | no |  | Slot size class. → `size_class`. |
| `is_active` | boolean | no | true | Soft retire flag; rows stay referenced by history. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Last update (trigger `set_updated_at`). |

<details><summary>Constraints and indexes</summary>

- FK `slot_basement_id_building_id_zone_id_fkey`: `FOREIGN KEY (basement_id, building_id, zone_id) REFERENCES app.basement(id, building_id, zone_id) ON DELETE RESTRICT`
- FK `slot_pool_id_slot_type_zone_id_fkey`: `FOREIGN KEY (pool_id, slot_type, zone_id) REFERENCES app.slot_pool(id, slot_type, zone_id) ON DELETE RESTRICT`
- FK `slot_size_class_code_fkey`: `FOREIGN KEY (size_class_code) REFERENCES app.size_class(code) ON DELETE RESTRICT`
- PK `slot_pkey`: `PRIMARY KEY (id)`
- UNIQUE `slot_building_id_code_key`: `UNIQUE (building_id, code)`
- UNIQUE `slot_id_zone_id_key`: `UNIQUE (id, zone_id)`
- UNIQUE `slot_id_zone_id_slot_type_key`: `UNIQUE (id, zone_id, slot_type)`
- INDEX: `btree (pool_id)`
- INDEX: `btree (zone_id, slot_type) WHERE is_active`

</details>

### gate

Entry/exit gate that emits LPR events.  
RLS: **yes**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `building_id` | uuid | yes |  | References `building`. |
| `code` | text | no |  | Business code, unique within its parent. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |

<details><summary>Constraints and indexes</summary>

- FK `gate_building_id_zone_id_fkey`: `FOREIGN KEY (building_id, zone_id) REFERENCES app.building(id, zone_id) ON DELETE RESTRICT`
- FK `gate_zone_id_fkey`: `FOREIGN KEY (zone_id) REFERENCES app.zone(id) ON DELETE RESTRICT`
- PK `gate_pkey`: `PRIMARY KEY (id)`
- UNIQUE `gate_id_zone_id_key`: `UNIQUE (id, zone_id)`
- UNIQUE `gate_zone_id_code_key`: `UNIQUE (zone_id, code)`

</details>

## Identity (M1)

### app_user

One account for the whole chain (FR-23). Soft-deleted; PII scrubbed on erasure.  
RLS: **yes**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `full_name` | text | no |  | PII. Pseudonymised before any LLM call (BR-14). |
| `phone_e164` | text | no |  | Login id, E.164. Unique among non-deleted users. |
| `email` | text | yes |  | PII, optional; unique case-insensitively among live users. |
| `password_hash` | text | no |  | argon2id hash only (CHECK). |
| `role` | app.user_role | no | 'resident'::app.user_role | Application role (ADR-0006). Eligibility is separate and never in the token. |
| `status` | app.user_status | no | 'active'::app.user_status | Value from the fixed set of its type / CHECK (see constraints). |
| `failed_logins` | smallint | no | 0 | Counter for temporary lock. |
| `locked_until` | timestamp with time zone | yes |  | Temporary lock after repeated failed logins. |
| `deleted_at` | timestamp with time zone | yes |  | Soft delete marker; equals status = deleted. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Last update (trigger `set_updated_at`). |

<details><summary>Constraints and indexes</summary>

- CHECK `app_user_deleted_consistent`: `CHECK ((status = 'deleted'::app.user_status) = (deleted_at IS NOT NULL))`
- CHECK `app_user_email_check`: `CHECK (email IS NULL OR email ~ '^[^@\s]+@[^@\s]+$'::text)`
- CHECK `app_user_failed_logins_check`: `CHECK (failed_logins >= 0)`
- CHECK `app_user_full_name_check`: `CHECK (btrim(full_name) <> ''::text AND length(full_name) <= 200)`
- CHECK `app_user_password_hash_check`: `CHECK (password_hash ~~ '$argon2id$%'::text)`
- CHECK `app_user_phone_e164_check`: `CHECK (phone_e164 ~ '^\+[1-9][0-9]{7,14}$'::text)`
- PK `app_user_pkey`: `PRIMARY KEY (id)`
- INDEX: `btree (lower(email)) WHERE ((deleted_at IS NULL) AND (email IS NOT NULL))`
- INDEX: `btree (phone_e164) WHERE (deleted_at IS NULL)`

</details>

### staff_zone

Zones a BQL or guard works for (source of the JWT `zone_ids` claim). M:N junction.  
RLS: **yes**

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

### consent

Consent to process plates/photos (A-03, BR-09). Withdrawal closes the row; never deleted.  
RLS: **yes**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `user_id` | uuid | no |  | References `app_user`. |
| `kind` | app.consent_kind | no |  | Value from the fixed set of its type / CHECK (see constraints). |
| `text_version` | text | no |  | Version of the consent text the user accepted. |
| `granted_at` | timestamp with time zone | no | now() | Time of the event the name describes (UTC); NULL = not happened. |
| `withdrawn_at` | timestamp with time zone | yes |  | Time of the event the name describes (UTC); NULL = not happened. |

<details><summary>Constraints and indexes</summary>

- CHECK `consent_check`: `CHECK (withdrawn_at IS NULL OR withdrawn_at >= granted_at)`
- FK `consent_user_id_fkey`: `FOREIGN KEY (user_id) REFERENCES app.app_user(id) ON DELETE CASCADE`
- PK `consent_pkey`: `PRIMARY KEY (id)`
- INDEX: `btree (user_id, kind) WHERE (withdrawn_at IS NULL)`

</details>

### refresh_token

Hashed rotating refresh tokens (ADR-0006). `family_id` lets reuse revoke the whole chain.  
RLS: **yes**

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
- INDEX: `btree (family_id) WHERE (revoked_at IS NULL)`
- INDEX: `btree (user_id)`

</details>

### password_reset_token

Hashed single-use reset links, 30-minute expiry (ADR-0006).  
RLS: **yes**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `user_id` | uuid | no |  | References `app_user`. |
| `token_hash` | bytea | no |  | SHA-256 digest (32 bytes); the clear value is never stored. |
| `expires_at` | timestamp with time zone | no |  | Time of the event the name describes (UTC); NULL = not happened. |
| `used_at` | timestamp with time zone | yes |  | Time of the event the name describes (UTC); NULL = not happened. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |

<details><summary>Constraints and indexes</summary>

- CHECK `password_reset_token_token_hash_check`: `CHECK (length(token_hash) = 32)`
- FK `password_reset_token_user_id_fkey`: `FOREIGN KEY (user_id) REFERENCES app.app_user(id) ON DELETE CASCADE`
- PK `password_reset_token_pkey`: `PRIMARY KEY (id)`
- UNIQUE `password_reset_token_token_hash_key`: `UNIQUE (token_hash)`
- INDEX: `btree (user_id)`

</details>

### vehicle

A user's vehicle. Plate stored encrypted + keyed hash + masked; ciphertext readable only via `app.reveal_vehicle_plate`.  
RLS: **yes**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `user_id` | uuid | no |  | References `app_user`. |
| `plate_ciphertext` | bytea | no |  | Encrypted plate. Not selectable by the app role (column grant). |
| `plate_key_version` | smallint | no | 1 | Key version for rotation. |
| `plate_hash` | bytea | no |  | HMAC-SHA256 of the normalised plate with a secret pepper; LPR matching. |
| `plate_masked` | text | no |  | Display form, e.g. 30A-•••.45. |
| `size_class_code` | text | no |  | References `size_class`. |
| `is_active` | boolean | no | true | Soft retire flag; rows stay referenced by history. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Last update (trigger `set_updated_at`). |

<details><summary>Constraints and indexes</summary>

- CHECK `vehicle_plate_hash_check`: `CHECK (length(plate_hash) = 32)`
- CHECK `vehicle_plate_key_version_check`: `CHECK (plate_key_version > 0)`
- CHECK `vehicle_plate_masked_check`: `CHECK (btrim(plate_masked) <> ''::text)`
- FK `vehicle_size_class_code_fkey`: `FOREIGN KEY (size_class_code) REFERENCES app.size_class(code) ON DELETE RESTRICT`
- FK `vehicle_user_id_fkey`: `FOREIGN KEY (user_id) REFERENCES app.app_user(id) ON DELETE RESTRICT`
- PK `vehicle_pkey`: `PRIMARY KEY (id)`
- UNIQUE `vehicle_id_user_id_key`: `UNIQUE (id, user_id)`
- INDEX: `btree (plate_hash) WHERE is_active`
- INDEX: `btree (user_id, plate_hash) WHERE is_active`

</details>

## Eligibility (M1)

### asset

Property that confers eligibility (apartment, shophouse, office…). Unit code never leaves its zone (BR-17).  
RLS: **yes**

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
- INDEX: `btree (building_id) WHERE (building_id IS NOT NULL)`

</details>

### eligibility

Tư cách = (asset, role, validity), verified by the BQL of the asset's zone. Source of L1–L4.  
RLS: **yes**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `user_id` | uuid | no |  | References `app_user`. |
| `asset_id` | uuid | no |  | References `asset`. |
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `role` | app.eligibility_role | no |  | owner · tenant · authorized · employee. |
| `valid_during` | tstzrange | no |  | Validity `[from, until)`; open upper = no expiry. Checked at use time (BR-16). |
| `status` | app.eligibility_status | no | 'pending'::app.eligibility_status | pending → verified → revoked/expired. |
| `verified_by` | uuid | yes |  | BQL who verified (required when verified). → `app_user`. |
| `verified_at` | timestamp with time zone | yes |  | Time of the event the name describes (UTC); NULL = not happened. |
| `revoked_at` | timestamp with time zone | yes |  | Time of the event the name describes (UTC); NULL = not happened. |
| `revoke_reason` | text | yes |  | As named. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Last update (trigger `set_updated_at`). |

<details><summary>Constraints and indexes</summary>

- CHECK `eligibility_check`: `CHECK (status <> 'verified'::app.eligibility_status OR verified_by IS NOT NULL AND verified_at IS NOT NULL)`
- CHECK `eligibility_check1`: `CHECK (status <> 'revoked'::app.eligibility_status OR revoked_at IS NOT NULL)`
- CHECK `eligibility_valid_during_check`: `CHECK (NOT isempty(valid_during) AND NOT lower_inf(valid_during))`
- FK `eligibility_asset_id_zone_id_fkey`: `FOREIGN KEY (asset_id, zone_id) REFERENCES app.asset(id, zone_id) ON DELETE RESTRICT`
- FK `eligibility_user_id_fkey`: `FOREIGN KEY (user_id) REFERENCES app.app_user(id) ON DELETE RESTRICT`
- FK `eligibility_verified_by_fkey`: `FOREIGN KEY (verified_by) REFERENCES app.app_user(id) ON DELETE RESTRICT`
- PK `eligibility_pkey`: `PRIMARY KEY (id)`
- EXCLUDE `eligibility_no_overlap`: `EXCLUDE USING gist (user_id WITH =, asset_id WITH =, role WITH =, valid_during WITH &&) WHERE (status = ANY (ARRAY['pending'::app.eligibility_status, 'verified'::app.eligibility_status]))`
- INDEX: `btree (asset_id)`
- INDEX: `btree (upper(valid_during)) WHERE ((status = 'verified'::app.eligibility_status) AND (NOT upper_inf(valid_during)))`
- INDEX: `gist (user_id, valid_during) WHERE (status = 'verified'::app.eligibility_status)`
- INDEX: `btree (zone_id, status)`

</details>

### slot_holding

Who holds the usage right of a TH1/TH2 slot over time (owner/lessee/after swap). Needed to share.  
RLS: **yes**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `slot_id` | uuid | no |  | References `slot`. |
| `slot_type` | app.slot_type | no |  | Value from the fixed set of its type / CHECK (see constraints). |
| `user_id` | uuid | no |  | References `app_user`. |
| `kind` | app.holding_kind | no |  | owner (TH1) · lessee (TH2) · swap_usage (after an approved swap). |
| `held_during` | tstzrange | no |  | Holding period; no overlap per slot (EXCLUDE). |
| `swap_proposal_id` | uuid | yes |  | Swap that created the holding. → `swap_proposal`. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |

<details><summary>Constraints and indexes</summary>

- CHECK `slot_holding_held_during_check`: `CHECK (NOT isempty(held_during) AND NOT lower_inf(held_during))`
- CHECK `slot_holding_type_kind`: `CHECK (slot_type = 'TH1'::app.slot_type AND (kind = ANY (ARRAY['owner'::app.holding_kind, 'swap_usage'::app.holding_kind])) OR slot_type = 'TH2'::app.slot_type AND (kind = ANY (ARRAY['lessee'::app.holding_kind, 'swap_usage'::app.holding_kind])))`
- FK `slot_holding_slot_id_zone_id_slot_type_fkey`: `FOREIGN KEY (slot_id, zone_id, slot_type) REFERENCES app.slot(id, zone_id, slot_type) ON DELETE RESTRICT`
- FK `slot_holding_swap_fk`: `FOREIGN KEY (swap_proposal_id) REFERENCES app.swap_proposal(id) ON DELETE RESTRICT`
- FK `slot_holding_user_id_fkey`: `FOREIGN KEY (user_id) REFERENCES app.app_user(id) ON DELETE RESTRICT`
- PK `slot_holding_pkey`: `PRIMARY KEY (id)`
- EXCLUDE `slot_holding_no_overlap`: `EXCLUDE USING gist (slot_id WITH =, held_during WITH &&)`
- INDEX: `btree (swap_proposal_id) WHERE (swap_proposal_id IS NOT NULL)`
- INDEX: `btree (user_id)`

</details>

## Policy & configuration (M3)

### zone_policy

Versioned zone rules: buffers, thresholds, TTLs, overstay fee. Agreements pin the version used.  
RLS: **yes**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `version` | integer | no |  | Monotonic per zone; a change is a new row. |
| `effective_from` | timestamp with time zone | no |  | Start of validity of this version. |
| `buffer_before` | interval | no |  | Buffer at the start of a share window (FR-06). |
| `buffer_after` | interval | no |  | Buffer before the owner returns (BR-07). |
| `approval_threshold_vnd` | bigint | no |  | Above this, an agreement needs BQL approval (BR-12). |
| `hold_ttl` | interval | no |  | Life of a temporary hold. |
| `agreement_confirm_ttl` | interval | no |  | Time both parties have to confirm. |
| `overstay_grace` | interval | no |  | Grace before overstay is charged. |
| `overstay_fee_per_hour_vnd` | bigint | no |  | Overstay fee (BR-08). |
| `eligibility_grace_max` | interval | yes |  | BR-16 maximum carry-over of a running booking after expiry (TBD; NULL = until booking end). |
| `created_by` | uuid | yes |  | References `app_user`. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |

<details><summary>Constraints and indexes</summary>

- CHECK `zone_policy_agreement_confirm_ttl_check`: `CHECK (agreement_confirm_ttl > '00:00:00'::interval)`
- CHECK `zone_policy_approval_threshold_vnd_check`: `CHECK (approval_threshold_vnd >= 0)`
- CHECK `zone_policy_buffer_after_check`: `CHECK (buffer_after >= '00:00:00'::interval)`
- CHECK `zone_policy_buffer_before_check`: `CHECK (buffer_before >= '00:00:00'::interval)`
- CHECK `zone_policy_hold_ttl_check`: `CHECK (hold_ttl > '00:00:00'::interval)`
- CHECK `zone_policy_overstay_fee_per_hour_vnd_check`: `CHECK (overstay_fee_per_hour_vnd >= 0)`
- CHECK `zone_policy_overstay_grace_check`: `CHECK (overstay_grace >= '00:00:00'::interval)`
- CHECK `zone_policy_version_check`: `CHECK (version > 0)`
- FK `zone_policy_created_by_fkey`: `FOREIGN KEY (created_by) REFERENCES app.app_user(id) ON DELETE SET NULL`
- FK `zone_policy_zone_id_fkey`: `FOREIGN KEY (zone_id) REFERENCES app.zone(id) ON DELETE RESTRICT`
- PK `zone_policy_pkey`: `PRIMARY KEY (id)`
- UNIQUE `zone_policy_id_zone_id_key`: `UNIQUE (id, zone_id)`
- UNIQUE `zone_policy_zone_id_version_key`: `UNIQUE (zone_id, version)`
- INDEX: `btree (zone_id, effective_from DESC)`

</details>

### price_rule

Price per slot type × eligibility level × unit (BR-19), in VND.  
RLS: **yes**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `zone_policy_id` | uuid | no |  | References `zone_policy`. |
| `slot_type` | app.slot_type | no |  | Value from the fixed set of its type / CHECK (see constraints). |
| `level` | app.eligibility_level | no |  | Value from the fixed set of its type / CHECK (see constraints). |
| `unit` | text | no |  | hour \| day. |
| `price_vnd` | bigint | no |  | Amount in VND (integer, ≥ 0). |

<details><summary>Constraints and indexes</summary>

- CHECK `price_rule_price_vnd_check`: `CHECK (price_vnd >= 0)`
- CHECK `price_rule_unit_check`: `CHECK (unit = ANY (ARRAY['hour'::text, 'day'::text]))`
- FK `price_rule_zone_policy_id_fkey`: `FOREIGN KEY (zone_policy_id) REFERENCES app.zone_policy(id) ON DELETE CASCADE`
- PK `price_rule_pkey`: `PRIMARY KEY (id)`
- UNIQUE `price_rule_zone_policy_id_slot_type_level_unit_key`: `UNIQUE (zone_policy_id, slot_type, level, unit)`

</details>

### agreement_template

Versioned agreement template of a zone (FR-08).  
RLS: **yes**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `version` | integer | no |  | Version number, increasing per parent. |
| `body_md` | text | no |  | As named. |
| `effective_from` | timestamp with time zone | no |  | Start of validity of this version. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |

<details><summary>Constraints and indexes</summary>

- CHECK `agreement_template_body_md_check`: `CHECK (btrim(body_md) <> ''::text)`
- CHECK `agreement_template_version_check`: `CHECK (version > 0)`
- FK `agreement_template_zone_id_fkey`: `FOREIGN KEY (zone_id) REFERENCES app.zone(id) ON DELETE RESTRICT`
- PK `agreement_template_pkey`: `PRIMARY KEY (id)`
- UNIQUE `agreement_template_id_zone_id_key`: `UNIQUE (id, zone_id)`
- UNIQUE `agreement_template_zone_id_version_key`: `UNIQUE (zone_id, version)`

</details>

### holiday

Chain holiday calendar for N4 forecasts (`day_kind = holiday`).  
RLS: **no**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `chain_id` | uuid | no |  | References `chain`. |
| `day` | date | no |  | As named. |
| `name` | text | no |  | Display name. |

<details><summary>Constraints and indexes</summary>

- FK `holiday_chain_id_fkey`: `FOREIGN KEY (chain_id) REFERENCES app.chain(id) ON DELETE CASCADE`
- PK `holiday_pkey`: `PRIMARY KEY (chain_id, day)`

</details>

## Sharing & booking (M4, M5)

### share_window

Owner publishes an away window; `bookable_period` = window minus buffers (FR-05/06).  
RLS: **yes**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `slot_id` | uuid | no |  | References `slot`. |
| `owner_user_id` | uuid | no |  | References `app_user`. |
| `period` | tstzrange | no |  | Window the owner is away. |
| `bookable_period` | tstzrange | no |  | Period minus buffers; bookings must lie inside it. |
| `open_scope` | app.open_scope | no |  | Owner-chosen scope ≤ pool max (AC-23). |
| `status` | app.share_status | no | 'open'::app.share_status | Value from the fixed set of its type / CHECK (see constraints). |
| `returned_at` | timestamp with time zone | yes |  | Early return time (W3). |
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
- EXCLUDE `share_window_no_overlap`: `EXCLUDE USING gist (slot_id WITH =, period WITH &&) WHERE (status = 'open'::app.share_status)`
- INDEX: `gist (zone_id, bookable_period) WHERE (status = 'open'::app.share_status)`
- INDEX: `btree (owner_user_id, lower(period) DESC)`

</details>

### parking_request

Every request with its derived level and outcome, including blocked ones (KPI, AC-03).  
RLS: **yes**

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
- CHECK `parking_request_requested_period_check`: `CHECK (app.is_finite_range(requested_period) AND (upper(requested_period) - lower(requested_period)) <= '31 days'::interval)`
- FK `parking_request_building_id_zone_id_fkey`: `FOREIGN KEY (building_id, zone_id) REFERENCES app.building(id, zone_id) ON DELETE RESTRICT`
- FK `parking_request_requester_user_id_fkey`: `FOREIGN KEY (requester_user_id) REFERENCES app.app_user(id) ON DELETE RESTRICT`
- FK `parking_request_vehicle_id_requester_user_id_fkey`: `FOREIGN KEY (vehicle_id, requester_user_id) REFERENCES app.vehicle(id, user_id) ON DELETE RESTRICT`
- PK `parking_request_pkey`: `PRIMARY KEY (id)`
- UNIQUE `parking_request_idempotency_key_key`: `UNIQUE (idempotency_key)`
- INDEX: `btree (zone_id, created_at, outcome)`
- INDEX: `btree (requester_user_id, created_at DESC)`

</details>

### booking

A reservation of a slot for a period. EXCLUDE constraint makes double booking impossible.  
RLS: **yes**

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
| `status` | app.booking_status | no | 'held'::app.booking_status | held → pending_agreement → pending_approval → confirmed → completed; or relocated/cancelled/expired/rejected. |
| `hold_expires_at` | timestamp with time zone | yes |  | Required while held. |
| `relocated_from_booking_id` | uuid | yes |  | Original booking when this is a TH3 replacement after early return. → `booking`. |
| `idempotency_key` | text | no |  | Caller-supplied key (`thread_id:step`); replays hit the UNIQUE constraint. |
| `version` | integer | no | 1 | Optimistic lock for user-driven edits. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Last update (trigger `set_updated_at`). |

<details><summary>Constraints and indexes</summary>

- CHECK `booking_check`: `CHECK ((share_window_id IS NULL) = (provider_user_id IS NULL))`
- CHECK `booking_check1`: `CHECK (provider_user_id IS NULL OR provider_user_id <> renter_user_id)`
- CHECK `booking_check2`: `CHECK (status <> 'held'::app.booking_status OR hold_expires_at IS NOT NULL)`
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
- EXCLUDE `booking_no_overlap`: `EXCLUDE USING gist (slot_id WITH =, period WITH &&) WHERE (status = ANY (ARRAY['held'::app.booking_status, 'pending_agreement'::app.booking_status, 'pending_approval'::app.booking_status, 'confirmed'::app.booking_status]))`
- INDEX: `btree (zone_id, upper(period)) WHERE (status = 'confirmed'::app.booking_status)`
- INDEX: `btree (hold_expires_at) WHERE (status = 'held'::app.booking_status)`
- INDEX: `btree (provider_user_id, lower(period) DESC) WHERE (provider_user_id IS NOT NULL)`
- INDEX: `btree (relocated_from_booking_id) WHERE (relocated_from_booking_id IS NOT NULL)`
- INDEX: `btree (renter_user_id, lower(period) DESC)`
- INDEX: `btree (request_id) WHERE (request_id IS NOT NULL)`
- INDEX: `btree (share_window_id) WHERE (share_window_id IS NOT NULL)`
- INDEX: `btree (vehicle_id)`

</details>

## Agreement & ledger (M6)

### agreement

Electronic agreement for a TH1/TH2 booking (FR-08); effective only after both confirmations (+ approval if over threshold).  
RLS: **yes**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `booking_id` | uuid | no |  | References `booking`. |
| `template_id` | uuid | no |  | References `agreement_template`. |
| `zone_policy_id` | uuid | no |  | Policy version that priced it. → `zone_policy`. |
| `provider_user_id` | uuid | no |  | References `app_user`. |
| `renter_user_id` | uuid | no |  | References `app_user`. |
| `price_vnd` | bigint | no |  | Amount in VND (integer, ≥ 0). |
| `body_rendered` | text | no |  | Exact text both parties confirmed. |
| `body_sha256` | bytea | no |  | Hash of the rendered text (put into the ledger payload). |
| `status` | app.agreement_status | no | 'pending_confirmation'::app.agreement_status | Value from the fixed set of its type / CHECK (see constraints). |
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
- CHECK `agreement_check`: `CHECK (status <> 'effective'::app.agreement_status OR provider_confirmed_at IS NOT NULL AND renter_confirmed_at IS NOT NULL AND effective_at IS NOT NULL AND (NOT requires_approval OR approval_request_id IS NOT NULL))`
- CHECK `agreement_check1`: `CHECK (status <> 'pending_approval'::app.agreement_status OR requires_approval AND approval_request_id IS NOT NULL)`
- CHECK `agreement_price_vnd_check`: `CHECK (price_vnd >= 0)`
- FK `agreement_approval_request_id_zone_id_fkey`: `FOREIGN KEY (approval_request_id, zone_id) REFERENCES app.approval_request(id, zone_id) ON DELETE RESTRICT`
- FK `agreement_booking_id_zone_id_fkey`: `FOREIGN KEY (booking_id, zone_id) REFERENCES app.booking(id, zone_id) ON DELETE RESTRICT`
- FK `agreement_provider_user_id_fkey`: `FOREIGN KEY (provider_user_id) REFERENCES app.app_user(id) ON DELETE RESTRICT`
- FK `agreement_renter_user_id_fkey`: `FOREIGN KEY (renter_user_id) REFERENCES app.app_user(id) ON DELETE RESTRICT`
- FK `agreement_template_id_zone_id_fkey`: `FOREIGN KEY (template_id, zone_id) REFERENCES app.agreement_template(id, zone_id) ON DELETE RESTRICT`
- FK `agreement_zone_policy_id_zone_id_fkey`: `FOREIGN KEY (zone_policy_id, zone_id) REFERENCES app.zone_policy(id, zone_id) ON DELETE RESTRICT`
- PK `agreement_pkey`: `PRIMARY KEY (id)`
- UNIQUE `agreement_booking_id_key`: `UNIQUE (booking_id)`
- UNIQUE `agreement_id_zone_id_key`: `UNIQUE (id, zone_id)`
- INDEX: `btree (approval_request_id) WHERE (approval_request_id IS NOT NULL)`
- INDEX: `btree (confirm_deadline) WHERE (status = 'pending_confirmation'::app.agreement_status)`
- INDEX: `btree (zone_policy_id)`
- INDEX: `btree (provider_user_id)`
- INDEX: `btree (renter_user_id)`
- INDEX: `btree (template_id)`

</details>

### otp_challenge

OTP used to confirm an agreement (ADR-0006): hashed, expiring, limited attempts.  
RLS: **yes**

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

- CHECK `otp_challenge_check`: `CHECK (attempts >= 0 AND attempts <= max_attempts)`
- CHECK `otp_challenge_code_hash_check`: `CHECK (length(code_hash) = 32)`
- CHECK `otp_challenge_max_attempts_check`: `CHECK (max_attempts >= 1 AND max_attempts <= 10)`
- CHECK `otp_challenge_purpose_check`: `CHECK (purpose = 'agreement_confirm'::text)`
- FK `otp_challenge_user_id_fkey`: `FOREIGN KEY (user_id) REFERENCES app.app_user(id) ON DELETE CASCADE`
- PK `otp_challenge_pkey`: `PRIMARY KEY (id)`
- INDEX: `btree (user_id, purpose, subject_id) WHERE (consumed_at IS NULL)`

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
RLS: **yes**

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
- CHECK `ledger_entry_subject_type_check`: `CHECK (subject_type = ANY (ARRAY['agreement'::text, 'booking'::text, 'payment'::text, 'overstay_case'::text, 'swap_proposal'::text]))`
- FK `ledger_entry_zone_id_fkey`: `FOREIGN KEY (zone_id) REFERENCES app.zone(id) ON DELETE RESTRICT`
- PK `ledger_entry_pkey`: `PRIMARY KEY (zone_id, seq)`
- UNIQUE `ledger_entry_idempotency_key_key`: `UNIQUE (idempotency_key)`
- INDEX: `btree (subject_type, subject_id)`
- INDEX: `btree (zone_id, created_at)`

</details>

## Payment & vouchers (M7)

### voucher

Shophouse voucher for a guest's TH3 visit (FR-22). Never changes eligibility.  
RLS: **yes**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `issuer_user_id` | uuid | no |  | References `app_user`. |
| `issuer_asset_id` | uuid | no |  | Shophouse that issued it. → `asset`. |
| `code` | text | no |  | Random unguessable code XXXX-XXXX-XXXX. |
| `value_vnd` | bigint | no |  | Amount in VND (integer, ≥ 0). |
| `valid_until` | timestamp with time zone | no |  | Time of the event the name describes (UTC); NULL = not happened. |
| `status` | app.voucher_status | no | 'issued'::app.voucher_status | Value from the fixed set of its type / CHECK (see constraints). |
| `redeemed_at` | timestamp with time zone | yes |  | Time of the event the name describes (UTC); NULL = not happened. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Last update (trigger `set_updated_at`). |

<details><summary>Constraints and indexes</summary>

- CHECK `voucher_check`: `CHECK ((status = 'redeemed'::app.voucher_status) = (redeemed_at IS NOT NULL))`
- CHECK `voucher_code_check`: `CHECK (code ~ '^[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$'::text)`
- CHECK `voucher_value_vnd_check`: `CHECK (value_vnd > 0)`
- FK `voucher_issuer_asset_id_zone_id_fkey`: `FOREIGN KEY (issuer_asset_id, zone_id) REFERENCES app.asset(id, zone_id) ON DELETE RESTRICT`
- FK `voucher_issuer_user_id_fkey`: `FOREIGN KEY (issuer_user_id) REFERENCES app.app_user(id) ON DELETE RESTRICT`
- PK `voucher_pkey`: `PRIMARY KEY (id)`
- UNIQUE `voucher_code_key`: `UNIQUE (code)`
- UNIQUE `voucher_id_zone_id_key`: `UNIQUE (id, zone_id)`
- INDEX: `btree (issuer_asset_id)`
- INDEX: `btree (issuer_user_id, created_at DESC)`

</details>

### payment

Simulated VietQR payment (A-05). `amount_vnd` is generated.  
RLS: **yes**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `booking_id` | uuid | no |  | References `booking`. |
| `payer_user_id` | uuid | no |  | References `app_user`. |
| `kind` | app.payment_kind | no |  | Value from the fixed set of its type / CHECK (see constraints). |
| `gross_vnd` | bigint | no |  | Amount before voucher. |
| `discount_vnd` | bigint | no | 0 | Amount in VND (integer, ≥ 0). |
| `amount_vnd` | bigint | yes | generated | Generated: gross − discount. |
| `voucher_id` | uuid | yes |  | References `voucher`. |
| `provider` | text | no | 'vietqr_mock'::text | Only `vietqr_mock` (A-05). |
| `status` | app.payment_status | no | 'pending'::app.payment_status | Value from the fixed set of its type / CHECK (see constraints). |
| `idempotency_key` | text | no |  | Caller-supplied key (`thread_id:step`); replays hit the UNIQUE constraint. |
| `paid_at` | timestamp with time zone | yes |  | Time of the event the name describes (UTC); NULL = not happened. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Last update (trigger `set_updated_at`). |

<details><summary>Constraints and indexes</summary>

- CHECK `payment_check`: `CHECK (discount_vnd <= gross_vnd)`
- CHECK `payment_check1`: `CHECK (voucher_id IS NOT NULL OR discount_vnd = 0)`
- CHECK `payment_check2`: `CHECK (voucher_id IS NULL OR kind = 'th3_visit'::app.payment_kind)`
- CHECK `payment_check3`: `CHECK ((status = 'paid_simulated'::app.payment_status) = (paid_at IS NOT NULL))`
- CHECK `payment_discount_vnd_check`: `CHECK (discount_vnd >= 0)`
- CHECK `payment_gross_vnd_check`: `CHECK (gross_vnd >= 0)`
- CHECK `payment_provider_check`: `CHECK (provider = 'vietqr_mock'::text)`
- FK `payment_booking_id_zone_id_fkey`: `FOREIGN KEY (booking_id, zone_id) REFERENCES app.booking(id, zone_id) ON DELETE RESTRICT`
- FK `payment_payer_user_id_fkey`: `FOREIGN KEY (payer_user_id) REFERENCES app.app_user(id) ON DELETE RESTRICT`
- FK `payment_voucher_id_zone_id_fkey`: `FOREIGN KEY (voucher_id, zone_id) REFERENCES app.voucher(id, zone_id) ON DELETE RESTRICT`
- PK `payment_pkey`: `PRIMARY KEY (id)`
- UNIQUE `payment_idempotency_key_key`: `UNIQUE (idempotency_key)`
- UNIQUE `payment_voucher_id_key`: `UNIQUE (voucher_id)`
- INDEX: `btree (booking_id)`
- INDEX: `btree (booking_id, kind) WHERE (status = 'paid_simulated'::app.payment_status)`
- INDEX: `btree (payer_user_id, created_at DESC)`

</details>

## Access / LPR (M8, M9)

### lpr_source

Configured LPR feed of a zone (webhook/MQTT/DB/CSV/simulated) with its OCR review threshold.  
RLS: **yes**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `kind` | app.lpr_source_kind | no |  | Value from the fixed set of its type / CHECK (see constraints). |
| `name` | text | no |  | Display name. |
| `ocr_review_threshold` | numeric(4,3) | no | 0.800 | Below this confidence an event goes to manual review. |
| `is_active` | boolean | no | true | Soft retire flag; rows stay referenced by history. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |

<details><summary>Constraints and indexes</summary>

- CHECK `lpr_source_ocr_review_threshold_check`: `CHECK (ocr_review_threshold >= 0::numeric AND ocr_review_threshold <= 1::numeric)`
- FK `lpr_source_zone_id_fkey`: `FOREIGN KEY (zone_id) REFERENCES app.zone(id) ON DELETE RESTRICT`
- PK `lpr_source_pkey`: `PRIMARY KEY (id)`
- UNIQUE `lpr_source_id_zone_id_key`: `UNIQUE (id, zone_id)`
- UNIQUE `lpr_source_zone_id_name_key`: `UNIQUE (zone_id, name)`

</details>

### lpr_event

Normalised LPR event. Partitioned monthly by `occurred_at`; deduplicated per source event (BR-13).  
RLS: **yes**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | bigint | no | nextval('app.lpr_event_id_seq'::regclass) | Primary key (UUIDv7 unless the type says bigint). |
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `source_id` | uuid | no |  | References `lpr_source`. |
| `source_event_id` | text | no |  | Vendor event id; dedupe key with source and time. |
| `gate_id` | uuid | no |  | References `gate`. |
| `direction` | app.gate_direction | no |  | Value from the fixed set of its type / CHECK (see constraints). |
| `occurred_at` | timestamp with time zone | no |  | Event time at the gate; partition key. |
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
- CHECK `lpr_event_check1`: `CHECK ((status <> ALL (ARRAY['confirmed_manual'::app.lpr_status, 'unreadable'::app.lpr_status])) OR reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)`
- CHECK `lpr_event_ocr_confidence_check`: `CHECK (ocr_confidence >= 0::numeric AND ocr_confidence <= 1::numeric)`
- CHECK `lpr_event_plate_hash_check`: `CHECK (plate_hash IS NULL OR length(plate_hash) = 32)`
- CHECK `lpr_event_source_event_id_check`: `CHECK (length(source_event_id) >= 1 AND length(source_event_id) <= 128)`
- FK `lpr_event_gate_id_zone_id_fkey`: `FOREIGN KEY (gate_id, zone_id) REFERENCES app.gate(id, zone_id) ON DELETE RESTRICT`
- FK `lpr_event_matched_booking_id_fkey`: `FOREIGN KEY (matched_booking_id) REFERENCES app.booking(id) ON DELETE SET NULL`
- FK `lpr_event_matched_vehicle_id_fkey`: `FOREIGN KEY (matched_vehicle_id) REFERENCES app.vehicle(id) ON DELETE SET NULL`
- FK `lpr_event_reviewed_by_fkey`: `FOREIGN KEY (reviewed_by) REFERENCES app.app_user(id) ON DELETE SET NULL`
- FK `lpr_event_source_id_zone_id_fkey`: `FOREIGN KEY (source_id, zone_id) REFERENCES app.lpr_source(id, zone_id) ON DELETE RESTRICT`
- PK `lpr_event_pkey`: `PRIMARY KEY (id, occurred_at)`
- UNIQUE `lpr_event_source_id_source_event_id_occurred_at_key`: `UNIQUE (source_id, source_event_id, occurred_at)`
- INDEX: `btree (matched_booking_id) WHERE (matched_booking_id IS NOT NULL)`
- INDEX: `btree (plate_hash, occurred_at DESC) WHERE (plate_hash IS NOT NULL)`
- INDEX: `btree (zone_id, occurred_at) WHERE (status = 'pending_review'::app.lpr_status)`
- INDEX: `btree (matched_vehicle_id) WHERE (matched_vehicle_id IS NOT NULL)`
- INDEX: `btree (zone_id, occurred_at DESC)`

</details>

### parking_session

Entry/exit pair derived from LPR by N1, optionally matched to a booking.  
RLS: **yes**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `booking_id` | uuid | yes |  | References `booking`. |
| `vehicle_id` | uuid | yes |  | References `vehicle`. |
| `entry_event_id` | bigint | no |  | lpr_event.id of the entry (no FK: partitioned high-churn parent). |
| `exit_event_id` | bigint | yes |  | As named. |
| `entered_at` | timestamp with time zone | no |  | Time of the event the name describes (UTC); NULL = not happened. |
| `exited_at` | timestamp with time zone | yes |  | Time of the event the name describes (UTC); NULL = not happened. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Last update (trigger `set_updated_at`). |

<details><summary>Constraints and indexes</summary>

- CHECK `parking_session_check`: `CHECK ((exit_event_id IS NULL) = (exited_at IS NULL))`
- CHECK `parking_session_check1`: `CHECK (exited_at IS NULL OR exited_at >= entered_at)`
- FK `parking_session_booking_id_fkey`: `FOREIGN KEY (booking_id) REFERENCES app.booking(id) ON DELETE RESTRICT`
- FK `parking_session_vehicle_id_fkey`: `FOREIGN KEY (vehicle_id) REFERENCES app.vehicle(id) ON DELETE RESTRICT`
- FK `parking_session_zone_id_fkey`: `FOREIGN KEY (zone_id) REFERENCES app.zone(id) ON DELETE RESTRICT`
- PK `parking_session_pkey`: `PRIMARY KEY (id)`
- UNIQUE `parking_session_zone_id_entry_event_id_key`: `UNIQUE (zone_id, entry_event_id)`
- INDEX: `btree (booking_id) WHERE (booking_id IS NOT NULL)`
- INDEX: `btree (zone_id, vehicle_id) WHERE (exited_at IS NULL)`
- INDEX: `btree (vehicle_id, entered_at DESC)`

</details>

### overstay_case

One overstay case per booking (FR-11/12); N2 creates, W4 reminds and charges.  
RLS: **yes**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `booking_id` | uuid | no |  | References `booking`. |
| `detected_at` | timestamp with time zone | no |  | Time of the event the name describes (UTC); NULL = not happened. |
| `reminder_count` | smallint | no | 0 | Reminders sent so far. |
| `last_reminded_at` | timestamp with time zone | yes |  | Time of the event the name describes (UTC); NULL = not happened. |
| `ended_at` | timestamp with time zone | yes |  | Time of the event the name describes (UTC); NULL = not happened. |
| `overstay_minutes` | integer | yes |  | As named. |
| `fee_vnd` | bigint | yes |  | Amount in VND (integer, ≥ 0). |
| `status` | app.overstay_status | no | 'open'::app.overstay_status | Value from the fixed set of its type / CHECK (see constraints). |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Last update (trigger `set_updated_at`). |

<details><summary>Constraints and indexes</summary>

- CHECK `overstay_case_check`: `CHECK (status <> 'charged'::app.overstay_status OR fee_vnd IS NOT NULL)`
- CHECK `overstay_case_fee_vnd_check`: `CHECK (fee_vnd >= 0)`
- CHECK `overstay_case_overstay_minutes_check`: `CHECK (overstay_minutes >= 0)`
- CHECK `overstay_case_reminder_count_check`: `CHECK (reminder_count >= 0)`
- FK `overstay_case_booking_id_zone_id_fkey`: `FOREIGN KEY (booking_id, zone_id) REFERENCES app.booking(id, zone_id) ON DELETE RESTRICT`
- PK `overstay_case_pkey`: `PRIMARY KEY (id)`
- UNIQUE `overstay_case_booking_id_key`: `UNIQUE (booking_id)`
- INDEX: `btree (zone_id, detected_at) WHERE (status = 'open'::app.overstay_status)`

</details>

### plate_access_log

Every read of an original plate (AC-12). Append-only.  
RLS: **yes**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | bigint | no | identity | Primary key (UUIDv7 unless the type says bigint). |
| `zone_id` | uuid | yes |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `viewer_user_id` | uuid | no |  | References `app_user`. |
| `subject_type` | text | no |  | Value from the fixed set of its type / CHECK (see constraints). |
| `subject_ref` | text | no |  | Id of the record whose plate was revealed. |
| `reason` | text | no |  | Mandatory reason (≥ 5 chars). |
| `viewed_at` | timestamp with time zone | no | now() | Time of the event the name describes (UTC); NULL = not happened. |

<details><summary>Constraints and indexes</summary>

- CHECK `plate_access_log_reason_check`: `CHECK (length(btrim(reason)) >= 5)`
- CHECK `plate_access_log_subject_type_check`: `CHECK (subject_type = ANY (ARRAY['lpr_event'::text, 'vehicle'::text, 'dispute_evidence'::text]))`
- FK `plate_access_log_viewer_user_id_fkey`: `FOREIGN KEY (viewer_user_id) REFERENCES app.app_user(id) ON DELETE RESTRICT`
- FK `plate_access_log_zone_id_fkey`: `FOREIGN KEY (zone_id) REFERENCES app.zone(id) ON DELETE RESTRICT`
- PK `plate_access_log_pkey`: `PRIMARY KEY (id)`
- INDEX: `btree (viewer_user_id)`
- INDEX: `btree (zone_id, viewed_at DESC)`

</details>

## Disputes (M10)

### dispute_category

Lookup: dispute categories (catalogue TBD in docs).  
RLS: **no**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `code` | text | no |  | Business code, unique within its parent. |
| `label_vi` | text | no |  | As named. |

<details><summary>Constraints and indexes</summary>

- CHECK `dispute_category_code_check`: `CHECK (code ~ '^[a-z_]{2,40}$'::text)`
- PK `dispute_category_pkey`: `PRIMARY KEY (code)`

</details>

### dispute_ticket

Dispute ticket routed to the BQL of the slot's zone (BR-18). AI summary is a suggestion only.  
RLS: **yes**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `ref_no` | bigint | no | identity | Human-readable number shown in the UI (GD-/TC-/HD- prefixes). |
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `slot_id` | uuid | no |  | References `slot`. |
| `booking_id` | uuid | yes |  | References `booking`. |
| `source` | app.dispute_source | no |  | app (user report) · lpr (detected). |
| `category_code` | text | no |  | References `dispute_category`. |
| `description` | text | yes |  | As named. |
| `status` | app.dispute_status | no | 'open'::app.dispute_status | Value from the fixed set of its type / CHECK (see constraints). |
| `ai_summary` | text | yes |  | Pseudonymised LLM summary — suggestion, not a verdict (BR-14). |
| `ai_confidence` | numeric(4,3) | yes |  | Confidence attached to the AI summary (0–1). |
| `resolution_code` | text | yes |  | Outcome catalogue TBD. |
| `resolution_note` | text | yes |  | As named. |
| `resolved_by` | uuid | yes |  | References `app_user`. |
| `resolved_at` | timestamp with time zone | yes |  | Time of the event the name describes (UTC); NULL = not happened. |
| `idempotency_key` | text | no |  | Caller-supplied key (`thread_id:step`); replays hit the UNIQUE constraint. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Last update (trigger `set_updated_at`). |

<details><summary>Constraints and indexes</summary>

- CHECK `dispute_ticket_ai_confidence_check`: `CHECK (ai_confidence >= 0::numeric AND ai_confidence <= 1::numeric)`
- CHECK `dispute_ticket_check`: `CHECK ((status = ANY (ARRAY['resolved'::app.dispute_status, 'dismissed'::app.dispute_status])) = (resolved_by IS NOT NULL AND resolved_at IS NOT NULL))`
- FK `dispute_ticket_booking_id_zone_id_fkey`: `FOREIGN KEY (booking_id, zone_id) REFERENCES app.booking(id, zone_id) ON DELETE RESTRICT`
- FK `dispute_ticket_category_code_fkey`: `FOREIGN KEY (category_code) REFERENCES app.dispute_category(code) ON DELETE RESTRICT`
- FK `dispute_ticket_resolved_by_fkey`: `FOREIGN KEY (resolved_by) REFERENCES app.app_user(id) ON DELETE RESTRICT`
- FK `dispute_ticket_slot_id_zone_id_fkey`: `FOREIGN KEY (slot_id, zone_id) REFERENCES app.slot(id, zone_id) ON DELETE RESTRICT`
- PK `dispute_ticket_pkey`: `PRIMARY KEY (id)`
- UNIQUE `dispute_ticket_id_zone_id_key`: `UNIQUE (id, zone_id)`
- UNIQUE `dispute_ticket_idempotency_key_key`: `UNIQUE (idempotency_key)`
- UNIQUE `dispute_ticket_ref_no_key`: `UNIQUE (ref_no)`
- INDEX: `btree (booking_id) WHERE (booking_id IS NOT NULL)`
- INDEX: `btree (zone_id, status, created_at DESC)`
- INDEX: `btree (slot_id, created_at DESC)`

</details>

### dispute_party

Users involved in a ticket (reporter/respondent). Used for access and N5 repeat detection.  
RLS: **yes**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `ticket_id` | uuid | no |  | References `dispute_ticket`. |
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `user_id` | uuid | no |  | References `app_user`. |
| `role` | text | no |  | Value from the fixed set of its type / CHECK (see constraints). |

<details><summary>Constraints and indexes</summary>

- CHECK `dispute_party_role_check`: `CHECK (role = ANY (ARRAY['reporter'::text, 'respondent'::text]))`
- FK `dispute_party_ticket_id_zone_id_fkey`: `FOREIGN KEY (ticket_id, zone_id) REFERENCES app.dispute_ticket(id, zone_id) ON DELETE CASCADE`
- FK `dispute_party_user_id_fkey`: `FOREIGN KEY (user_id) REFERENCES app.app_user(id) ON DELETE RESTRICT`
- PK `dispute_party_pkey`: `PRIMARY KEY (ticket_id, user_id)`
- INDEX: `btree (user_id)`

</details>

### dispute_evidence

Evidence: photo object keys in S3 (original key column-restricted), LPR event or ledger entry.  
RLS: **yes**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `ticket_id` | uuid | no |  | References `dispute_ticket`. |
| `kind` | app.evidence_kind | no |  | Value from the fixed set of its type / CHECK (see constraints). |
| `object_key_original` | text | yes |  | S3 key of the unmasked photo; column-restricted. |
| `object_key_masked` | text | yes |  | S3 key of the plate-masked photo. |
| `sha256` | bytea | yes |  | SHA-256 digest (32 bytes); the clear value is never stored. |
| `lpr_event_id` | bigint | yes |  | As named. |
| `lpr_occurred_at` | timestamp with time zone | yes |  | Time of the event the name describes (UTC); NULL = not happened. |
| `ledger_seq` | bigint | yes |  | As named. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |

<details><summary>Constraints and indexes</summary>

- CHECK `dispute_evidence_check`: `CHECK (kind = 'photo'::app.evidence_kind AND object_key_original IS NOT NULL AND object_key_masked IS NOT NULL AND sha256 IS NOT NULL OR kind = 'lpr_event'::app.evidence_kind AND lpr_event_id IS NOT NULL AND lpr_occurred_at IS NOT NULL OR kind = 'ledger_entry'::app.evidence_kind AND ledger_seq IS NOT NULL)`
- CHECK `dispute_evidence_sha256_check`: `CHECK (sha256 IS NULL OR length(sha256) = 32)`
- FK `dispute_evidence_ticket_id_zone_id_fkey`: `FOREIGN KEY (ticket_id, zone_id) REFERENCES app.dispute_ticket(id, zone_id) ON DELETE CASCADE`
- FK `dispute_evidence_zone_id_ledger_seq_fkey`: `FOREIGN KEY (zone_id, ledger_seq) REFERENCES app.ledger_entry(zone_id, seq) ON DELETE RESTRICT`
- PK `dispute_evidence_pkey`: `PRIMARY KEY (id)`
- INDEX: `btree (ticket_id)`

</details>

## Swaps (M11)

### swap_need

A user's registered need to change slot (US-14).  
RLS: **yes**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `user_id` | uuid | no |  | References `app_user`. |
| `current_slot_id` | uuid | no |  | References `slot`. |
| `desired_size_class` | text | yes |  | References `size_class`. |
| `note` | text | yes |  | As named. |
| `status` | app.need_status | no | 'open'::app.need_status | Value from the fixed set of its type / CHECK (see constraints). |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Last update (trigger `set_updated_at`). |

<details><summary>Constraints and indexes</summary>

- FK `swap_need_current_slot_id_zone_id_fkey`: `FOREIGN KEY (current_slot_id, zone_id) REFERENCES app.slot(id, zone_id) ON DELETE RESTRICT`
- FK `swap_need_desired_size_class_fkey`: `FOREIGN KEY (desired_size_class) REFERENCES app.size_class(code) ON DELETE RESTRICT`
- FK `swap_need_user_id_fkey`: `FOREIGN KEY (user_id) REFERENCES app.app_user(id) ON DELETE RESTRICT`
- PK `swap_need_pkey`: `PRIMARY KEY (id)`
- INDEX: `btree (user_id, current_slot_id) WHERE (status = 'open'::app.need_status)`
- INDEX: `btree (zone_id) WHERE (status = 'open'::app.need_status)`

</details>

### swap_proposal

Swap proposal in one zone (BR-10); applied only after BQL approval (FR-18).  
RLS: **yes**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `ref_no` | bigint | no | identity | Human-readable number shown in the UI (GD-/TC-/HD- prefixes). |
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `kind` | app.swap_kind | no |  | Value from the fixed set of its type / CHECK (see constraints). |
| `status` | app.swap_status | no | 'pending_approval'::app.swap_status | Value from the fixed set of its type / CHECK (see constraints). |
| `reason` | text | no |  | As named. |
| `score` | numeric(6,3) | yes |  | Matching score from W6 (deterministic). |
| `approval_request_id` | uuid | yes |  | References `approval_request`. |
| `effective_from` | timestamp with time zone | yes |  | Start of validity of this version. |
| `applied_at` | timestamp with time zone | yes |  | Time of the event the name describes (UTC); NULL = not happened. |
| `idempotency_key` | text | no |  | Caller-supplied key (`thread_id:step`); replays hit the UNIQUE constraint. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Last update (trigger `set_updated_at`). |

<details><summary>Constraints and indexes</summary>

- CHECK `swap_proposal_check`: `CHECK ((status <> ALL (ARRAY['approved'::app.swap_status, 'applied'::app.swap_status])) OR approval_request_id IS NOT NULL)`
- CHECK `swap_proposal_check1`: `CHECK ((status = 'applied'::app.swap_status) = (applied_at IS NOT NULL))`
- FK `swap_proposal_approval_request_id_zone_id_fkey`: `FOREIGN KEY (approval_request_id, zone_id) REFERENCES app.approval_request(id, zone_id) ON DELETE RESTRICT`
- FK `swap_proposal_zone_id_fkey`: `FOREIGN KEY (zone_id) REFERENCES app.zone(id) ON DELETE RESTRICT`
- PK `swap_proposal_pkey`: `PRIMARY KEY (id)`
- UNIQUE `swap_proposal_id_zone_id_key`: `UNIQUE (id, zone_id)`
- UNIQUE `swap_proposal_idempotency_key_key`: `UNIQUE (idempotency_key)`
- UNIQUE `swap_proposal_ref_no_key`: `UNIQUE (ref_no)`
- INDEX: `btree (approval_request_id) WHERE (approval_request_id IS NOT NULL)`
- INDEX: `btree (zone_id, status, created_at DESC)`

</details>

### swap_leg

One slot moving from one user to another inside a proposal. Same zone enforced by FK.  
RLS: **yes**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `proposal_id` | uuid | no |  | References `swap_proposal`. |
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `slot_id` | uuid | no |  | References `slot`. |
| `from_user_id` | uuid | no |  | References `app_user`. |
| `to_user_id` | uuid | no |  | References `app_user`. |
| `ordinal` | smallint | no |  | Order of the leg in a chain swap. |

<details><summary>Constraints and indexes</summary>

- CHECK `swap_leg_check`: `CHECK (from_user_id <> to_user_id)`
- CHECK `swap_leg_ordinal_check`: `CHECK (ordinal >= 1)`
- FK `swap_leg_from_user_id_fkey`: `FOREIGN KEY (from_user_id) REFERENCES app.app_user(id) ON DELETE RESTRICT`
- FK `swap_leg_proposal_id_zone_id_fkey`: `FOREIGN KEY (proposal_id, zone_id) REFERENCES app.swap_proposal(id, zone_id) ON DELETE CASCADE`
- FK `swap_leg_slot_id_zone_id_fkey`: `FOREIGN KEY (slot_id, zone_id) REFERENCES app.slot(id, zone_id) ON DELETE RESTRICT`
- FK `swap_leg_to_user_id_fkey`: `FOREIGN KEY (to_user_id) REFERENCES app.app_user(id) ON DELETE RESTRICT`
- PK `swap_leg_pkey`: `PRIMARY KEY (proposal_id, slot_id)`
- UNIQUE `swap_leg_proposal_id_ordinal_key`: `UNIQUE (proposal_id, ordinal)`
- INDEX: `btree (from_user_id)`
- INDEX: `btree (slot_id)`
- INDEX: `btree (to_user_id)`

</details>

## Approvals (M12)

### approval_request

HITL queue item for the BQL of the slot's zone; carries the LangGraph `thread_id` to resume.  
RLS: **yes**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `kind` | app.approval_kind | no |  | Value from the fixed set of its type / CHECK (see constraints). |
| `subject_id` | uuid | no |  | Agreement / dispute / swap / booking under review. |
| `thread_id` | text | no |  | LangGraph thread resumed after the decision. |
| `status` | app.approval_status | no | 'pending'::app.approval_status | Value from the fixed set of its type / CHECK (see constraints). |
| `summary` | text | yes |  | As named. |
| `requested_at` | timestamp with time zone | no | now() | Time of the event the name describes (UTC); NULL = not happened. |
| `due_at` | timestamp with time zone | yes |  | Time of the event the name describes (UTC); NULL = not happened. |
| `decided_by` | uuid | yes |  | References `app_user`. |
| `decided_at` | timestamp with time zone | yes |  | Time of the event the name describes (UTC); NULL = not happened. |
| `decision_note` | text | yes |  | As named. |
| `updated_at` | timestamp with time zone | no | now() | Last update (trigger `set_updated_at`). |

<details><summary>Constraints and indexes</summary>

- CHECK `approval_request_check`: `CHECK ((status = ANY (ARRAY['approved'::app.approval_status, 'rejected'::app.approval_status])) = (decided_by IS NOT NULL AND decided_at IS NOT NULL))`
- FK `approval_request_decided_by_fkey`: `FOREIGN KEY (decided_by) REFERENCES app.app_user(id) ON DELETE RESTRICT`
- FK `approval_request_zone_id_fkey`: `FOREIGN KEY (zone_id) REFERENCES app.zone(id) ON DELETE RESTRICT`
- PK `approval_request_pkey`: `PRIMARY KEY (id)`
- UNIQUE `approval_request_id_zone_id_key`: `UNIQUE (id, zone_id)`
- INDEX: `btree (kind, subject_id) WHERE (status = 'pending'::app.approval_status)`
- INDEX: `btree (zone_id, requested_at) WHERE (status = 'pending'::app.approval_status)`

</details>

## Notifications (M13)

### notification

In-app notification (M13). Idempotent per outbox event.  
RLS: **yes**

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
- CHECK `notification_link_check`: `CHECK (link IS NULL OR jsonb_typeof(link) = 'object'::text)`
- FK `notification_user_id_fkey`: `FOREIGN KEY (user_id) REFERENCES app.app_user(id) ON DELETE CASCADE`
- FK `notification_zone_id_fkey`: `FOREIGN KEY (zone_id) REFERENCES app.zone(id) ON DELETE RESTRICT`
- PK `notification_pkey`: `PRIMARY KEY (id)`
- UNIQUE `notification_idempotency_key_key`: `UNIQUE (idempotency_key)`
- INDEX: `btree (user_id, created_at DESC, id DESC)`
- INDEX: `btree (user_id) WHERE (read_at IS NULL)`

</details>

## Reporting (M12, N3, N4, N7)

### vacancy_forecast

N4 output: probability a slot is vacant per day kind and hour. Advisory only (AC-18).  
RLS: **yes**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `slot_id` | uuid | no |  | References `slot`. |
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `day_kind` | app.day_kind | no |  | Value from the fixed set of its type / CHECK (see constraints). |
| `hour_of_day` | smallint | no |  | Local hour 0–23. |
| `p_vacant` | numeric(4,3) | no |  | Probability the slot is vacant. |
| `sample_days` | integer | no |  | Days of history behind the estimate. |
| `computed_at` | timestamp with time zone | no | now() | Time of the event the name describes (UTC); NULL = not happened. |

<details><summary>Constraints and indexes</summary>

- CHECK `vacancy_forecast_hour_of_day_check`: `CHECK (hour_of_day >= 0 AND hour_of_day <= 23)`
- CHECK `vacancy_forecast_p_vacant_check`: `CHECK (p_vacant >= 0::numeric AND p_vacant <= 1::numeric)`
- CHECK `vacancy_forecast_sample_days_check`: `CHECK (sample_days >= 0)`
- FK `vacancy_forecast_slot_id_zone_id_fkey`: `FOREIGN KEY (slot_id, zone_id) REFERENCES app.slot(id, zone_id) ON DELETE CASCADE`
- PK `vacancy_forecast_pkey`: `PRIMARY KEY (slot_id, day_kind, hour_of_day)`
- INDEX: `btree (zone_id)`

</details>

### kpi_daily

Daily KPI per zone (aggregates only). The only data the chain operator reads.  
RLS: **yes**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `day` | date | no |  | Local date in the zone's timezone. |
| `metric` | text | no |  | Value from the fixed set of its type / CHECK (see constraints). |
| `value` | numeric | no |  | As named. |
| `computed_at` | timestamp with time zone | no | now() | Time of the event the name describes (UTC); NULL = not happened. |

<details><summary>Constraints and indexes</summary>

- CHECK `kpi_daily_metric_check`: `CHECK (metric = ANY (ARRAY['extra_slot_hours'::text, 'match_rate'::text, 'cross_zone_fulfilment_rate'::text, 'owner_return_conflicts'::text, 'dispute_filing_minutes_p50'::text, 'blocked_ineligible_tx'::text, 'repeat_dispute_rate_after_swap'::text]))`
- FK `kpi_daily_zone_id_fkey`: `FOREIGN KEY (zone_id) REFERENCES app.zone(id) ON DELETE RESTRICT`
- PK `kpi_daily_pkey`: `PRIMARY KEY (zone_id, day, metric)`
- INDEX: `btree (day, metric)`

</details>

### reconciliation_report

N3 end-of-day report per zone.  
RLS: **yes**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `zone_id` | uuid | no |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `day` | date | no |  | As named. |
| `summary` | jsonb | no |  | As named. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |

<details><summary>Constraints and indexes</summary>

- CHECK `reconciliation_report_summary_check`: `CHECK (jsonb_typeof(summary) = 'object'::text)`
- FK `reconciliation_report_zone_id_fkey`: `FOREIGN KEY (zone_id) REFERENCES app.zone(id) ON DELETE RESTRICT`
- PK `reconciliation_report_pkey`: `PRIMARY KEY (id)`
- UNIQUE `reconciliation_report_zone_id_day_key`: `UNIQUE (zone_id, day)`

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
- INDEX: `btree (published_at) WHERE (published_at IS NOT NULL)`
- INDEX: `btree (id) WHERE (published_at IS NULL)`

</details>

### idempotency_keys

Generic idempotency store (`thread_id:step`, `source:event_id`), purged by TTL.  
RLS: **no**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `key` | text | no |  | `thread_id:step` (workflows) or `source:event_id` (jobs). |
| `result` | jsonb | yes |  | Result returned to a replay of the same key. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |

<details><summary>Constraints and indexes</summary>

- CHECK `idempotency_keys_key_check`: `CHECK (length(key) >= 1 AND length(key) <= 200)`
- PK `idempotency_keys_pkey`: `PRIMARY KEY (key)`
- INDEX: `btree (created_at)`

</details>

### workflow_run

Index of LangGraph runs (W0–W7) for status screens and RLS; state itself lives in schema `agent`.  
RLS: **yes**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `thread_id` | text | no |  | LangGraph thread id. |
| `workflow` | app.workflow_code | no |  | Value from the fixed set of its type / CHECK (see constraints). |
| `zone_id` | uuid | yes |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `initiator_user_id` | uuid | yes |  | References `app_user`. |
| `status` | app.workflow_status | no | 'running'::app.workflow_status | Value from the fixed set of its type / CHECK (see constraints). |
| `started_at` | timestamp with time zone | no | now() | Time of the event the name describes (UTC); NULL = not happened. |
| `finished_at` | timestamp with time zone | yes |  | Time of the event the name describes (UTC); NULL = not happened. |
| `updated_at` | timestamp with time zone | no | now() | Last update (trigger `set_updated_at`). |

<details><summary>Constraints and indexes</summary>

- CHECK `workflow_run_check`: `CHECK ((status = ANY (ARRAY['completed'::app.workflow_status, 'failed'::app.workflow_status, 'cancelled'::app.workflow_status])) = (finished_at IS NOT NULL))`
- FK `workflow_run_initiator_user_id_fkey`: `FOREIGN KEY (initiator_user_id) REFERENCES app.app_user(id) ON DELETE SET NULL`
- FK `workflow_run_zone_id_fkey`: `FOREIGN KEY (zone_id) REFERENCES app.zone(id) ON DELETE RESTRICT`
- PK `workflow_run_pkey`: `PRIMARY KEY (thread_id)`
- INDEX: `btree (initiator_user_id, started_at DESC)`
- INDEX: `btree (zone_id, status)`

</details>

### audit_log

Trigger-written history of config, eligibility, holding and approval changes. Append-only.  
RLS: **yes**

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

### knowledge_doc

Rule documents for RAG, scoped to chain / zone / building.  
RLS: **yes**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `zone_id` | uuid | yes |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `building_id` | uuid | yes |  | References `building`. |
| `title` | text | no |  | As named. |
| `source_uri` | text | no |  | As named. |
| `version` | integer | no | 1 | Version number, increasing per parent. |
| `is_active` | boolean | no | true | Soft retire flag; rows stay referenced by history. |
| `created_at` | timestamp with time zone | no | now() | Insert time (UTC). |

<details><summary>Constraints and indexes</summary>

- CHECK `knowledge_doc_version_check`: `CHECK (version > 0)`
- FK `knowledge_doc_building_id_fkey`: `FOREIGN KEY (building_id) REFERENCES app.building(id) ON DELETE RESTRICT`
- FK `knowledge_doc_zone_id_fkey`: `FOREIGN KEY (zone_id) REFERENCES app.zone(id) ON DELETE RESTRICT`
- PK `knowledge_doc_pkey`: `PRIMARY KEY (id)`
- UNIQUE `knowledge_doc_source_uri_version_key`: `UNIQUE (source_uri, version)`

</details>

### knowledge_chunk

Chunks + `embedding vector(1024)` (pgvector). Exact scan; no ANN index at this size.  
RLS: **yes**

| Column | Type | Null | Default | Meaning |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Primary key (UUIDv7 unless the type says bigint). |
| `doc_id` | uuid | no |  | References `knowledge_doc`. |
| `zone_id` | uuid | yes |  | Owning zone; drives RLS. Consistent with the parent via composite FK. |
| `building_id` | uuid | yes |  | Optional building scope; NULL = zone-wide. |
| `ordinal` | integer | no |  | As named. |
| `content` | text | no |  | Chunk text retrieved for W7 answers. |

<details><summary>Constraints and indexes</summary>

- CHECK `knowledge_chunk_content_check`: `CHECK (btrim(content) <> ''::text)`
- CHECK `knowledge_chunk_ordinal_check`: `CHECK (ordinal >= 0)`
- FK `knowledge_chunk_doc_id_fkey`: `FOREIGN KEY (doc_id) REFERENCES app.knowledge_doc(id) ON DELETE CASCADE`
- PK `knowledge_chunk_pkey`: `PRIMARY KEY (id)`
- UNIQUE `knowledge_chunk_doc_id_ordinal_key`: `UNIQUE (doc_id, ordinal)`
- INDEX: `btree (zone_id, building_id)`

</details>
