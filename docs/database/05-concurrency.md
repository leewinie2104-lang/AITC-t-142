# 05 — Concurrency and integrity per sensitive flow

## 0. Ground rules (all flows)

| Rule | Detail |
|------|--------|
| Isolation | **READ COMMITTED** everywhere (Postgres default). Every invariant below is protected by a constraint, a row lock or a conditional UPDATE, so SERIALIZABLE's retry cost is not needed. Re-evaluate only if a new invariant cannot be expressed that way. |
| Transaction = one unit of work | Opened by `platform.db.unit_of_work(ctx)`, which runs `SET LOCAL app.user_id / app.role / app.zone_ids` (ADR-0005). One zone per transaction (a cross-zone step is two transactions). |
| No external calls inside a transaction | LLM (Bedrock), S3, notifications, WebSocket publish, arq enqueue: never inside. Pattern: *read tx → external call → write tx with an idempotency key*. Side effects after commit go through the **outbox** written in the same transaction. |
| Timeouts (role defaults in 02-schema §0) | `statement_timeout = 5s`, `lock_timeout = 2s`, `idle_in_transaction_session_timeout = 30s` for `parksmart_app`. Background jobs may `SET LOCAL statement_timeout = '60s'` for a known scan. Migrations: `lock_timeout = 5s` + retry. |
| Idempotency | Every write made by a workflow step or job carries `idempotency_key = thread_id:step` (or `source:event_id`). UNIQUE constraints turn a replay into `23505`, which the repository maps to "return the existing row". LangGraph re-runs the node containing `interrupt()` on resume; arq re-runs jobs. |
| Lock ordering (deadlock avoidance) | When a transaction locks several rows of one table, it locks them in **ascending primary key** order. Across tables the order is: `share_window` → `booking` → `slot_holding` → `swap_proposal` → `ledger_head`. `ledger_append` is always the last statement before the outbox insert. |
| Retries | Retry the whole transaction (max 3, jittered) on `40P01` deadlock, `55P03` lock timeout, `40001` serialization. Do **not** retry `23P01`/`23505`/`23514`: they are business answers. |
| Optimistic locking | User-edited rows with a `version` column (`booking`) use `UPDATE … SET version = version + 1 WHERE id = $1 AND version = $2`; 0 rows → `409 Conflict`. |

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
  5. `ledger_append(..., 'early_return_relocation', ..., thread_id:w3.ledger)`; outbox notifications.
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

## 4. HITL approval decision (M12; W2/W3/W5/W6)

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

## 6. Swap application (M11, W6)

**Risks**: holder changed since the proposal (stale proposal); two proposals touching the same slot applied
together; deadlock between them.

```sql
BEGIN;
UPDATE app.swap_proposal SET status = 'applied', applied_at = now()
 WHERE id = $p AND status = 'approved' RETURNING id;           -- 0 rows → already applied/rejected
SELECT id, slot_id, user_id FROM app.slot_holding
 WHERE slot_id = ANY ($slots) AND upper_inf(held_during)
 ORDER BY slot_id FOR UPDATE;                                   -- deterministic order → no deadlock
-- verify each leg: current holder = from_user_id; otherwise ROLLBACK and mark the proposal stale
UPDATE app.slot_holding SET held_during = tstzrange(lower(held_during), now()) WHERE id = ANY ($holding_ids);
INSERT INTO app.slot_holding (..., kind, held_during, swap_proposal_id) VALUES (..., 'swap_usage', tstzrange(now(), NULL), $p), ...;
SELECT * FROM app.ledger_append($zone, 'swap_applied', 'swap_proposal', $p, $payload, $thread || ':w6.ledger');
COMMIT;
```
`slot_holding_no_overlap` guarantees that even a buggy path cannot leave two holders on one slot.
Share windows already published by the old holder for the future are cancelled in the same transaction
(lock order: `share_window` first).

## 7. LPR ingestion (N1) and sessions

**Risks**: vendor re-sends; two workers process the same file; exit processed before entry.

* `INSERT INTO app.lpr_event … ON CONFLICT (source_id, source_event_id, occurred_at) DO NOTHING RETURNING id`. No
  row returned = duplicate: stop, no side effect (AC-10a). This is safe under concurrency.
* Low confidence (< `lpr_source.ocr_review_threshold`) → `status = 'pending_review'`; no session, no outbox event (BR-13).
* Entry → `INSERT parking_session … ON CONFLICT (zone_id, entry_event_id) DO NOTHING`.
* Exit → `UPDATE parking_session SET exit_event_id = $e, exited_at = $t WHERE zone_id = $z AND vehicle_id = $v AND
  exited_at IS NULL AND entered_at <= $t` (one row, the open session); 0 rows = orphan exit, kept for N3.
* One N1 worker per source at a time: `SELECT pg_try_advisory_xact_lock(hashtextextended('n1:' || $source_id, 0))`.

## 8. Overstay (N2 → W4) and charging

* Detect: `INSERT INTO app.overstay_case (booking_id, …) … ON CONFLICT (booking_id) DO NOTHING` — re-runs of N2 are no-ops.
* Remind: `UPDATE overstay_case SET reminder_count = reminder_count + 1, last_reminded_at = now()
  WHERE id = $1 AND status = 'open' AND (last_reminded_at IS NULL OR last_reminded_at < now() - $every)`
  — two workers cannot both send reminder n.
* Charge: `UPDATE overstay_case SET status = 'charged', fee_vnd = $fee, ended_at = $t WHERE id = $1 AND status = 'open'`
  + `payment (kind = 'overstay_fee', idempotency_key = 'overstay:' || booking_id)` + `ledger_append(…, 'overstay:' || booking_id)`.

## 9. Payment (VietQR mock) and vouchers (M7)

* Mark paid: `UPDATE payment SET status = 'paid_simulated', paid_at = now() WHERE id = $1 AND status = 'pending'`.
  `payment_paid_uq` prevents two successful payments of one kind for one booking.
* Redeem voucher (same transaction as the payment insert):
  `UPDATE voucher SET status = 'redeemed', redeemed_at = now() WHERE code = $c AND status = 'issued' AND
  valid_until > now() RETURNING id, value_vnd` → 0 rows = invalid/used. UNIQUE `payment.voucher_id` is the backstop.
* `payment.idempotency_key` makes a double-submitted "Pay" button harmless.

## 10. Auth (ADR-0006)

* Refresh rotation: `UPDATE refresh_token SET used_at = now() WHERE token_hash = $h AND used_at IS NULL AND
  revoked_at IS NULL AND expires_at > now() RETURNING user_id, family_id`. 0 rows but the hash exists with
  `used_at` set → **reuse**: `UPDATE refresh_token SET revoked_at = now() WHERE family_id = $f`.
* Failed logins: `UPDATE app_user SET failed_logins = failed_logins + 1, locked_until = CASE WHEN failed_logins + 1 >= $max
  THEN now() + $lock END WHERE id = $1` — atomic increment, no lost update (Redis rate limit stays the first line).

## 11. Configuration changes (M3)

New policy version: `INSERT INTO zone_policy (zone_id, version, …) SELECT $z, coalesce(max(version), 0) + 1, …`.
Two BQLs saving at once → one gets `23505` on `(zone_id, version)` → reload and retry. Agreements reference the
version id, so in-flight agreements keep their terms.

## 12. Background jobs and the outbox

* Outbox relay: `SELECT … WHERE published_at IS NULL ORDER BY id LIMIT 100 FOR UPDATE SKIP LOCKED` → publish →
  `UPDATE outbox SET published_at = now()`. Delivery is **at least once**; consumers are idempotent
  (`notification.idempotency_key = 'outbox:' || id`).
* Singleton jobs per zone (N3 reconciliation, N4 forecast, N6 expiry): `pg_try_advisory_xact_lock(hashtextextended('n3:' || zone_id, 0))`
  at the start of the job's transaction; `false` → another worker is on it, exit.
* Hold sweeper: `UPDATE booking SET status = 'expired' WHERE status = 'held' AND hold_expires_at < now()` in batches
  of 500 (`ctid IN (SELECT … LIMIT 500 FOR UPDATE SKIP LOCKED)`).

## 13. Workflows with LLM steps (W5 dispute, W2 suggestion)

```
tx1 (read): ledger rows, LPR rows, booking         → commit
LLM call (no transaction, pseudonymised input)     → summary + confidence
tx2 (write): INSERT dispute_ticket (idempotency_key = thread_id:w5.ticket), evidence, approval_request, outbox
```
If the process dies between the LLM call and tx2, the step re-runs; the key makes tx2 insert once.
