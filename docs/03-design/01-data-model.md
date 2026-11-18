# 01 — Data model: database design overview

## TL;DR (tiếng Việt)

**Thiết kế này là gì:** schema PostgreSQL 16 cho ParkSmart AI (**v3 MVP: 27 bảng**, schema `app`; v2 có 57 bảng), RLS theo khu/hộ, sổ cái hash-chain, mã hóa biển số. Phạm vi MVP = các module Ưu tiên 1 + 2 của backlog (4 người × 4 tuần) cộng 7 bảng bảo mật/độ bền (`refresh_token`, `staff_zone`, `otp_challenge`, `ledger_head`, `audit_log`, `slot_holding`, `idempotency_keys`). 30 bảng còn lại (Ưu tiên 3, chất lượng dữ liệu, tuân thủ) **đã hoãn**, xem [08-deferred-tables.md](08-deferred-tables.md); DDL v2 đầy đủ lấy lại bằng `git show 333b85b:docs/database/02-schema.sql`. Các giá trị mặc định vẫn là mặc định có nghiên cứu — **chưa được BQL/nghiệp vụ duyệt**.

**Hoãn trong MVP:** tranh chấp (M10), hoán đổi (M11), quá giờ/phiên đỗ (W4), voucher, dự báo/KPI lịch sử, đối soát, quên mật khẩu, log xem biển số gốc, xóa dữ liệu theo yêu cầu, job xóa theo thời hạn lưu, chia partition `lpr_event`. Biển số trong MVP **chỉ hiển thị dạng che** (`plate_masked`).

**10 quyết định quan trọng nhất** (chi tiết: [07-db-decision-log.md](07-db-decision-log.md); **D-31** là quyết định cắt còn 27 bảng)
1. RLS trên mọi bảng theo khu/hộ; khu khác chỉ nhận *cấp tư cách + hạn* (BR-17).
2. EXCLUDE constraint chống đặt trùng ô/giờ; dòng đã hủy/đổi chỗ/void không còn chặn (D-26).
3. Sổ cái chỉ ghi thêm, hash-chain theo từng khu, ghi qua một hàm duy nhất.
4. Biển số mã hóa **ở ứng dụng** AES-256-GCM + KMS, tra cứu bằng HMAC (D-07, đề xuất sửa ADR-0005). MVP không có hàm xem biển số gốc.
5. Log LPR thô: mục tiêu giữ **90 ngày** (D-05), nhưng **MVP không chia partition và không có job xóa** — bảng thường, hoãn đến khi có dữ liệu thật.
6. Mục tiêu lưu: audit **5 năm**; sổ cái, thỏa thuận, thanh toán **10 năm** (D-06). Trong MVP `audit_log` chỉ ghi thêm; không có `retention_rule`/`purge_expired`, các thời hạn là **mục tiêu ghi trong tài liệu, chưa thực thi**.
7. Xóa dữ liệu cá nhân trong **20 ngày** theo Nghị định 356/2025 (D-14, D-15) là **mục tiêu hoãn**: chưa có `erase_user`/`privacy_request`; bắt buộc làm trước khi dùng dữ liệu người dùng thật.
8. Chủ về sớm: chủ **không** chịu thêm phí; người thuê trả giá TH3 cho phần thời gian bị chuyển, được hoàn phần chưa dùng (D-09).
9. Hoán đổi và đồng ý hai bên (D-10) **hoãn** cùng M11 (bỏ `swap_*`, `zone_policy.swap_requires_party_consent`).
10. Ngưỡng duyệt 1 000 000 đ/thỏa thuận; dự phòng 15/30 phút (D-02, D-08 — *mặc định, cần BQL xác nhận*). Giá nằm trong `zone_policy.prices` (jsonb, D-01). Quá giờ (D-03) **hoãn** cùng W4: bỏ `overstay_*`.

**5 rủi ro lớn nhất:** (1) **chưa chạy được trên PG16 + pgvector** (WSL2 crash do lỗi phần cứng); (2) giá/ngưỡng/thời gian là số mặc định, độ tin cậy thấp; (3) EXPLAIN với dữ liệu lớn chưa làm — index chưa được kiểm chứng ở quy mô thật; (4) checkpoint LangGraph (schema `agent`) có thể chứa dữ liệu cá nhân nếu code agent vi phạm quy tắc D-12 (job xóa checkpoint cũ đã hoãn); (5) cần hồ sơ đánh giá chuyển dữ liệu xuyên biên giới (Bedrock) trước khi dùng dữ liệu thật (D-23); (6) **MVP chưa thực thi thời hạn lưu và chưa có xóa dữ liệu cá nhân** → phải bổ sung (`retention_rule`, `privacy_request`, `erase_user`) trước khi có dữ liệu người dùng thật; (7) **chỉ hiển thị biển số che**: không có luồng xem biển gốc có log, nên mọi màn hình cần biển gốc phải chờ `plate_access_log` (AC-12).

**Đọc trước trong decision log:** D-31, rồi mục 1 (độ tin cậy thấp / khó đảo ngược): D-05, D-07, D-01–D-04, D-08, D-12, D-14, D-09.

## Changes since v2 (v3, MVP 27 tables)

| Area | Change |
|------|--------|
| Decision | [D-31](07-db-decision-log.md): MVP schema = 27 tables (option C). 57 → 27; rationale and what stays in the decision log |
| Kept (27) | `zone`, `building`, `slot_pool`, `slot`, `app_user`, `staff_zone`, `refresh_token`, `vehicle`, `asset`, `eligibility`, `slot_holding`, `zone_policy`, `approval_request`, `share_window`, `parking_request`, `booking`, `agreement`, `otp_challenge`, `ledger_head`, `ledger_entry`, `payment`, `notification`, `outbox`, `idempotency_keys`, `audit_log`, `lpr_event`, `knowledge_chunk` |
| Removed (30) | Listed with the way back in [08-deferred-tables.md](08-deferred-tables.md); full v2 DDL: `git show 333b85b:docs/database/02-schema.sql` |
| Merged into columns | `subzone` → `building.subzone_code`; `basement` → `slot.level_code`; `size_class` → enum `app.size_class` (S<M<L<XL); `gate`/`lpr_source` → `lpr_event.gate_code/source_code`; `consent` → `app_user.consent_text_version/consented_at`; `price_rule` → `zone_policy.prices` (jsonb); `agreement_template` → `zone_policy.agreement_template_md`; `knowledge_doc` → `knowledge_chunk` doc columns; `kpi_daily` → view `app.kpi_daily_v`; `chain` dropped (`zone.code` globally unique) |
| Moved | OCR threshold: `lpr_source.ocr_review_threshold` → `zone_policy.ocr_review_threshold` (D-21) |
| `lpr_event` | Plain table (no partitions, identity PK); dedupe `UNIQUE (zone_id, source_code, source_event_id)` |
| Enums / policy | 15 enums dropped, `holding_kind`, `approval_kind`, `ledger_entry_type`, `payment_kind` trimmed; `zone_policy` loses `overstay_*` and `swap_requires_party_consent` |
| Functions removed | `ensure_lpr_partitions`, `drop_expired_lpr_partitions`, `reveal_lpr_plate`, `reveal_vehicle_plate`, `payment_validate_voucher`, `swap_proposal_validate`, `purge_expired`, `erase_user`, `purge_agent_checkpoints`; `reject_mutation()` loses the purge branch |
| Not enforced in MVP | Retention periods (D-05, D-06, D-12 purge) and erasure (D-14, D-15): documented targets only; masked plates only |
| Tests | v3 assertion count in §6; swap, erasure, retention/partition, voucher, dispute and reveal tests dropped; new tests for enum size rule, `prices` object, consent pair, `lpr_event` dedupe, `kpi_daily_v` row filter |
| Docs | 00, 01, 02, 03, 04–07, 08, 09, 10, diagram regenerated or trimmed; new [08-deferred-tables.md](08-deferred-tables.md) |

## Changes since v1 (v2, 57 tables; superseded by v3 above)

| Area | Change |
|------|--------|
| Decisions | Q1–Q13 and 17 new items resolved in [07-db-decision-log.md](07-db-decision-log.md); ADR-0005 change proposed in [09-adr-0005-amendment-proposal](09-adr-0005-amendment-proposal.md) |
| Legal basis | Decree 13/2023 replaced by **PDPL 91/2025/QH15 + Decree 356/2025/ND-CP** (in force 2026-01-01) |
| Defaults | `zone_policy` columns now carry researched DEFAULTs ("default, confirm with BQL"); seed uses them; prices re-based (D-01) |
| New schema | `privacy_request`, `retention_rule`, `occupancy_hourly`; `zone_policy.overstay_reminder_every / swap_requires_party_consent / early_return_cost_rule`; payment kinds `relocation_th3`, `early_return_refund` + `payment.direction`; ledger type `early_return_settlement`; `swap_leg.accepted_at`; `dispute_evidence.snapshot`; functions `purge_expired`, `drop_expired_lpr_partitions`, `erase_user`, `purge_agent_checkpoints`, `current_zone_policy` |
| Bugs fixed | `slot_holding` could not release a mistaken holding (added void); `lpr_event.reviewed_by` SET NULL contradicted a CHECK (→ RESTRICT); missing idempotency keys on `share_window`, `voucher`, evidence; `drop_expired_lpr_partitions` reported OIDs |
| Erasure support | `vehicle.plate_*` and `app_user.phone_e164` nullable after erasure, guarded by CHECKs |
| Tests | 125 assertions (was 95): new §9 covers checks a–d, D-05/06/09/10/12/14/15; concurrency re-run |
| Diagram | [diagrams/schema-diagram.html](diagrams/schema-diagram.html): all 57 tables at column level in 13 module panels, generated from the catalog |
| Docs | 01, 03 (regenerated, 57 tables / 503 columns), 04, 05 (idempotency inventory, settlement, consent), 06 (E-29…E-34, R-18…R-20), 07 (retention, data-subject requests, agent schema, verified migration recipes), 09 updated |
| Not done | PG16/pgvector run (blocked, §6); large-volume EXPLAIN (skipped at the user's request, §6) |

> Scope: the PostgreSQL schema for ParkSmart AI (P-142), derived from `docs/` and the existing repo.
> Files: [02-erd](02-erd.md) · [sql/schema.sql](sql/schema.sql) · [03-data-dictionary](03-data-dictionary.md) ·
> [04-queries-indexes](04-queries-indexes.md) · [05-concurrency](05-concurrency.md) ·
> [06-risks-edge-cases](06-risks-edge-cases.md) · [01-database-operations](../08-operations/01-database-operations.md) ·
> [sql/seed-and-tests.sql](sql/seed-and-tests.sql) · [01-db-preprod-checklist](../07-deployment/01-db-preprod-checklist.md)
>
> [08-deferred-tables](08-deferred-tables.md)
>
> Status: **proposal v3, MVP 27 tables** (2026-11-18; v2 = 57 tables is in git, `333b85b`). Nothing in `server/migrations/` exists yet. This design is meant to be turned into
> Alembic revisions (plain SQL, ADR-0005) module by module, following the backlog order.

## 1. Sources read

| Source | Used for |
|--------|----------|
| `docs/01-product/00-xac-dinh-bai-toan.md`, `01-product/01-project-brief.md`, `02-prd.md`, `03-scope.md` | Domain, roles, TH1/TH2/TH3, L1–L4, BR-01…BR-19, FR-01…FR-27, NFRs, assumptions A-01…A-10 |
| `01-product/04-user-stories.md`, `04-user-stories.md`, `ux/01-user-flow.md` | US/AC detail, flows 0–6 |
| `01-product/backlog/{README,01-modules,02-agent-workflows,03-background-workflows}.md` | Modules M1–M14, workflows W0–W7, jobs N1–N8, priorities |
| `01-product/ux/wireframes/*.html` (17 screens, read as text) | Field-level hints: agreement/ledger codes (GD-, TC-, HD-), ledger entry types, OCR queue, plate-view log with reason, voucher codes |
| `10-adr/ADR-0005` (DB), `0006` (auth), `0010` (modules), `0004`, `0007`–`0009` (DB-related lines) | RDS PG + pgvector/pgcrypto/btree_gist, asyncpg + RLS via `SET LOCAL`, Alembic plain SQL, outbox, idempotency keys, JWT/argon2id/OTP |
| `02-architecture/02-tech-stack.md`, `05-development/01-server-structure.md`, `02-architecture/01-architecture-diagram.md` | Stack, module ownership of tables |
| `docker-compose.yml`, `server/src/app/platform/config/settings.py`, `server/requirements.txt`, `.claude/skills/new-migration`, `.claude/references/domain-glossary.md` | Postgres image `pgvector/pgvector:pg16`, no existing migrations or repositories, naming conventions |
| `docs/images/ParkSmartAI-arch-backend-folders.png` | `share_slots` example (`period tstzrange`, `buffer`) |

**Not read, or read only partly (listed rather than skipped silently):**

| File(s) | Why |
|---------|-----|
| `docs/guide/**` (15 chapters, topic guides, 8 screenshots) | Organisers' generic guidebook (CODEOWNERS-protected), not product requirements. Not read in detail. |
| `docs/images/*.png` except the backend-folders image | The docs say these images predate the N-zone model and that the text wins when they disagree (`backlog/README.md`, `02-architecture/01-architecture-diagram.md`). Not opened. |
| `docs/01-product/ux/ui-design/parksmart-prototype-tour.html` | Untracked file present at session start; it was removed from the working tree before it could be read. |
| `docs/01-product/ux/wireframes/assets/*.{css,js}` | Styling and demo interactions only. |

No PDF, DOCX or scanned material exists in `docs/`.

## 2. Requirements summary

**Domain.** One operator runs a *chain* of N ≥ 2 urban *zones* (khu). Each zone has subzones, residential towers
with a base podium (shophouses, offices, clinics, kindergartens), low-rise shophouse clusters and public lots.
Every tower basement has three slot types:

| Type | Who rents it out | Open scope (who may rent) |
|------|------------------|---------------------------|
| TH1 — bought by a resident | the owner | building (L1) by default; zone (L2) if the building rules allow (A-08) |
| TH2 — leased from the developer | the lessee, after one-time developer consent per pool (BR-02) | zone by default; chain (L3) if the chain operator allows |
| TH3 — public/guest | the zone BQL only (BR-03) | public, price by level |

**Eligibility.** One account per person for the whole chain (FR-23), with many entitlements (asset, role, validity)
verified by the BQL of the asset's zone. At a given building the person's level is the strongest of
L1 (asset in this building) > L2 (asset elsewhere in the zone) > L3 (asset in another zone) > L4 (none) (BR-15).
Expired entitlements block new transactions immediately (BR-16). Zones only exchange (level, valid_until) (BR-17).

**Roles.** resident/renter, guard, BQL (zone manager), chain operator (ADR-0006); system jobs and workflows.

**Main flows.** Request → level → route (TH1/TH2 match, or TH3/public) → hold → agreement (both confirm by OTP)
→ BQL approval if over threshold → ledger → simulated payment. Exceptions: owner returns early (renter moved to TH3
of the same zone), LPR ingestion (dedupe by event id, low-OCR review), KPIs. Overstay, disputes, swaps and
forecasts are modelled in v2 but **deferred in v3** ([08-deferred-tables](08-deferred-tables.md)).

**Non-functional requirements found.**

| NFR | Source | Where it lands |
|-----|--------|----------------|
| Separation by zone and household; BQL sees only its zone; chain operator sees aggregates only | PRD §9, ADR-0005 | RLS on the tenant tables (v3), `app.kpi_daily_v` only for chain operator and zone staff of that zone |
| Plates encrypted at rest; only the zone's BQL sees originals; every view logged | PRD §9, Scope §3, AC-12 | `plate_ciphertext` column-revoked; v3 shows masked plates only (no `reveal_*`, no `plate_access_log`: [08-deferred-tables](08-deferred-tables.md)) |
| Ledger append-only with hash chain | PRD §9, ADR-0005 | `ledger_entry` + `app.ledger_append` + statement triggers |
| No overlapping windows/bookings per slot | ADR-0005 | `EXCLUDE USING gist` |
| Idempotent workflow steps and jobs | ADR-0005, ADR-0010 | `idempotency_key` UNIQUE on every write target + `idempotency_keys` |
| Add zones/buildings/pools by data only | PRD §2, §9 | All hierarchy and rules are rows; no zone names in code or DDL |
| Retention, performance targets, availability | PRD §9 says **TBD** | Assumed in §3 below |

## 3. Assumptions

| ID | Assumption | Source / reason |
|----|------------|-----------------|
| AS-01 | **Scale (not stated in docs): medium.** ~20 zones, ~300 k users, ~150 k slots; ~200 k LPR events/day, kept 90 days (≈ 18 M rows, D-05; target only — v3 has no purge job, D-31); bookings ≈ 5 M/year. The demo has 3 zones. Confirmed as D-17. | Prompt default; PRD §9 "mục tiêu hiệu năng: TBD" |
| AS-02 | Target **PostgreSQL 16** (compose `pgvector:pg16`, RDS 16). DDL avoids PG17-only features (identity on partitioned tables, etc.). | `docker-compose.yml`, ADR-0005 |
| AS-03 | Money is integer VND (`bigint`); VND has no minor unit in practice. Prices are computed by the rule engine; the DB stores results. | PRD §8 (prices in đồng) |
| AS-04 | One time zone per zone (`Asia/Ho_Chi_Minh` default) defines business days (end-of-day reconciliation, "expires on day D"). | Single city (Project Brief §1) |
| AS-05 | Eligibility expiry is enforced at use time (`valid_during @> now()`), not by the N6 job. N6 only cleans status and notifies. | `background-workflows.md` N6 note |
| AS-06 | A low-rise shophouse belongs to no tower (`asset.building_id IS NULL`) → its holder is L2 in its zone; a podium shophouse belongs to its tower → L1 there. | Scope A-10 |
| AS-07 | Holding a parking slot does **not** by itself confer an eligibility level; levels come from apartment/shophouse/office assets. Slot usage rights live in `slot_holding`. Decided as D-18. | PRD §3.1 lists "chỗ đỗ" as a possible asset |
| AS-08 | Buffers are configured per zone (before and after the window); the owner's window minus buffers is the bookable period. | FR-06, AC-05 (length TBD); wireframe "Chủ \| DP \| Chia sẻ \| DP \| Chủ" |
| AS-09 | Pools: TH1 pool per building, TH2 and TH3 pools per zone. | PRD §4, AC-20 ("pool TH2 của khu C") |
| AS-10 | *(deferred with M11 in v3)* A swap transfers the **usage right** (new `slot_holding` of kind `swap_usage`), never ownership. | Scope §2 (ownership transfer out of scope); swap-proposal wireframe TBD |
| AS-11 | *(deferred with W4 in v3)* The overstay fee is charged as a `payment` of kind `overstay_fee`; the agreement pins the policy version used. | BR-08, FR-12 |
| AS-12 | The application never hard-deletes users; erasure (deferred in v3, D-14) = soft delete + PII scrub. Hence `ON DELETE RESTRICT` on user FKs. | Ledger and dispute history must survive (PRD §9) |
| AS-13 | Plate encryption: **app-side AES-256-GCM with KMS envelope keys + HMAC blind index** (D-07). ADR-0005 says pgcrypto → amendment proposed in [09-adr-0005-amendment-proposal](09-adr-0005-amendment-proposal.md). | §4.6 |
| AS-14 | Photo files are stored in S3, never in the DB; the DB keeps object keys and SHA-256. | Prompt rule; FR-13 |
| AS-15 | Embedding dimension 1024 (Bedrock Titan v2 class). | ADR-0007 does not name the embedding model |
| AS-16 | Requests are limited to 31 days; monthly passes are out of scope. | Scope §2 |
| AS-17 | `Supabase Auth/Realtime` in `modules.md` and `03-scope.md` is stale: ADR-0004/0005/0006 (RDS, self-issued JWT, Redis pub/sub) are newer and win. | Contradiction between backlog text and ADRs |

## 4. Key decisions

### 4.1 One schema `app`, module ownership by table prefix/area

Tables are grouped by module (ADR-0010) but live in a single schema `app`; schema `agent` is reserved for the
LangGraph checkpointer. *Alternative:* one schema per module. Rejected for now: cross-module FKs (booking → slot →
pool) are wanted for integrity, and per-module schemas add search_path and grant management for a 4-person team
without a real isolation benefit (the app uses one role anyway).

### 4.2 Primary keys: UUIDv7 for entities, bigint for append-heavy logs

* Entities use `uuid` generated as **UUIDv7** (`app.uuid_v7()`, or by the app). Reasons: ids appear in URLs and
  workflow state (no guessable sequence, no enumeration), the app can create ids before insert (needed for
  idempotent workflow steps), and v7 is time-ordered so B-tree inserts stay at the right edge (unlike v4).
* `lpr_event`, `outbox`, `audit_log` use `bigint` (16 bytes saved per row and per index entry on
  the biggest tables; ids are internal).
* `ledger_entry` uses the natural key `(zone_id, seq)`: the gap-free per-zone sequence *is* the chain order.
* *Alternative:* bigint everywhere. Rejected because external ids would be enumerable (IDOR risk on top of RLS)
  and multi-process workflows would need a round trip to get ids.

### 4.3 Zone denormalised everywhere, kept honest by composite FKs

RLS needs `zone_id` on each zone-owned row. Instead of trusting the app, every child carries `zone_id` and
references its parent by `(parent_id, zone_id)`. Example: `booking (slot_id, zone_id) → slot (id, zone_id)`. A
row can therefore never claim a zone different from its slot. The same trick keeps
`booking.provider_user_id = share_window.owner_user_id` and `booking.vehicle_id` owned by the renter. Cost: one
extra UNIQUE index per parent. This is the only denormalisation; it is constraint-protected, so 3NF anomalies
cannot occur.

### 4.4 The database enforces hard invariants; the rule engine decides

BR-14 says the deterministic rule engine (`policy/domain`) decides. The DB does not replace it; it refuses rows
that would violate a hard invariant if the app had a bug:
`EXCLUDE` (no double booking / overlapping windows / overlapping holders / duplicate entitlements),
`booking_validate` trigger (vehicle fits, level re-derived, inside bookable period, level within open scope,
TH3 has no share window), `share_window_validate` (no TH3 sharing, holder only, scope ≤ pool max),
agreement effective only with both confirmations (+ approval), TH2 pool needs developer consent.

### 4.5 Eligibility attestation across zones (BR-17)

`app.eligibility_level_at(user, building, at)` is `SECURITY DEFINER` and returns **only** `(level, valid_until)`.
A BQL of zone C cannot read zone A's `asset`/`eligibility` rows (RLS), but can still learn that a person is L3 at
C. Ordinary users can query only themselves (IDOR guard inside the function).

### 4.6 Plates: ciphertext + keyed hash + mask (masked only in the MVP)

* `plate_ciphertext` — not selectable by the app role (column-level grants). **v3 has no reveal path**: the
  functions `app.reveal_lpr_plate` / `app.reveal_vehicle_plate` and the `plate_access_log` table are deferred
  ([08-deferred-tables.md](08-deferred-tables.md)), so the MVP shows **masked plates only**. AC-12 holds because
  no original plate is ever shown. If any screen must show an original plate, ship `plate_access_log` and the
  reveal functions (log in the same transaction) first.
* `plate_hash` = HMAC-SHA256(normalised plate) with a separate KMS-held key ("blind index") for LPR matching
  without decryption.
* `plate_masked` for display.
* Encryption (D-07): AES-256-GCM **in the application**, envelope keys from KMS; the database never sees a key.
  See [09-adr-0005-amendment-proposal.md](09-adr-0005-amendment-proposal.md). Nulling ciphertext/hash on
  erasure (D-14) is deferred with `erase_user`.

### 4.7 Ledger: one hash chain per zone, single write path

`app.ledger_append()` locks the zone's `ledger_head` row, checks the idempotency key, computes
`sha256(prev_hash ‖ canonical fields)` and inserts. The app role has no INSERT/UPDATE/DELETE on the ledger;
statement-level triggers reject UPDATE/DELETE/TRUNCATE even for the owner. Per-zone chains avoid a global hot
row and match "BQL of the zone verifies". Verified under 4 concurrent writers (160 appends, gap-free, chain
intact).

### 4.8 No partitioning in the MVP

v2 range-partitioned `lpr_event` by month (90-day retention, D-05). **v3 does not partition**: `lpr_event` is a
plain table with an identity primary key and `UNIQUE (zone_id, source_code, source_event_id)` for dedupe
(BR-13). The demo and MVP volumes (3 zones) are far below any partitioning threshold, and
`ensure_lpr_partitions()` / `drop_expired_lpr_partitions()` are removed together with the retention purge (D-31).
Bring partitioning back when `lpr_event` approaches tens of millions of rows or when the 90-day purge ships
(dropping a partition is the cheap way to delete); the thresholds are in [01-database-operations §5](../08-operations/01-database-operations.md) and
the v2 DDL is in `git show 333b85b:docs/database/02-schema.sql`. Migrating a populated table to partitions needs a
copy/swap (new partitioned table, backfill, rename), so decide before the table is large. Every other table
stays unpartitioned.

### 4.9 Enums vs lookup tables vs jsonb

* PostgreSQL enums for closed sets the code branches on (slot type, scope, level, statuses). Adding a value is a
  cheap `ALTER TYPE … ADD VALUE`; removing one is hard, which is acceptable for these sets.
* v3 uses the ordered enum `app.size_class` for vehicle/slot size; lookup tables for open catalogues (dispute categories, etc.) are deferred.
* `jsonb` only for: ledger/outbox payloads (immutable event bodies), audit snapshots, `zone_policy.prices`
  (validated by the rule engine, D-31), notification deep links. No EAV, no multi-valued columns.

### 4.10 Technology choices

| Choice | Why | Alternative not chosen |
|--------|-----|------------------------|
| PostgreSQL 16 on RDS | ADR-0005; RLS, range types, EXCLUDE, pgvector | — |
| `btree_gist` | Needed for `EXCLUDE (uuid =, tstzrange &&)` | App-level overlap checks (racy) |
| `pgcrypto` | Installed per ADR-0005; used only by the seed/tests. Production plate crypto is app-side (D-07) | pgcrypto in production (key exposure in logs) |
| `pgvector` | W7 RAG over a few dozen documents, no extra vector DB | Separate vector store |
| Alembic, plain SQL | ADR-0005, `new-migration` skill | Autogenerate (rejected by ADR) |
| `pg_trgm` | **Not installed**: no requirement for `LIKE '%x%'` search. Add it with the first fuzzy-search feature (BQL user search). | — |

## 5. Questions (v1) → decisions (v2)

All v1 questions are decided in [07-db-decision-log.md](07-db-decision-log.md). Values are defaults to confirm with the
BQL / product owner, not approved business rules.

| v1 question | Decision | Confidence |
|-------------|----------|-----------|
| Q1 scale | D-17 keep AS-01 (LPR now kept 90 days) | medium |
| Q2 buffer, threshold, overstay, TTLs | D-02 (15/30 min), D-08 (1 000 000 đ), D-03 (overstay, **deferred in v3**), D-16 (hold 10 min, confirm 30 min), D-24 (OTP 5 min / 5 tries); prices D-01 | low |
| Q3 slot holding → L1? | D-18 no | medium |
| Q4 BR-16 carry-over | D-04 at most 7 days | low |
| Q5 TH1 open to zone | D-19 per building, default building | high |
| Q6 retention, erasure | D-05 (LPR 90 days), D-06 (logs 5 y, money 10 y, …), D-14 (erasure), D-15 (request deadlines) — **targets only in v3, not enforced (D-31)** | medium |
| Q7 plate encryption | D-07 app-side AES-256-GCM + KMS + HMAC blind index; ADR amendment proposed | medium |
| Q8 threshold criterion | D-08 amount only | low |
| Q9 early-return cost | D-09 provider pays nothing; renter pays TH3 price for the relocated period; refund of unused share time | medium |
| Q10 swap consent | D-10 yes by default (per-zone flag) — **deferred in v3 with swaps** | medium |
| Q11 organisations | D-11 representative user | low |
| Q12 embedding | D-20 1024-dim multilingual model | medium |
| Q13 shared family plates | D-13 allowed; ambiguous LPR match → review | medium |

D-31 (v3): the schema is cut to 27 tables; D-03, D-05, D-06, D-10, D-11, D-12 (purge), D-14, D-15 are deferred or changed, D-21 moves to `zone_policy`. New items found in v2: D-12 (agent checkpoints), D-21 (OCR threshold), D-22 (legal basis changed), D-23
(cross-border transfer dossier), D-25 (LPR = sensitive), D-26…D-29 (checks a, c, d, e), D-30 (PG16 run open).

## 6. Verification status

| What | Status | Detail |
|------|--------|--------|
| `sql/schema.sql` + `sql/seed-and-tests.sql` (v3, 27 tables) | **v3 verified on PostgreSQL 17.10: 127 assertions (76 negative, 51 positive)** | Run on a throwaway PG17 cluster; last line `== done: all assertions passed`. Each negative test must fail with the expected SQLSTATE and, for business rules, the expected message. v2 (57 tables) had 125 assertions; the tests of removed tables/functions were dropped. |
| Same on **PostgreSQL 16** (`pgvector/pgvector:pg16`) | **Not run** | Docker Desktop cannot start: its WSL2 VM kernel-panics with a hardware *Machine Check Exception* ("Fatal machine check"; crash report under `%LOCALAPPDATA%/temp/wsl-crashes`). Downloading the official PG16 Windows binaries was refused by the session's permission policy. The DDL avoids PG17-only features, but that is reasoning, not a test. |
| `knowledge_chunk.embedding vector(1024)` | **Not run** | pgvector is not installed on the local PG17 and cannot be built here (no MSVC toolchain). Scripts ran with the explicit `parksmart.allow_missing_pgvector=on` opt-out, which skips only that column. |
| Concurrency (run on v2, PG17; v3 keeps the same EXCLUDE and ledger code) | Verified on v2 | 8 sessions racing for one slot → 1 booking, 7 × `23P01`; 4 × 40 concurrent ledger appends → seq gap-free, `ledger_verify` intact; a share-window cancel waited behind an in-flight booking (hit `lock_timeout`) and the booking committed. |
| Online migration recipes (check e) | Verified on PG17 (v2) | `booking` (add column, index `CONCURRENTLY`, FK `NOT VALID` + `VALIDATE`), `notification` (NOT NULL in steps), `lpr_event` (v2 partitioned recipe; v3 table is not partitioned). A `NOT VALID` FK on a partitioned table is rejected by PostgreSQL (relevant only if partitioning returns). |
| EXPLAIN at realistic volume | **Not done** | Skipped at the user's request during v2. 04 still holds the v1 plans: LPR (300 k rows) and notifications (110 k) measured; the others were forced on tiny tables and only prove a usable index exists. |

**To close the gaps** on a machine with working Docker: `docker compose up -d postgres`, then
`psql -v ON_ERROR_STOP=1 -f sql/schema.sql` and `-f sql/seed-and-tests.sql` (no opt-out). Expected last line:
`== done: all assertions passed`.

## 7. Traceability (requirement → schema)

Rows marked **deferred** point to objects that exist only in the v2 design; see
[08-deferred-tables.md](08-deferred-tables.md) for how to bring them back.

| Requirement | Tables / columns / objects |
|-------------|----------------------------|
| FR-23 one account, many entitlements | `app_user`, `eligibility (user_id, asset_id, role, valid_during, status, verified_by)`, `asset` |
| FR-24 / BR-15 level at slot location | `app.eligibility_level_at()`, `asset.building_id/zone_id`, `booking.eligibility_level` |
| FR-25 / BR-16 expiry blocks new tx | `eligibility.valid_during` checked at use; `booking_validate`; `parking_request(outcome='blocked', block_reason='BR-16')`; N6 via `eligibility_expiry_idx` |
| FR-26 open scope per pool, owner narrows only | `slot_pool.max_open_scope` + CHECK by type, `share_window.open_scope` + `share_window_validate` |
| FR-27 suggest other zones | `share_window_match_idx`; `share_window` open supply readable chain-wide (RLS `open_read`) |
| FR-01…04 routing & blocking | `parking_request`, `booking_validate` (BR-01/04/11), `share_window_validate` (BR-03), `slot.slot_type` |
| BR-05 free guest parking only at own building | Rule engine; no paid row is created. Not DB-enforced (no data model for "guest of resident" beyond TH3 booking) — see 06 R-14 |
| BR-06 / FR-22 / AC-16 shophouse guests → TH3, vouchers | **Deferred** (voucher, Ưu tiên 3): `voucher`, `payment.voucher_id`, `payment_validate_voucher` → [08-deferred-tables](08-deferred-tables.md) |
| FR-05 / FR-20 suggest windows, forecasts | **Deferred**: `vacancy_forecast`, `holiday`, `occupancy_hourly` → [08-deferred-tables](08-deferred-tables.md) |
| FR-06 buffer | `zone_policy.buffer_before/after`, `share_window.bookable_period` |
| FR-07 / BR-11 match by time, size, scope | enum `app.size_class` (S<M<L<XL), `slot.size_class`, `vehicle.size_class` (`vehicle.size_class <= slot.size_class`), EXCLUDE on `booking` |
| FR-08 / AC-07 agreement both confirm | `agreement` (pins `zone_policy_id`; template text in `zone_policy.agreement_template_md`), `otp_challenge`, CHECK on `effective` |
| FR-09 ledger | `ledger_entry`, `ledger_head`, `app.ledger_append`, `app.ledger_verify` |
| FR-09a / BR-12 / AC-15 approval over threshold | `zone_policy.approval_threshold_vnd`, `agreement.requires_approval/approval_request_id`, `approval_request` |
| FR-10 / BR-07 early return | `share_window.status='closed_early', returned_at`, `booking.status='relocated'`, `booking.relocated_from_booking_id`, ledger `early_return_relocation` |
| FR-11/12 / BR-08 overstay | **Deferred** (W4): `overstay_case`, `parking_session`, `zone_policy.overstay_*` → [08-deferred-tables](08-deferred-tables.md) |
| FR-13…16 / BR-18 disputes | **Deferred** (M10): `dispute_ticket`, `dispute_party`, `dispute_evidence`, `dispute_category` → [08-deferred-tables](08-deferred-tables.md) |
| FR-15 / BR-09 / AC-12 masked plates, logged views | `*_plate_masked`, column-revoked ciphertext; **MVP shows masked plates only**; `app.reveal_*` + `plate_access_log` deferred (must come first if an original plate is ever shown) → [08-deferred-tables](08-deferred-tables.md) |
| FR-16a / BR-13 / AC-10a LPR dedupe, OCR review | `lpr_event UNIQUE (zone_id, source_code, source_event_id)`, `zone_policy.ocr_review_threshold`, `lpr_event.status='pending_review'`, `lpr_event_review_idx` |
| FR-17/18 / BR-10 swaps | **Deferred** (M11): `swap_need`, `swap_proposal`, `swap_leg` → [08-deferred-tables](08-deferred-tables.md) |
| FR-19 LPR adapters | `lpr_event.source_code` (the `lpr_source` table is deferred) |
| FR-21 fees, VietQR mock | `zone_policy.prices` (jsonb), `payment.provider='vietqr_mock'` |
| BR-14 LLM never decides | `approval_request` decisions are made by staff; no decision column is written from LLM output (dispute AI suggestions are deferred with M10) |
| BR-17 minimal cross-zone data | RLS on `asset`/`eligibility`; `eligibility_level_at` returns level + expiry only |
| BR-19 price by level | `zone_policy.prices` `{slot_type: {level: {hour, day}}}`, validated by the rule engine |
| A-03 consent | `app_user.consent_text_version`, `app_user.consented_at` (withdrawal history deferred: `consent`) |
| KPIs (Scope §6) | view `app.kpi_daily_v` over `parking_request` and `zone` (requests, matched, redirected, blocked, no_match); dispute/swap KPIs deferred |
| ADR-0005 outbox / idempotency | `outbox`, `idempotency_keys`, `idempotency_key` UNIQUE on write targets |
| ADR-0006 auth | `app_user.password_hash` (argon2id CHECK), `refresh_token` (hashed, rotated, reuse detection), `staff_zone` (JWT `zone_ids`), `otp_challenge` (hashed, attempt limit); `password_reset_token` deferred |
| ADR-0010 HITL resume | `approval_request.thread_id` (LangGraph checkpointer; `workflow_run` deferred) |
| W7 RAG | `knowledge_chunk` (doc columns `doc_title`, `source_uri`, `doc_version`, `is_active`; `knowledge_doc` deferred), `embedding` |
| AC-09 cost of early return (D-09) | `payment.kind IN ('relocation_th3','early_return_refund')`, `payment.direction`, ledger `early_return_settlement`, `zone_policy.early_return_cost_rule` |
| PDPL / Decree 356 rights (D-14, D-15) | **Not enforced in v3**: `privacy_request`, `app.erase_user`, `consent` history deferred → [08-deferred-tables](08-deferred-tables.md); must ship before real user data |
| Retention (D-05, D-06, D-12) | **Not enforced in v3**: `retention_rule`, `app.purge_expired`, `app.drop_expired_lpr_partitions`, `app.purge_agent_checkpoints`, `occupancy_hourly` deferred; `audit_log` is strictly append-only |
| Swap consent (D-10) | **Deferred** with M11 (`swap_leg.accepted_at`, `swap_requires_party_consent`, `swap_proposal_validate`) |
