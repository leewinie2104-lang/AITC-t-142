# 05 — Concurrency and integrity per sensitive flow

## 0. Ground rules (all flows)

| Rule | Detail |
|------|--------|
| Isolation | **READ COMMITTED** everywhere (Postgres default). Every invariant below is protected by a constraint, a row lock or a conditional UPDATE, so SERIALIZABLE's retry cost is not needed. Re-evaluate only if a new invariant cannot be expressed that way. |
| Transaction = one unit of work | Opened by `platform.db.unit_of_work(ctx)`, which runs `SET LOCAL app.user_id / app.role / app.zone_ids` (ADR-0005). One zone per transaction (a cross-zone step is two transactions). |
| No external calls inside a transaction | LLM (Bedrock), S3, notifications, WebSocket publish, arq enqueue: never inside. Pattern: *read tx → external call → write tx with an idempotency key*. Side effects after commit go through the **outbox** written in the same transaction. |
| Timeouts (role defaults in 02-schema §0) | `statement_timeout = 5s`, `lock_timeout = 2s`, `idle_in_transaction_session_timeout = 30s` for `parksmart_app`. Background jobs may `SET LOCAL statement_timeout = '60s'` for a known scan. Migrations: `lock_timeout = 5s` + retry. |
| Idempotency | Every write made by a workflow step or job carries `idempotency_key = thread_id:step` (or `source:event_id`). UNIQUE constraints turn a replay into `23505`, which the repository maps to "return the existing row". LangGraph re-runs the node containing `interrupt()` on resume; arq re-runs jobs. |
| Lock ordering (deadlock avoidance) | When a transaction locks several rows of one table, it locks them in **ascending primary key** order. Across tables the order is: `share_window` → `booking` → `slot_holding` → `ledger_head`. `ledger_append` is always the last statement before the outbox insert. |
| Retries | Retry the whole transaction (max 3, jittered) on `40P01` deadlock, `55P03` lock timeout, `40001` serialization. Do **not** retry `23P01`/`23505`/`23514`: they are business answers. |
| Optimistic locking | User-edited rows with a `version` column (`booking`) use `UPDATE … SET version = version + 1 WHERE id = $1 AND version = $2`; 0 rows → `409 Conflict`. |

### 0.1 Idempotency inventory (check d, v3)

Every table written by a workflow step or job, and what makes a replay harmless:

| Write target | Replay guard |
|--------------|--------------|
| `parking_request`, `booking`, `payment`, `notification`, `ledger_entry`, `share_window` | UNIQUE `idempotency_key` (`share_window`: a replayed publish would otherwise hit the EXCLUDE as `23P01`) |
| `agreement` | UNIQUE `booking_id` |
| `approval_request` | partial UNIQUE `(kind, subject_id) WHERE status = 'pending'` + conditional decision UPDATE |
| `otp_challenge` | partial UNIQUE active challenge per (user, purpose, subject) |
| `lpr_event` | UNIQUE `(zone_id, source_code, source_event_id)` + `ON CONFLICT DO NOTHING` |
| `slot_holding` | EXCLUDE overlap |
| `outbox` | written in the same transaction as a guarded business row, so it cannot be replayed alone |
| `audit_log` | not idempotent by design: each row records one real event |

Deferred write targets (`voucher`, `dispute_evidence`, `swap_proposal`, `overstay_case`, `parking_session`,
`vacancy_forecast`, `occupancy_hourly`, `reconciliation_report`, `privacy_request`, `workflow_run`,
`plate_access_log`) and their guards: see [11-deferred-tables](11-deferred-tables.md). `kpi_daily` is now a view and
needs no guard.

No workflow or job write target of the 27-table schema is left without a guard.

## 1. Hold / booking creation (W1 → M5)

**Risk**: two seekers (or one seeker double-clicking, or a LangGraph replay) reserve the same slot and time.

**Transaction**
```sql
BEGIN;  -- unit_of_work: role=system, zone_ids={slot zone}
-- 1. free this slot from holds that already expired (the sweeper may lag)
UPDATE app.booking SET status = 'expired'
 WHERE slot_id = $slot AND status = 'held' AND hold_expires_at < now();
-- 2. insert the hold; the EXCLUDE constraint is the arbiter
INSERT INTO app.booking (..., status, hold_expires_at, idempotency_key)
VALUES (..., 'held', now() + $hold_ttl, $thread_step)
RETURNING id;
-- 3. outbox event in the same transaction
INSERT INTO app.outbox (event_type, zone_id, payload) VALUES ('BookingHeld', $zone, jsonb_build_object('booking_id', $id));
COMMIT;
```
* `booking_no_overlap` (EXCLUDE on `(slot_id, period)` for live statuses) makes a double booking impossible even
  when both transactions run at the same instant: the second inserter **waits** for the first to commit, then
  fails with `23P01`. Measured: 8 parallel sessions for one slot → exactly 1 booking, 7 × `23P01`.
* `23P01` → the step tries the next candidate from the matching query (Q2) in a new transaction.
* `23505` on `idempotency_key` → replay: `SELECT … WHERE idempotency_key = $1` and return it.
* The `booking_validate` trigger re-derives the level at the slot and the scope (BR-01/04/16), the size (BR-11),
  and the window bounds (FR-06) inside the same transaction, so a stale decision cannot be persisted.

## 2. Share window publish / cancel / early return (M4, W3)

**Risks**: overlapping windows; owner cancels while a booking is being created; early return races with a booking.

* Publish: `share_window_no_overlap` EXCLUDE on `(slot_id, period) WHERE status = 'open'`.
* Booking insert takes **`FOR SHARE`** on the window row (inside `booking_validate`). An owner's cancel is an
  `UPDATE` of that row, so the two serialize. Verified: a cancel started during an in-flight booking waited
  and hit `lock_timeout`.
* Cancel (owner) must check for live bookings **after** taking the lock:
```sql
BEGIN;
SELECT id FROM app.share_window WHERE id = $w AND owner_user_id = $me AND status = 'open' FOR UPDATE;   -- 0 rows → 404/409
-- new statement = new snapshot in READ COMMITTED: sees bookings committed while we waited for the lock
SELECT 1 FROM app.booking WHERE share_window_id = $w AND status IN ('held','pending_agreement','pending_approval','confirmed') LIMIT 1;
-- if found → refuse (use early return instead); else
UPDATE app.share_window SET status = 'cancelled' WHERE id = $w;
COMMIT;
```
  (Do not fold the booking check into the UPDATE's `WHERE NOT EXISTS`: on a lock wait, READ COMMITTED re-checks
  the target row but evaluates the sub-select against the old snapshot.)
* Early return (W3), one transaction in the slot's zone:
  1. `SELECT … FROM share_window WHERE id = $w FOR UPDATE`;
  2. `SELECT … FROM booking WHERE share_window_id = $w AND status = 'confirmed' AND period @> now() FOR UPDATE`;
  3. for each TH3 candidate slot of the same zone (ordered): `SAVEPOINT c; INSERT replacement booking
     (relocated_from_booking_id = old)`; on `23P01` `ROLLBACK TO c` and try the next;
  4. `UPDATE booking SET status = 'relocated'` (old), `UPDATE share_window SET status = 'closed_early', returned_at = now()`;
  5. **Settlement (D-09, rule `zone_policy.early_return_cost_rule = 'renter_pays_th3_relocated'`)**: insert
     `payment(kind = 'early_return_refund', booking = old, amount = unused share time)` and
     `payment(kind = 'relocation_th3', booking = replacement, amount = TH3 price for the relocated period)`, each with
     its own `thread_id:w3.*` key; the provider is charged nothing;
  6. `ledger_append(..., 'early_return_settlement', 'booking', old_id, {refund, th3_charge, provider_extra_cost: 0, rule}, thread_id:w3.ledger)`;
     outbox notifications. All in one transaction — tested end to end in 08 §9.2.
  Two renters relocated at the same time cannot get the same TH3 slot (EXCLUDE). No TH3 left → commit nothing,
  emit `EarlyReturnNoTh3` → W3 suggests other zones (FR-27) or opens an approval (`early_return_escalation`).

## 3. Agreement confirmation by both parties (M6, AC-07)

**Risk**: provider and renter confirm at the same moment; each sees the other as unconfirmed → agreement never
becomes effective (lost update), or becomes effective twice.

Single conditional UPDATE per confirmation; the row lock serializes the two and the second re-reads the first's
values:
```sql
UPDATE app.agreement
   SET renter_confirmed_at = now(),
       status = CASE WHEN provider_confirmed_at IS NULL THEN status
                     WHEN requires_approval            THEN 'pending_approval'
                     ELSE 'effective' END,
       effective_at = CASE WHEN provider_confirmed_at IS NOT NULL AND NOT requires_approval THEN now() END
 WHERE id = $1 AND status = 'pending_confirmation' AND renter_confirmed_at IS NULL AND confirm_deadline > now()
RETURNING status;
```
(The provider path is symmetric.) If `status = 'effective'` is returned, the same transaction calls
`ledger_append(..., idempotency_key = thread_id:w2.ledger)` and updates the booking to `confirmed`.
If `pending_approval` is returned, the same transaction inserts the `approval_request` and sets
`approval_request_id` (the CHECK forbids `pending_approval` without it).

**OTP** (attempt limit is enforced atomically, no read-then-write):
```sql
UPDATE app.otp_challenge SET attempts = attempts + 1
 WHERE id = $1 AND consumed_at IS NULL AND expires_at > now() AND attempts < max_attempts
RETURNING code_hash;            -- 0 rows → expired/locked; compare hash in the app (constant time)
UPDATE app.otp_challenge SET consumed_at = now() WHERE id = $1 AND consumed_at IS NULL;   -- on match
```

## 4. HITL approval decision (M12; W2/W3)

**Risks**: two BQLs decide the same request; a double click; resume runs twice.

```sql
UPDATE app.approval_request
   SET status = $decision, decided_by = $me, decided_at = now(), decision_note = $note
 WHERE id = $1 AND status = 'pending'          -- RLS restricts to the BQL's zones
RETURNING thread_id, kind, subject_id;
-- 0 rows → already decided: return 409 with the current state
INSERT INTO app.outbox (event_type, zone_id, payload) VALUES ('ApprovalDecided', $zone, ...);
```
The resume job (`agent.resume_workflow`) is enqueued from the outbox, never inside the HTTP request (ADR-0010).
Every write step after resume uses `thread_id:step` keys, so a double resume is harmless.
`approval_request_pending_uq` prevents two open requests for one subject.

## 5. Ledger append (M6)

**Risks**: two appends in one zone read the same tip (fork of the chain); a retried step appends twice.

`app.ledger_append` locks the zone's `ledger_head` row (`FOR UPDATE`), checks the idempotency key **under that
lock**, inserts, and advances the head. Concurrent appends in one zone queue on that row for the duration of one
INSERT + UPDATE. Measured: 4 sessions × 40 appends → seq 1…162 gap-free, `ledger_verify` = intact.
Appends in different zones never contend. The function is called last in its transaction, so the head lock is
held for microseconds (lock ordering rule).

## 6. LPR ingestion (N1)

**Risks**: vendor re-sends; two workers process the same file.

* `INSERT INTO app.lpr_event … ON CONFLICT (zone_id, source_code, source_event_id) DO NOTHING RETURNING id`. No
  row returned = duplicate: stop, no side effect (AC-10a). This is safe under concurrency. `lpr_event` is a plain
  table, so the dedupe key does not need the partition column.
* Low confidence (< `zone_policy.ocr_review_threshold`) → `status = 'pending_review'`; no outbox event (BR-13).
* One N1 worker per source at a time: `SELECT pg_try_advisory_xact_lock(hashtextextended('n1:' || $zone_id || ':' || $source_code, 0))`.

## 7. Payment (VietQR mock) (M7)

* Mark paid: `UPDATE payment SET status = 'paid_simulated', paid_at = now() WHERE id = $1 AND status = 'pending'`.
  `payment_paid_uq` prevents two successful payments of one kind for one booking.
* `payment.idempotency_key` makes a double-submitted "Pay" button harmless.

## 8. Deferred (see [11-deferred-tables](11-deferred-tables.md))

Concurrency recipes for features that are not in the MVP schema. They are kept in git (`333b85b:docs/database/05-concurrency.md`)
and must be re-derived with the table when it returns:

* **Swap application (M11/W6)**: `swap_proposal`/`swap_leg`, consent-first legs, lock order `slot_holding` by `slot_id`.
* **Overstay (N2 → W4)**: `overstay_case` `ON CONFLICT (booking_id)`, conditional reminder and charge UPDATEs; `parking_session` entry/exit pairing.
* **Voucher redemption**: conditional `UPDATE voucher … WHERE status = 'issued'` in the payment transaction.
* **Disputes (W5)**: evidence idempotency keys; the read-tx → LLM → write-tx shape in §12 still applies to any LLM step.

## 9. Auth (ADR-0006)

* Refresh rotation: `UPDATE refresh_token SET used_at = now() WHERE token_hash = $h AND used_at IS NULL AND
  revoked_at IS NULL AND expires_at > now() RETURNING user_id, family_id`. 0 rows but the hash exists with
  `used_at` set → **reuse**: `UPDATE refresh_token SET revoked_at = now() WHERE family_id = $f`.
* Failed logins: `UPDATE app_user SET failed_logins = failed_logins + 1, locked_until = CASE WHEN failed_logins + 1 >= $max
  THEN now() + $lock END WHERE id = $1` — atomic increment, no lost update (Redis rate limit stays the first line).

## 10. Configuration changes (M3)

New policy version: `INSERT INTO zone_policy (zone_id, version, …) SELECT $z, coalesce(max(version), 0) + 1, …`.
Two BQLs saving at once → one gets `23505` on `(zone_id, version)` → reload and retry. Agreements reference the
version id, so in-flight agreements keep their terms. Prices (`zone_policy.prices` jsonb) and the agreement template
(`zone_policy.agreement_template_md`) are part of the same row, so they are versioned and pinned together; the DB only
checks that `prices` is a JSON object, the rule engine (Pydantic) validates its shape before the INSERT.

## 11. Background jobs and the outbox

* Outbox relay: `SELECT … WHERE published_at IS NULL ORDER BY id LIMIT 100 FOR UPDATE SKIP LOCKED` → publish →
  `UPDATE outbox SET published_at = now()`. Delivery is **at least once**; consumers are idempotent
  (`notification.idempotency_key = 'outbox:' || id`).
* Singleton jobs per zone (N6 expiry, and any later N-job): `pg_try_advisory_xact_lock(hashtextextended('n6:' || zone_id, 0))`
  at the start of the job's transaction; `false` → another worker is on it, exit.
* Retention and erasure jobs are **not in the MVP** (no `purge_expired`, `drop_expired_lpr_partitions`, `erase_user`);
  see 07 §3 and [11-deferred-tables](11-deferred-tables.md). Without them `audit_log` stays strictly append-only.
* Hold sweeper: `UPDATE booking SET status = 'expired' WHERE status = 'held' AND hold_expires_at < now()` in batches
  of 500 (`ctid IN (SELECT … LIMIT 500 FOR UPDATE SKIP LOCKED)`).

## 12. Workflows with LLM steps (W2 suggestion; same shape for later W5)

```
tx1 (read): ledger rows, booking, policy            → commit
LLM call (no transaction, pseudonymised input)     → suggestion + confidence
tx2 (write): INSERT approval_request / booking (idempotency_key = thread_id:step), outbox
```
If the process dies between the LLM call and tx2, the step re-runs; the key makes tx2 insert once.
