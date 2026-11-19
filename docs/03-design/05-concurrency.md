# 05 — Concurrency and integrity per sensitive flow

## 0. Ground rules (all flows)

| Rule | Detail |
|------|--------|
| Isolation | **READ COMMITTED** everywhere (Postgres default). Every invariant below is protected by a constraint, a row lock or a conditional UPDATE, so SERIALIZABLE's retry cost is not needed. Re-evaluate only if a new invariant cannot be expressed that way. |
| Transaction = one unit of work | Opened by `platform.db.unit_of_work(ctx)`, which runs `SET LOCAL app.user_id / app.role / app.zone_ids` (ADR-0005). One zone per transaction (a cross-zone step is two transactions). |
| No external calls inside a transaction | LLM (Bedrock), S3, notifications, WebSocket publish, arq enqueue: never inside. Pattern: *read tx → external call → write tx with an idempotency key*. In v4 there is no outbox ([ADR-0011](../10-adr/ADR-0011-mvp-simplifications.md)): the use case inserts the `notification` row in the same transaction and pushes the realtime message **after commit** through the `platform.publish()` port; a lost push is recovered from the `notification` list. The port lets an outbox return later without touching use cases. |
| Timeouts (role defaults in schema.sql §0) | `statement_timeout = 5s`, `lock_timeout = 2s`, `idle_in_transaction_session_timeout = 30s` for `parksmart_app`. Background jobs may `SET LOCAL statement_timeout = '60s'` for a known scan. Migrations: `lock_timeout = 5s` + retry. |
| Idempotency | Every write made by a workflow step or job carries `idempotency_key = thread_id:step` (or `source:event_id`). UNIQUE constraints turn a replay into `23505`, which the repository maps to "return the existing row". LangGraph re-runs the node containing `interrupt()` on resume; arq re-runs jobs. |
| Lock ordering (deadlock avoidance) | When a transaction locks several rows of one table, it locks them in **ascending primary key** order. Across tables the order is: `share_window` → `booking` → `slot_holding` → `recovery_case`. Append-only inserts (`consent_record`, `ai_decision_log`, `notification`) come last. |
| Retries | Retry the whole transaction (max 3, jittered) on `40P01` deadlock, `55P03` lock timeout, `40001` serialization. Do **not** retry `23P01`/`23505`/`23514`: they are business answers. |
| Optimistic locking | User-edited rows with a `version` column (`booking`) use `UPDATE … SET version = version + 1 WHERE id = $1 AND version = $2`; 0 rows → `409 Conflict`. |

### 0.1 Idempotency inventory (check d, v4)

Every table written by a workflow step or job, and what makes a replay harmless:

| Write target | Replay guard |
|--------------|--------------|
| `parking_request`, `booking`, `payment`, `notification`, `share_window`, `recovery_case`, `ai_decision_log` | UNIQUE `idempotency_key` column on the table itself (there is no `idempotency_keys` table in v4). `share_window`: a replayed publish would otherwise hit the EXCLUDE as `23P01`. `ai_decision_log`: key = `thread_id:checkpoint_id:node` |
| `agreement` | UNIQUE `booking_id` |
| `approval_request` | partial UNIQUE `(kind, subject_id) WHERE status = 'pending'` + conditional decision UPDATE |
| `consent_record` | natural key: UNIQUE `(user_id, action, subject_id, terms_version, decision)`; a replayed confirmation is `23505` → treat as done (`ON CONFLICT DO NOTHING`) |
| `recovery_case` | besides the key, partial UNIQUE `recovery_case_open_uq (booking_id) WHERE status NOT IN ('resolved','cancelled')`: one open case per booking |
| `agent_thread` | PK `thread_id` + `INSERT … ON CONFLICT (thread_id) DO UPDATE` (status, `pending_card`) |
| `lpr_event` | UNIQUE `(zone_id, source_code, source_event_id)` + `ON CONFLICT DO NOTHING` |
| `slot_holding` | EXCLUDE overlap |

The agreement confirmation OTP (hash, TTL, attempt counter) lives in Redis, not in the database
([ADR-0011](../10-adr/ADR-0011-mvp-simplifications.md)); its atomic counter is a Redis operation.

Deferred write targets (`voucher`, `dispute_evidence`, `swap_proposal`, `overstay_case`, `parking_session`,
`vacancy_forecast`, `occupancy_hourly`, `reconciliation_report`, `privacy_request`, `workflow_run`,
`plate_access_log`, and the v4 removals `outbox`, `idempotency_keys`, `audit_log`, `otp_challenge`, `ledger_entry`)
and their guards: see [08-deferred-tables](08-deferred-tables.md). `kpi_daily` is now a view and needs no guard.

No workflow or job write target of the 23-table schema is left without a guard.

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
-- 3. notification in the same transaction (realtime push happens after COMMIT, via platform.publish())
INSERT INTO app.notification (user_id, zone_id, kind, title, body, link, idempotency_key) VALUES (..., 'booking_held', ..., $thread_step || ':notify');
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
  4. open the case first (`INSERT INTO recovery_case … idempotency_key = thread_id:w3.case`; the partial UNIQUE
     `recovery_case_open_uq` rejects a second open case for the same booking with `23505` → load the existing one),
     fill `options` from the rule engine; after the renter's choice (`consent_record`, `accept_relocation`) set
     `chosen_slot_id`;
  4b. `UPDATE booking SET status = 'relocated'` (old), `UPDATE share_window SET status = 'closed_early', returned_at = now()`;
  5. **Settlement (D-09, rule `zone_policy.early_return_cost_rule = 'renter_pays_th3_relocated'`)**: insert
     `payment(kind = 'early_return_refund', booking = old, amount = unused share time)` and
     `payment(kind = 'relocation_th3', booking = replacement, amount = TH3 price for the relocated period)`, each with
     its own `thread_id:w3.*` key; the provider is charged nothing;
  6. `UPDATE recovery_case SET status = 'resolved', relocated_booking_id = $new, version = version + 1 WHERE id = $c AND version = $v`
     (CHECK `recovery_case_resolved_has_booking`), the refund / TH3 charge split is visible in the two payments
     (provider extra cost 0); `notification` rows. All in one transaction (the v2 end-to-end test used a ledger row
     for the settlement; in v4 the evidence is the `consent_record` of the renter's acceptance).
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
(The provider path is symmetric.) If `status = 'effective'` is returned, the same transaction
inserts the `consent_record` rows (`action = 'agreement_confirm'`, `evidence.body_sha256` = hash nội dung thỏa thuận;
natural key makes a replay a no-op) and updates the booking to `confirmed`.
If `pending_approval` is returned, the same transaction inserts the `approval_request` and sets
`approval_request_id` (the CHECK forbids `pending_approval` without it).

**OTP** (v4: kept in Redis, no `otp_challenge` table). The attempt limit must still be atomic: `INCR` the attempt
counter key (with the same TTL as the code) and refuse above 5; compare the stored hash in the app (constant time);
delete the key on a match. Only the successful confirmation reaches the database (`agreement.*_confirmed_at` and one
`consent_record` row).

## 4. HITL approval decision (M12; W2/W3)

**Risks**: two BQLs decide the same request; a double click; resume runs twice.

```sql
UPDATE app.approval_request
   SET status = $decision, decided_by = $me, decided_at = now(), decision_note = $note
 WHERE id = $1 AND status = 'pending'          -- RLS restricts to the BQL's zones
RETURNING thread_id, kind, subject_id;
-- 0 rows → already decided: return 409 with the current state
INSERT INTO app.notification (...) VALUES (...);          -- same transaction; realtime push after COMMIT
```
The resume job (`agent.resume_workflow`) is enqueued **after commit** by the use case (v4: no outbox; the arq enqueue
is retried by the caller and a double resume is harmless, see below), never inside the HTTP request (ADR-0010).
Every write step after resume uses `thread_id:step` keys, so a double resume is harmless.
`approval_request_pending_uq` prevents two open requests for one subject.

## 5. Consent evidence and recovery case (M6, W3)

**Risks**: a confirmation recorded twice; two open recovery cases for one booking; evidence edited afterwards.

* `consent_record` is insert-only: the statement trigger `reject_mutation()` rejects UPDATE/DELETE/TRUNCATE (even for
  the owner) and the app role has INSERT + SELECT only. The natural key `UNIQUE (user_id, action, subject_id,
  terms_version, decision)` serialises two concurrent inserts of the same confirmation: the second waits, then gets
  `23505`, which the repository treats as "already recorded". Two different parties confirming the same agreement
  write different `user_id`s, so they never contend.
* `recovery_case`: `recovery_case_open_uq` (partial UNIQUE on `booking_id` while the status is not `resolved` or
  `cancelled`) lets only one of two concurrent W3 runs open a case; the loser reads the existing case. State changes
  use `UPDATE … WHERE id = $1 AND version = $2` (optimistic lock, 0 rows → reload).
* **Ledger serialisation (deferred).** The v1–v3 `ledger_append` locked the zone's `ledger_head` row and chained
  hashes; that function, `ledger_head` and `ledger_entry` are removed in v4 (ADR-0011). If a hash chain returns, re-derive
  this section: lock the head row last in the transaction, check the idempotency key under the lock, one chain per
  zone (see [08-deferred-tables](08-deferred-tables.md) and `git show` of the v3 version of this file).

## 6. LPR ingestion (N1)

**Risks**: vendor re-sends; two workers process the same file.

* `INSERT INTO app.lpr_event … ON CONFLICT (zone_id, source_code, source_event_id) DO NOTHING RETURNING id`. No
  row returned = duplicate: stop, no side effect (AC-10a). This is safe under concurrency. `lpr_event` is a plain
  table, so the dedupe key does not need the partition column.
* Low confidence (< `zone_policy.ocr_review_threshold`) → `status = 'pending_review'`; no notification and no workflow trigger (BR-13).
* One N1 worker per source at a time: `SELECT pg_try_advisory_xact_lock(hashtextextended('n1:' || $zone_id || ':' || $source_code, 0))`.

## 7. Payment (VietQR mock) (M7)

* Mark paid: `UPDATE payment SET status = 'paid_simulated', paid_at = now() WHERE id = $1 AND status = 'pending'`.
  `payment_paid_uq` prevents two successful payments of one kind for one booking.
* `payment.idempotency_key` makes a double-submitted "Pay" button harmless.

## 8. Deferred (see [08-deferred-tables](08-deferred-tables.md))

Concurrency recipes for features that are not in the MVP schema. They are kept in git (`333b85b:docs/database/05-concurrency.md`)
and must be re-derived with the table when it returns:

* **Swap application (M11/W6)**: `swap_proposal`/`swap_leg`, consent-first legs, lock order `slot_holding` by `slot_id`.
* **Overstay (N2 → W4)**: `overstay_case` `ON CONFLICT (booking_id)`, conditional reminder and charge UPDATEs; `parking_session` entry/exit pairing.
* **Voucher redemption**: conditional `UPDATE voucher … WHERE status = 'issued'` in the payment transaction.
* **Disputes (W5)**: evidence idempotency keys; the read-tx → LLM → write-tx shape in §12 still applies to any LLM step.

## 9. Auth (ADR-0006, partly superseded by ADR-0011)

* No refresh token in the demo (v4): only an access JWT with an 8-hour lifetime, no revocation and no reuse detection.
  The rotation recipe (`UPDATE refresh_token SET used_at … WHERE token_hash = $h AND used_at IS NULL …`, reuse revokes
  the family) comes back with the table, before real users (see [08-deferred-tables](08-deferred-tables.md)).
* Failed logins: `UPDATE app_user SET failed_logins = failed_logins + 1, locked_until = CASE WHEN failed_logins + 1 >= $max
  THEN now() + $lock END WHERE id = $1` — atomic increment, no lost update (Redis rate limit stays the first line).

## 10. Configuration changes (M3)

New policy version: `INSERT INTO zone_policy (zone_id, version, …) SELECT $z, coalesce(max(version), 0) + 1, …`.
Two BQLs saving at once → one gets `23505` on `(zone_id, version)` → reload and retry. Agreements reference the
version id, so in-flight agreements keep their terms. Prices (`zone_policy.prices` jsonb) and the agreement template
(`zone_policy.agreement_template_md`) are part of the same row, so they are versioned and pinned together; the DB only
checks that `prices` is a JSON object, the rule engine (Pydantic) validates its shape before the INSERT.

## 11. Background jobs (no outbox in v4)

* Outbox relay: **deferred** with `outbox` (ADR-0011; it returns with the Ưu tiên 3 jobs that trigger Agent workflows).
  Until then the relay recipe (`FOR UPDATE SKIP LOCKED`, at-least-once delivery, idempotent consumers) is not needed:
  use cases write `notification` in their own transaction and publish after commit.
* Singleton jobs per zone (N6 expiry, and any later N-job): `pg_try_advisory_xact_lock(hashtextextended('n6:' || zone_id, 0))`
  at the start of the job's transaction; `false` → another worker is on it, exit.
* Retention and erasure jobs are **not in the MVP** (no `purge_expired`, `drop_expired_lpr_partitions`, `erase_user`);
  see 01-database-operations §3 and [08-deferred-tables](08-deferred-tables.md). Without them `consent_record` and `ai_decision_log` stay strictly append-only.
* Hold sweeper: `UPDATE booking SET status = 'expired' WHERE status = 'held' AND hold_expires_at < now()` in batches
  of 500 (`ctid IN (SELECT … LIMIT 500 FOR UPDATE SKIP LOCKED)`).

## 12. Workflows with LLM steps (W2 suggestion; same shape for later W5)

```
tx1 (read): booking, agreement evidence, policy     → commit
LLM call (no transaction, pseudonymised input)     → suggestion + confidence
tx2 (write): INSERT approval_request / booking (idempotency_key = thread_id:step), notification,
             ai_decision_log (idempotency_key = thread_id:checkpoint_id:node)
```
If the process dies between the LLM call and tx2, the step re-runs; the keys make tx2 insert once (the
`ai_decision_log` row is logged once per node, even after an `interrupt()` replay).
