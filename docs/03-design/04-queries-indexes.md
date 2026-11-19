# 04 — Main queries and the indexes that serve them

> **v4 (MVP, 23 tables) status:** no EXPLAIN pass at realistic volume has been run. Plans in §2 were forced with
> `enable_seqscan=off` on tiny tables and only show that a usable index exists; the 300 k-row `lpr_event` and 110 k-row
> `notification` measurements were taken on v1/v2 and still apply (`lpr_event` is now a plain table, so the plan is a
> single index scan instead of a Merge Append). No index was dropped for that reason. See checklist #35.
>
> **Indexes of removed tables** (`privacy_request_*`, `occupancy_hourly_zone_idx`, `dispute_*`, `voucher_*`,
> `plate_access_log_zone_idx`, `overstay_case_*`, `swap_leg_*`, `kpi_daily_day_idx`) are deferred, see
> [08-deferred-tables](08-deferred-tables.md). UNIQUE `share_window.idempotency_key` stays.
>
> **v4 ([D-32](07-db-decision-log.md#d-32)):** the indexes of `outbox` (`outbox_unpublished_idx`), `ledger_entry`
> (`ledger_entry_zone_time_idx`, PK `(zone_id, seq)`), `refresh_token`, `staff_zone` and `audit_log` went with their tables, so
> the old Q8, Q13 and the refresh-token part of Q15 are deferred. New indexes serve Q18–Q20 (agent threads, recovery cases,
> consent evidence, AI decision log) and `app_user_staff_zone_idx`. Slot lookups filter `slot.operational_status = 'active'`
> (`slot_zone_type_idx` is partial on it).

Principles used:
* Every index below serves a named query; there are no speculative ones. FKs are indexed where the child is
  queried or deleted through them (RESTRICT checks scan the child on parent delete).
* Partial indexes for queue-like access (`WHERE status = 'pending'`, `status NOT IN ('resolved','cancelled')`, `status = 'held'`):
  they stay small because rows leave the queue.
* Keyset pagination everywhere a list can grow (`ORDER BY created_at DESC, id DESC` + `(created_at, id) < ($1, $2)`).
  No `OFFSET` beyond the first page.
* RLS adds a predicate on `zone_id` / `user_id` to every query. Queries below already lead with that column, so
  the policy predicate lands on the same index.

## 1. Query ↔ index map

| # | Query (module / workflow) | Index | Type and why | Write cost |
|---|---------------------------|-------|--------------|------------|
| Q1 | Level of a user at a building (W1, every booking trigger) | `eligibility_user_idx` gist `(user_id, valid_during) WHERE status='verified'`; `asset` PK | GiST because `valid_during @> now()` is a range predicate; partial keeps it to live rows | Low: entitlements change rarely |
| Q2 | Matching: open windows in zone K covering [s,e) + slot size + not already booked (W1/W2, FR-07) | `share_window_match_idx` gist `(zone_id, bookable_period) WHERE status='open'`; `booking_no_overlap` gist (also the EXCLUDE) | Range containment needs GiST; the anti-join reuses the exclusion index, no extra index | Medium: one GiST per window insert |
| Q3 | Renter / provider history, newest first (M5, M4) | `booking_renter_idx (renter_user_id, lower(period) DESC)`, `booking_provider_idx` partial | Composite with equality first, sort column second → index-ordered keyset scan | Low |
| Q4 | BQL approval queue of a zone (M12) | `approval_request_queue_idx (zone_id, requested_at) WHERE status='pending'`; `approval_request_pending_uq (kind, subject_id) WHERE status='pending'` | Partial: only pending rows | Negligible |
| Q5 | OCR review queue (M8, BR-13) | `lpr_event_review_idx (zone_id, occurred_at) WHERE status='pending_review'` | Partial: only low-OCR rows (~2 %) | Low (only low-OCR rows) |
| Q6 | LPR → vehicle match, recent events of a plate (N1, W5) | `vehicle_plate_hash_idx` partial; `lpr_event_plate_idx (plate_hash, occurred_at DESC)` | Equality on HMAC, then time | One B-tree per LPR insert |
| Q7 | _Deferred (N2 overstay scan, `overstay_case`)_ | — | See [08-deferred-tables](08-deferred-tables.md); `booking_active_end_idx` stays and is the access path when it returns | — |
| Q8 | _Deferred (outbox relay, `outbox`)_ | — | See [08-deferred-tables](08-deferred-tables.md) and ADR-0011; use cases insert `notification` in the same transaction | — |
| Q9 | Notification inbox, unread badge (M13) | `notification_inbox_idx (user_id, created_at DESC, id DESC)`, `notification_unread_idx` partial | Keyset; partial for the badge count | One B-tree per insert (+1 while unread) |
| Q10 | N6 expiring entitlements | `eligibility_expiry_idx (upper(valid_during)) WHERE status='verified' AND NOT upper_inf(valid_during)` | Expression + partial: owners (no expiry) are excluded | Low |
| Q11 | Hold sweeper (expire stale holds) | `booking_hold_expiry_idx (hold_expires_at) WHERE status='held'` | Partial; holds live minutes | Low |
| Q12 | _Deferred (dispute queue, `dispute_ticket`)_ | — | See [08-deferred-tables](08-deferred-tables.md) | — |
| Q13 | Confirmation evidence of an agreement / of a zone by time (M6) | `consent_record_subject_idx (subject_type, subject_id)`, `consent_record_zone_idx (zone_id, created_at DESC) WHERE zone_id IS NOT NULL`; natural key `consent_record_natural_uq` | Equality on the subject; keyset by time for the BQL screen. The old hash-chain verify is deferred | Two B-trees + the UNIQUE per insert (append-only table, low rate) |
| Q14 | KPI dashboards (M12, N7) | view `app.kpi_daily_v` over `parking_request` (zone + local day); served by `parking_request_kpi_idx (zone_id, created_at, outcome)` | Aggregate on read: small tables at MVP volume; materialise only if > 500 ms (01-database-operations §5) | None |
| Q15 | Login by phone (ADR-0006; no refresh-token lookup in v4); staff of a zone | `app_user_phone_uq` partial unique; `app_user_staff_zone_idx (staff_zone_id) WHERE staff_zone_id IS NOT NULL` | Equality | Low |
| Q16 | _Deferred (plate-access audit, `plate_access_log`)_ | — | See [08-deferred-tables](08-deferred-tables.md) | — |
| Q17 | RAG retrieval for W7 | `knowledge_chunk_scope_idx (zone_id, building_id)` (real FKs) + exact vector scan; `is_active` filter | A few dozen documents → exact search is faster than ANN; add HNSW above ~50 k chunks | Negligible |
| Q18 | Conversations of a user, newest first (M14); BQL threads waiting for a decision | `agent_thread_user_idx (user_id, updated_at DESC)`; `agent_thread_zone_idx (zone_id) WHERE status='awaiting_manager'`; `approval_request_thread_idx (thread_id)` | Composite for the user list; partial for the BQL queue | Low (one update per turn) |
| Q19 | Open recovery cases of a zone by deadline (W3); relocated / chosen / approval lookups | `recovery_case_zone_idx (zone_id, deadline_at) WHERE status NOT IN ('resolved','cancelled')`; `recovery_case_open_uq (booking_id)` partial UNIQUE (one open case per booking); `recovery_case_relocated_idx`, `recovery_case_slot_idx`, `recovery_case_approval_idx` (partial, FK checks) | Partial: closed cases leave the index | Low |
| Q20 | AI decisions of a zone by time; of a thread; of an approval (BQL audit screen) | `ai_decision_log_zone_idx (zone_id, created_at DESC)`, `ai_decision_log_thread_idx (thread_id)`, `ai_decision_log_approval_idx` partial; `idempotency_key` UNIQUE | Keyset by time; equality on thread | One B-tree set per AI step (append-only) |

FK indexes added only for joins/RESTRICT checks that happen: `slot_pool_id_idx`, `booking_share_window_idx`,
`booking_request_idx`, `booking_vehicle_idx`, `agreement_*_idx`, `slot_holding_user_idx`, etc. Composite-FK targets reuse their UNIQUE `(id, zone_id)`
indexes. Not indexed on purpose: `ai_decision_log.user_hash` (investigations by user are rare and can afford a scan of a time range), `lpr_event.reviewed_by` (never filtered on;
investigations can afford a scan of a recent time range).

## 2. Sample queries with EXPLAIN notes

Measured on PostgreSQL 17.10 with the seed from `sql/seed-and-tests.sql` (the `lpr_event`/`notification` volume
figures come from earlier synthetic loads of 300 k / 110 k rows). Other tables hold a handful of rows, so for Q1–Q4, Q8, Q10 the plans were forced with
`SET enable_seqscan = off` and only prove that a usable index exists; on real data the planner should choose them
because the predicates are selective. Re-run these with `EXPLAIN (ANALYZE, BUFFERS)` on a staging copy before go-live.

### Q1 — level facts for one user (inside `app.eligibility_level_at`)
```sql
SELECT a.building_id, a.zone_id, upper(e.valid_during)
FROM app.eligibility e JOIN app.asset a ON a.id = e.asset_id
WHERE e.user_id = $1 AND e.status = 'verified' AND e.valid_during @> now();
```
Observed: `Nested Loop → Index Scan using eligibility_user_idx (user_id = $1 AND valid_during @> now()) → Index Scan
using asset_id_zone_id_key`. A user has a handful of entitlements, so this is O(1) per booking.

### Q2 — matching open supply (W1/W2)
```sql
SELECT w.id, s.id, s.code
FROM app.share_window w
JOIN app.slot s        ON s.id = w.slot_id
WHERE w.zone_id = $1 AND w.status = 'open'
  AND w.bookable_period @> tstzrange($2, $3)
  AND s.size_class >= $4::app.size_class              -- vehicle size (BR-11, ordered enum S<M<L<XL)
  AND w.open_scope >= $5                              -- scope admitting the seeker's level
  AND NOT EXISTS (SELECT 1 FROM app.booking b
                  WHERE b.slot_id = w.slot_id
                    AND b.status IN ('held','pending_agreement','pending_approval','confirmed')
                    AND b.period && tstzrange($2, $3))
ORDER BY lower(w.bookable_period)
LIMIT 20;
```
Observed (forced): `Nested Loop Anti Join`; inner `Index Only Scan using booking_no_overlap (period && …)`. On the
tiny table the planner used the window's EXCLUDE index (`share_window_no_overlap`, also partial on `open`) with a
zone filter; with real volume `share_window_match_idx` (zone first) is the expected access path. **Verify on staging.**
The anti-join is advisory: the EXCLUDE constraint is what finally prevents a double booking (05-concurrency §2).

### Q3 — renter history, keyset
```sql
SELECT id, period, status FROM app.booking
WHERE renter_user_id = $1 AND lower(period) < $2       -- $2 = last row's lower(period) from the previous page
ORDER BY lower(period) DESC LIMIT 20;
```
Observed: `Limit → Index Scan using booking_renter_idx (renter_user_id = $1 AND lower(period) < $2)`. No sort node.
Add `id` as a tie-breaker in the cursor if two bookings can start at the same instant.

### Q5 — OCR review queue (300 k rows)
```sql
SELECT id, occurred_at, ocr_confidence FROM app.lpr_event
WHERE zone_id = $1 AND status = 'pending_review'
ORDER BY occurred_at LIMIT 50;
```
Expected: `Limit → Index Scan using lpr_event_review_idx` (partial review index); 50 rows read, no sort, no heap filter.
(Earlier measurement was on the partitioned v2 table: Merge Append over per-partition indexes. Re-check on v3.)

### Q6 — recent passages of a plate (300 k rows)
```sql
SELECT id, occurred_at, direction FROM app.lpr_event
WHERE plate_hash = $1 AND occurred_at > now() - interval '7 days'
ORDER BY occurred_at DESC LIMIT 20;
```
Expected: `Bitmap Index Scan on lpr_event_plate_idx` → few heap blocks → small sort. (v2 measurement: 8 heap blocks, quicksort
of 8 rows.) With one plain table there is no partition pruning to plan for; if `lpr_event` is partitioned later,
pass the time bound as a parameter, not `now() - …`.

### Q7 — N2 overstay scan
_Deferred_ (N2/W4 and `overstay_case` are not in the MVP, see [08-deferred-tables](08-deferred-tables.md)).

### Q8 — outbox relay
_Deferred_ (`outbox` is not in the v4 MVP, see [08-deferred-tables](08-deferred-tables.md) and ADR-0011). The v3 relay
query (`FOR UPDATE SKIP LOCKED` on a partial index of unpublished rows) comes back with the table.

### Q9 — notification inbox, keyset (110 k rows)
```sql
SELECT id, title, created_at FROM app.notification
WHERE user_id = $1 AND (created_at, id) < ($2, $3)
ORDER BY created_at DESC, id DESC LIMIT 20;
```
Observed: `Limit → Index Scan using notification_inbox_idx (user_id = $1 AND ROW(created_at, id) < ROW($2, $3))`;
20 rows read regardless of page depth. This is why `OFFSET` is not used.

### Q10 — N6 entitlements expiring within 7 days
```sql
SELECT id, user_id FROM app.eligibility
WHERE status = 'verified' AND NOT upper_inf(valid_during) AND upper(valid_during) < now() + interval '7 days';
```
Observed (forced): `Index Scan using eligibility_expiry_idx (upper(valid_during) < …)`. Owners without expiry are
not in the index at all.

## 3. Bottlenecks anticipated

| Risk | Where | Mitigation in this design | When to do more |
|------|-------|---------------------------|-----------------|
| Deep pagination | inbox, histories, consent evidence, AI decision log, LPR timeline | Keyset cursors + matching composite indexes | — |
| `LIKE '%x%'` | none required by the docs | Not built. First fuzzy search (BQL user lookup by name) → `pg_trgm` GIN on `lower(unaccent(full_name))` | When the feature lands |
| Table growth / bloat | `lpr_event` | Plain table, fine for demo volume; no retention job in MVP | Before real LPR feeds: partition by month + retention (deferred, [08-deferred-tables](08-deferred-tables.md)) |
| | `notification`, `ai_decision_log`, `consent_record` | `notification` TTL deletes by an app job (not in MVP); `ai_decision_log` and `consent_record` are append-only and never purged in MVP (retention of `ai_decision_log` to decide before real data); partition only past ~50 M rows | See 01-database-operations §5 |
| Hot rows | `share_window`/`booking` of a popular slot | EXCLUDE uses row-level index locks only; no counter rows | — |
| N+1 queries | matching, inbox | Matching is one set-based query (Q2) | Code review rule |
| Heavy reporting | KPI | View `app.kpi_daily_v` (aggregates only) computed on read; dashboards read only it | Materialise nightly, then read replica when reporting queries exceed ~10 % of primary CPU (01-database-operations §5) |
| RLS overhead | every query | Context functions wrapped in `(SELECT …)` → evaluated once per query (InitPlan); policies lead with indexed columns | Profile with `pg_stat_statements` |
| Trigger cost on booking insert | `booking_validate` (3 lookups + level function) | All lookups are PK/index probes; ~5 index reads per insert | Bookings are a low-rate table (AS-01: ~15/min average) |
