# 00 — Database design overview

## TL;DR (tiếng Việt)

**Thiết kế này là gì:** schema PostgreSQL 16 cho ParkSmart AI (54 → 57 bảng, schema `app`), RLS theo khu/hộ, sổ cái hash-chain, mã hóa biển số. Bản v2 đã chốt mọi câu hỏi mở bằng giá trị mặc định có nghiên cứu — **chưa được BQL/nghiệp vụ duyệt**.

**10 quyết định quan trọng nhất** (chi tiết: [10-decision-log.md](10-decision-log.md))
1. RLS trên mọi bảng theo khu/hộ; khu khác chỉ nhận *cấp tư cách + hạn* (BR-17).
2. EXCLUDE constraint chống đặt trùng ô/giờ; dòng đã hủy/đổi chỗ/void không còn chặn (D-26).
3. Sổ cái chỉ ghi thêm, hash-chain theo từng khu, ghi qua một hàm duy nhất.
4. Biển số mã hóa **ở ứng dụng** AES-256-GCM + KMS, tra cứu bằng HMAC (D-07, đề xuất sửa ADR-0005).
5. Log LPR thô giữ **90 ngày** rồi xóa cả partition; dự báo dùng bảng tổng hợp không có dữ liệu cá nhân (D-05).
6. Log truy cập biển số / audit giữ **5 năm**; sổ cái, thỏa thuận, thanh toán **10 năm** (D-06).
7. Xóa dữ liệu cá nhân trong **20 ngày** theo Nghị định 356/2025, giữ id để sổ cái không phải sửa (D-14, D-15).
8. Chủ về sớm: chủ **không** chịu thêm phí; người thuê trả giá TH3 cho phần thời gian bị chuyển, được hoàn phần chưa dùng (D-09).
9. Hoán đổi cần **cả hai bên đồng ý** rồi BQL mới duyệt được (D-10, có thể tắt theo khu).
10. Ngưỡng duyệt 1 000 000 đ/thỏa thuận; dự phòng 15/30 phút; quá giờ: miễn 10 phút, 50 000 đ/giờ (D-02, D-03, D-08 — *mặc định, cần BQL xác nhận*).

**5 rủi ro lớn nhất:** (1) **chưa chạy được trên PG16 + pgvector** (WSL2 crash do lỗi phần cứng); (2) giá/ngưỡng/thời gian là số mặc định, độ tin cậy thấp; (3) EXPLAIN với dữ liệu lớn chưa làm — index chưa được kiểm chứng ở quy mô thật; (4) checkpoint LangGraph (schema `agent`) có thể chứa dữ liệu cá nhân nếu code agent vi phạm quy tắc D-12; (5) cần hồ sơ đánh giá chuyển dữ liệu xuyên biên giới (Bedrock) trước khi dùng dữ liệu thật (D-23).

**Đọc trước trong decision log:** mục 1 (độ tin cậy thấp / khó đảo ngược): D-05, D-07, D-01–D-04, D-08, D-12, D-14, D-09.

## Changes since v1

| Area | Change |
|------|--------|
| Decisions | Q1–Q13 and 17 new items resolved in [10-decision-log.md](10-decision-log.md); ADR-0005 change proposed in [adr-proposals/](adr-proposals/ADR-0005-amendment.md) |
| Legal basis | Decree 13/2023 replaced by **PDPL 91/2025/QH15 + Decree 356/2025/ND-CP** (in force 2026-01-01) |
| Defaults | `zone_policy` columns now carry researched DEFAULTs ("default, confirm with BQL"); seed uses them; prices re-based (D-01) |
| New schema | `privacy_request`, `retention_rule`, `occupancy_hourly`; `zone_policy.overstay_reminder_every / swap_requires_party_consent / early_return_cost_rule`; payment kinds `relocation_th3`, `early_return_refund` + `payment.direction`; ledger type `early_return_settlement`; `swap_leg.accepted_at`; `dispute_evidence.snapshot`; functions `purge_expired`, `drop_expired_lpr_partitions`, `erase_user`, `purge_agent_checkpoints`, `current_zone_policy` |
| Bugs fixed | `slot_holding` could not release a mistaken holding (added void); `lpr_event.reviewed_by` SET NULL contradicted a CHECK (→ RESTRICT); missing idempotency keys on `share_window`, `voucher`, evidence; `drop_expired_lpr_partitions` reported OIDs |
| Erasure support | `vehicle.plate_*` and `app_user.phone_e164` nullable after erasure, guarded by CHECKs |
| Tests | 125 assertions (was 95): new §9 covers checks a–d, D-05/06/09/10/12/14/15; concurrency re-run |
| Not done | PG16/pgvector run (blocked, §6); large-volume EXPLAIN (skipped at the user's request, §6) |

> Scope: the PostgreSQL schema for ParkSmart AI (P-142), derived from `docs/` and the existing repo.
> Files: [01-erd](01-erd.md) · [02-schema.sql](02-schema.sql) · [03-data-dictionary](03-data-dictionary.md) ·
> [04-queries-indexes](04-queries-indexes.md) · [05-concurrency](05-concurrency.md) ·
> [06-risks-edge-cases](06-risks-edge-cases.md) · [07-operations](07-operations.md) ·
> [08-seed-and-tests.sql](08-seed-and-tests.sql) · [09-checklist](09-checklist.md)
>
> Status: **proposal v2** (2026-11-18). Nothing in `server/migrations/` exists yet. This design is meant to be turned into
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
of the same zone), overstay (remind, charge). Disputes (ticket with masked plates to the slot zone's BQL),
swaps (same zone, BQL approval), LPR ingestion (dedupe by event id, low-OCR review), forecasts, KPIs.

**Non-functional requirements found.**

| NFR | Source | Where it lands |
|-----|--------|----------------|
| Separation by zone and household; BQL sees only its zone; chain operator sees aggregates only | PRD §9, ADR-0005 | RLS on 46 tables, `kpi_daily` only for chain operator |
| Plates encrypted at rest; only the zone's BQL sees originals; every view logged | PRD §9, Scope §3, AC-12 | `plate_ciphertext` column-revoked, `app.reveal_*` + `plate_access_log` |
| Ledger append-only with hash chain | PRD §9, ADR-0005 | `ledger_entry` + `app.ledger_append` + statement triggers |
| No overlapping windows/bookings per slot | ADR-0005 | `EXCLUDE USING gist` |
| Idempotent workflow steps and jobs | ADR-0005, ADR-0010 | `idempotency_key` UNIQUE on every write target + `idempotency_keys` |
| Add zones/buildings/pools by data only | PRD §2, §9 | All hierarchy and rules are rows; no zone names in code or DDL |
| Retention, performance targets, availability | PRD §9 says **TBD** | Assumed in §3 below |

## 3. Assumptions

| ID | Assumption | Source / reason |
|----|------------|-----------------|
| AS-01 | **Scale (not stated in docs): medium.** ~20 zones, ~300 k users, ~150 k slots; ~200 k LPR events/day, kept 90 days (≈ 18 M rows, D-05); bookings ≈ 5 M/year. The demo has 3 zones. Confirmed as D-17. | Prompt default; PRD §9 "mục tiêu hiệu năng: TBD" |
| AS-02 | Target **PostgreSQL 16** (compose `pgvector:pg16`, RDS 16). DDL avoids PG17-only features (identity on partitioned tables, etc.). | `docker-compose.yml`, ADR-0005 |
| AS-03 | Money is integer VND (`bigint`); VND has no minor unit in practice. Prices are computed by the rule engine; the DB stores results. | PRD §8 (prices in đồng) |
| AS-04 | One time zone per zone (`Asia/Ho_Chi_Minh` default) defines business days (end-of-day reconciliation, "expires on day D"). | Single city (Project Brief §1) |
| AS-05 | Eligibility expiry is enforced at use time (`valid_during @> now()`), not by the N6 job. N6 only cleans status and notifies. | `background-workflows.md` N6 note |
| AS-06 | A low-rise shophouse belongs to no tower (`asset.building_id IS NULL`) → its holder is L2 in its zone; a podium shophouse belongs to its tower → L1 there. | Scope A-10 |
| AS-07 | Holding a parking slot does **not** by itself confer an eligibility level; levels come from apartment/shophouse/office assets. Slot usage rights live in `slot_holding`. Decided as D-18. | PRD §3.1 lists "chỗ đỗ" as a possible asset |
| AS-08 | Buffers are configured per zone (before and after the window); the owner's window minus buffers is the bookable period. | FR-06, AC-05 (length TBD); wireframe "Chủ \| DP \| Chia sẻ \| DP \| Chủ" |
| AS-09 | Pools: TH1 pool per building, TH2 and TH3 pools per zone. | PRD §4, AC-20 ("pool TH2 của khu C") |
| AS-10 | A swap transfers the **usage right** (new `slot_holding` of kind `swap_usage`), never ownership. | Scope §2 (ownership transfer out of scope); swap-proposal wireframe TBD |
| AS-11 | The overstay fee is charged as a `payment` of kind `overstay_fee`; the agreement pins the policy version used. | BR-08, FR-12 |
| AS-12 | The application never hard-deletes users; erasure = soft delete + PII scrub. Hence `ON DELETE RESTRICT` on user FKs. | Ledger and dispute history must survive (PRD §9) |
| AS-13 | Plate encryption: **app-side AES-256-GCM with KMS envelope keys + HMAC blind index** (D-07). ADR-0005 says pgcrypto → amendment proposed in `adr-proposals/`. | §4.6 |
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
* `lpr_event`, `outbox`, `audit_log`, `plate_access_log` use `bigint` (16 bytes saved per row and per index entry on
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
TH3 has no share window), `share_window_validate` (no TH3 sharing, holder only, scope ≤ pool max), voucher only
for TH3, agreement effective only with both confirmations (+ approval), TH2 pool needs developer consent.

### 4.5 Eligibility attestation across zones (BR-17)

`app.eligibility_level_at(user, building, at)` is `SECURITY DEFINER` and returns **only** `(level, valid_until)`.
A BQL of zone C cannot read zone A's `asset`/`eligibility` rows (RLS), but can still learn that a person is L3 at
C. Ordinary users can query only themselves (IDOR guard inside the function).

### 4.6 Plates: ciphertext + keyed hash + mask, reads are logged by construction

* `plate_ciphertext` — not selectable by the app role (column-level grants). The only read paths are
  `app.reveal_lpr_plate` / `app.reveal_vehicle_plate`, which check the role/zone and write `plate_access_log` in
  the same transaction (AC-12).
* `plate_hash` = HMAC-SHA256(normalised plate) with a separate KMS-held key ("blind index") for LPR matching
  without decryption.
* `plate_masked` for display.
* Encryption (D-07): AES-256-GCM **in the application**, envelope keys from KMS; the database never sees a key.
  See [adr-proposals/ADR-0005-amendment.md](adr-proposals/ADR-0005-amendment.md). On erasure the ciphertext and
  hash become NULL (D-14).

### 4.7 Ledger: one hash chain per zone, single write path

`app.ledger_append()` locks the zone's `ledger_head` row, checks the idempotency key, computes
`sha256(prev_hash ‖ canonical fields)` and inserts. The app role has no INSERT/UPDATE/DELETE on the ledger;
statement-level triggers reject UPDATE/DELETE/TRUNCATE even for the owner. Per-zone chains avoid a global hot
row and match "BQL of the zone verifies". Verified under 4 concurrent writers (160 appends, gap-free, chain
intact).

### 4.8 Partition only `lpr_event`

Only `lpr_event` is expected to reach tens of millions of rows and needs time-based retention (90 days, D-05).
It is range-partitioned by month with a default partition, `ensure_lpr_partitions()` to create months ahead and
`drop_expired_lpr_partitions()` to drop expired ones. Every other table stays unpartitioned (thresholds in [07-operations §5](07-operations.md)).

### 4.9 Enums vs lookup tables vs jsonb

* PostgreSQL enums for closed sets the code branches on (slot type, scope, level, statuses). Adding a value is a
  cheap `ALTER TYPE … ADD VALUE`; removing one is hard, which is acceptable for these sets.
* Lookup tables for catalogues the docs leave open (vehicle size classes, dispute categories).
* `jsonb` only for: ledger/outbox payloads (immutable event bodies), audit snapshots, the N3 report document,
  notification deep links. No EAV, no multi-valued columns.

### 4.10 Technology choices

| Choice | Why | Alternative not chosen |
|--------|-----|------------------------|
| PostgreSQL 16 on RDS | ADR-0005; RLS, range types, EXCLUDE, partitioning, pgvector | — |
| `btree_gist` | Needed for `EXCLUDE (uuid =, tstzrange &&)` | App-level overlap checks (racy) |
| `pgcrypto` | Installed per ADR-0005; used only by the seed/tests. Production plate crypto is app-side (D-07) | pgcrypto in production (key exposure in logs) |
| `pgvector` | W7 RAG over a few dozen documents, no extra vector DB | Separate vector store |
| Alembic, plain SQL | ADR-0005, `new-migration` skill | Autogenerate (rejected by ADR) |
| `pg_trgm` | **Not installed**: no requirement for `LIKE '%x%'` search. Add it with the first fuzzy-search feature (BQL user search). | — |

## 5. Questions (v1) → decisions (v2)

All v1 questions are decided in [10-decision-log.md](10-decision-log.md). Values are defaults to confirm with the
BQL / product owner, not approved business rules.

| v1 question | Decision | Confidence |
|-------------|----------|-----------|
| Q1 scale | D-17 keep AS-01 (LPR now kept 90 days) | medium |
| Q2 buffer, threshold, overstay, TTLs | D-02 (15/30 min), D-08 (1 000 000 đ), D-03 (10 min grace, 50 000 đ/h, remind every 15 min), D-16 (hold 10 min, confirm 30 min), D-24 (OTP 5 min / 5 tries); prices D-01 | low |
| Q3 slot holding → L1? | D-18 no | medium |
| Q4 BR-16 carry-over | D-04 at most 7 days | low |
| Q5 TH1 open to zone | D-19 per building, default building | high |
| Q6 retention, erasure | D-05 (LPR 90 days), D-06 (logs 5 y, money 10 y, …), D-14 (erasure), D-15 (request deadlines) | medium |
| Q7 plate encryption | D-07 app-side AES-256-GCM + KMS + HMAC blind index; ADR amendment proposed | medium |
| Q8 threshold criterion | D-08 amount only | low |
| Q9 early-return cost | D-09 provider pays nothing; renter pays TH3 price for the relocated period; refund of unused share time | medium |
| Q10 swap consent | D-10 yes by default (per-zone flag) | medium |
| Q11 organisations | D-11 representative user | low |
| Q12 embedding | D-20 1024-dim multilingual model | medium |
| Q13 shared family plates | D-13 allowed; ambiguous LPR match → review | medium |

New items found in v2: D-12 (agent checkpoints), D-21 (OCR threshold), D-22 (legal basis changed), D-23
(cross-border transfer dossier), D-25 (LPR = sensitive), D-26…D-29 (checks a, c, d, e), D-30 (PG16 run open).

## 6. Verification status

| What | Status | Detail |
|------|--------|--------|
| `02-schema.sql` + `08-seed-and-tests.sql` | **Verified on PostgreSQL 17.10 only** | 125 assertions pass: 10 positive checks (§5), 51 negative constraint tests (§6), 1 tamper test (§7), 33 RLS/privilege (§8), 30 v2 checks (§9). Each negative test must fail with the expected SQLSTATE and, for business rules, the expected message. |
| Same on **PostgreSQL 16** (`pgvector/pgvector:pg16`) | **Not run** | Docker Desktop cannot start: its WSL2 VM kernel-panics with a hardware *Machine Check Exception* ("Fatal machine check"; crash report under `%LOCALAPPDATA%/temp/wsl-crashes`). Downloading the official PG16 Windows binaries was refused by the session's permission policy. The DDL avoids PG17-only features (identity on a partitioned table was replaced by a sequence in v1), but that is reasoning, not a test. |
| `knowledge_chunk.embedding vector(1024)` | **Not run** | pgvector is not installed on the local PG17 and cannot be built here (no MSVC toolchain). Scripts ran with the explicit `parksmart.allow_missing_pgvector=on` opt-out, which skips only that column. |
| Concurrency (re-run on v2, PG17) | Verified | 8 sessions racing for one slot → 1 booking, 7 × `23P01`; 4 × 40 concurrent ledger appends → seq gap-free, `ledger_verify` intact; a share-window cancel waited behind an in-flight booking (hit `lock_timeout`) and the booking committed. |
| Online migration recipes (check e) | Verified on PG17 | `booking` (add column, index `CONCURRENTLY`, FK `NOT VALID` + `VALIDATE`), `notification` (NOT NULL in steps), `lpr_event` (index `ON ONLY` + per partition + `ATTACH`). A `NOT VALID` FK on a partitioned table is rejected by PostgreSQL → per-partition procedure in 07 §1. |
| EXPLAIN at realistic volume | **Not done** | Skipped at the user's request during v2. 04 still holds the v1 plans: LPR (300 k rows) and notifications (110 k) measured; the others were forced on tiny tables and only prove a usable index exists. |

**To close the gaps** on a machine with working Docker: `docker compose up -d postgres`, then
`psql -v ON_ERROR_STOP=1 -f 02-schema.sql` and `-f 08-seed-and-tests.sql` (no opt-out). Expected last line:
`== done: all assertions passed`.

## 7. Traceability (requirement → schema)

| Requirement | Tables / columns / objects |
|-------------|----------------------------|
| FR-23 one account, many entitlements | `app_user`, `eligibility (user_id, asset_id, role, valid_during, status, verified_by)`, `asset` |
| FR-24 / BR-15 level at slot location | `app.eligibility_level_at()`, `asset.building_id/zone_id`, `booking.eligibility_level` |
| FR-25 / BR-16 expiry blocks new tx | `eligibility.valid_during` checked at use; `booking_validate`; `parking_request(outcome='blocked', block_reason='BR-16')`; N6 via `eligibility_expiry_idx` |
| FR-26 open scope per pool, owner narrows only | `slot_pool.max_open_scope` + CHECK by type, `share_window.open_scope` + `share_window_validate` |
| FR-27 suggest other zones | `share_window_match_idx`; `share_window` open supply readable chain-wide (RLS `open_read`) |
| FR-01…04 routing & blocking | `parking_request`, `booking_validate` (BR-01/04/11), `share_window_validate` (BR-03), `slot.slot_type` |
| BR-05 free guest parking only at own building | Rule engine; no paid row is created. Not DB-enforced (no data model for "guest of resident" beyond TH3 booking) — see 06 R-14 |
| BR-06 / FR-22 / AC-16 shophouse guests → TH3, vouchers | `voucher`, `payment.voucher_id` + CHECK + `payment_validate_voucher` |
| FR-05 / FR-20 suggest windows, forecasts | `vacancy_forecast`, `holiday`, `occupancy_hourly` (history without personal data) |
| FR-06 buffer | `zone_policy.buffer_before/after`, `share_window.bookable_period` |
| FR-07 / BR-11 match by time, size, scope | `size_class.rank`, `slot.size_class_code`, `vehicle.size_class_code`, EXCLUDE on `booking` |
| FR-08 / AC-07 agreement both confirm | `agreement`, `agreement_template`, `otp_challenge`, CHECK on `effective` |
| FR-09 ledger | `ledger_entry`, `ledger_head`, `app.ledger_append`, `app.ledger_verify` |
| FR-09a / BR-12 / AC-15 approval over threshold | `zone_policy.approval_threshold_vnd`, `agreement.requires_approval/approval_request_id`, `approval_request` |
| FR-10 / BR-07 early return | `share_window.status='closed_early', returned_at`, `booking.status='relocated'`, `booking.relocated_from_booking_id`, ledger `early_return_relocation` |
| FR-11/12 / BR-08 overstay | `overstay_case`, `zone_policy.overstay_*`, `payment.kind='overstay_fee'`, ledger `overstay_fee` |
| FR-13…16 / BR-18 disputes | `dispute_ticket (zone_id = slot zone)`, `dispute_party`, `dispute_evidence`, `dispute_category` |
| FR-15 / BR-09 / AC-12 masked plates, logged views | `*_plate_masked`, column-revoked ciphertext, `app.reveal_*`, `plate_access_log` |
| FR-16a / BR-13 / AC-10a LPR dedupe, OCR review | `lpr_event UNIQUE (source_id, source_event_id, occurred_at)`, `lpr_source.ocr_review_threshold`, `lpr_event.status='pending_review'`, `lpr_event_review_idx` |
| FR-17/18 / BR-10 swaps | `swap_need`, `swap_proposal`, `swap_leg` (same-zone FK), `slot_holding(kind='swap_usage')` |
| FR-19 LPR adapters | `lpr_source.kind` |
| FR-21 fees, VietQR mock | `price_rule`, `payment.provider='vietqr_mock'` |
| BR-14 LLM never decides | `dispute_ticket.ai_summary/ai_confidence` stored as suggestions; no decision column is written from LLM output |
| BR-17 minimal cross-zone data | RLS on `asset`/`eligibility`; `eligibility_level_at` returns level + expiry only |
| BR-19 price by level | `price_rule (slot_type, level, unit)` |
| A-03 consent | `consent` |
| KPIs (Scope §6) | `kpi_daily.metric` (7 metrics), sources: `parking_request`, `booking`, `dispute_ticket`, `swap_proposal` |
| ADR-0005 outbox / idempotency | `outbox`, `idempotency_keys`, `idempotency_key` UNIQUE on write targets |
| ADR-0006 auth | `app_user.password_hash` (argon2id CHECK), `refresh_token`, `password_reset_token`, `otp_challenge` |
| ADR-0010 HITL resume | `approval_request.thread_id`, `workflow_run` |
| W7 RAG | `knowledge_doc`, `knowledge_chunk.embedding` |
| AC-09 cost of early return (D-09) | `payment.kind IN ('relocation_th3','early_return_refund')`, `payment.direction`, ledger `early_return_settlement`, `zone_policy.early_return_cost_rule` |
| PDPL / Decree 356 rights (D-14, D-15) | `privacy_request`, `app.erase_user`, `consent` |
| Retention (D-05, D-06, D-12) | `retention_rule`, `app.purge_expired`, `app.drop_expired_lpr_partitions`, `app.purge_agent_checkpoints`, `occupancy_hourly`, `dispute_evidence.snapshot` |
| Swap consent (D-10) | `swap_leg.accepted_at`, `zone_policy.swap_requires_party_consent`, trigger `swap_proposal_validate` |
