-- =====================================================================================================
-- ParkSmart AI — demo seed + constraint / RLS proofs (v7, 26 tables — plan 024: owner OTP and listing expiry, renter ETA / OTP / hold,
-- two-layer approval review, BQL registry import; v6, 25 tables — plan 003: v4 lean MVP of plan 002 / ADR-0011 / D-32
-- plus overstay fee and disputes; plan 023: pilot queue, owner exit, early return with renter priority, fee ledger)
-- The app's own repeatable demo seed (Python, app plate crypto, idempotent) is server/src/demo_seed; this file stays the
-- constraint / RLS proof script.
-- Run after docs/03-design/sql/schema.sql on an EMPTY database, as the schema owner (or a superuser in a scratch DB):
--   psql -v ON_ERROR_STOP=1 -f docs/03-design/sql/seed-and-tests.sql
-- Every negative test goes through pg_temp.expect_fail(): it runs the statement in a sub-transaction and
-- aborts the whole script ("FAIL …") if the database ACCEPTS it or rejects it with an unexpected SQLSTATE.
-- Expected output: only "PASS …" / "OK …" lines.
-- v6: section 11 proves the pilot changes (queue shape, owner exit, renter decision, intake pause, fee ledger, refund).
-- v5: section 10 proves overstay (zone_policy columns, overstay_fee payment guard, reminder keys) and disputes (dispute_case,
-- dispute_evidence: CHECKs, append-only, RLS, masked evidence, decision flow, KPI columns). It runs last so that the row counts of
-- sections 5-9 stay valid.
-- v4: proofs of the deferred tables (swaps, vouchers, erasure, retention, partitions, plate reveal, ledger,
-- staff_zone, refresh_token, otp_challenge, outbox, idempotency_keys, audit_log) are gone with them; the v2 script is in
-- git: git show 333b85b:docs/database/08-seed-and-tests.sql. New proofs: agent_thread, recovery_case, consent_record,
-- ai_decision_log, app_user.staff_zone_id, slot.operational_status, booking.checked_in_at / checked_out_at.
--
-- Scenario (Scope §1): one operator, 3 zones.
--   A: residential + low-rise shophouses. Tower A1 (TH1 + TH2 slots), public lot APL (TH3).
--   B: residential. Tower B1.
--   C: offices/school. Tower C1 with a TH2 pool open to the whole chain, public lot CPL (TH3).
--   Users: lan (A1 owner, holds TH1 B2-045/B2-046), binh (A1 owner, L1 at A1), minh (low-rise shophouse in A
--   + apartment in B → L2 in A, L1 in B1, L3 in C — AC-19), hoa (B1 resident → L3 in C — AC-20), tuan
--   (A1 tenant, expired yesterday — AC-22), khach (guest, L4), van (C1 resident, holds TH2 B1-010),
--   bql_a / bql_c (BQL), guard_a, op (chain operator).
-- =====================================================================================================
\set ON_ERROR_STOP 1
\pset footer off
\pset tuples_only on
SET client_min_messages = warning;

-- Seed runs as a system job covering all three zones (the booking trigger derives levels in this context).
SELECT set_config('app.role', 'system', false) \gset ignored_

-- Local dates in Asia/Ho_Chi_Minh; the demo window is "tomorrow" so the script never goes stale.
SELECT ((now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date + 1)::text AS d1,
       ((now() AT TIME ZONE 'Asia/Ho_Chi_Minh')::date - 1)::text AS d_yesterday \gset

-- p_msg (optional): a substring the error message must contain, so a rule is proven by the right check and
-- not by an unrelated constraint that happens to share the SQLSTATE.
CREATE FUNCTION pg_temp.expect_fail(p_label text, p_sql text, p_state text DEFAULT NULL, p_msg text DEFAULT NULL)
RETURNS text LANGUAGE plpgsql AS $$
BEGIN
  BEGIN
    EXECUTE p_sql;
  EXCEPTION WHEN OTHERS THEN
    IF p_state IS NOT NULL AND SQLSTATE <> p_state THEN
      RAISE EXCEPTION 'FAIL % : expected SQLSTATE %, got % (%)', p_label, p_state, SQLSTATE, SQLERRM;
    END IF;
    IF p_msg IS NOT NULL AND strpos(SQLERRM, p_msg) = 0 THEN
      RAISE EXCEPTION 'FAIL % : expected message containing "%", got "%"', p_label, p_msg, SQLERRM;
    END IF;
    RETURN format('PASS  %-52s [%s] %s', p_label, SQLSTATE, left(SQLERRM, 80));
  END;
  RAISE EXCEPTION 'FAIL % : the database accepted a statement it must reject', p_label;
END $$;

CREATE FUNCTION pg_temp.expect(p_label text, p_ok boolean) RETURNS text LANGUAGE plpgsql AS $$
BEGIN
  IF p_ok IS NOT TRUE THEN
    RAISE EXCEPTION 'FAIL % : assertion is false', p_label;
  END IF;
  RETURN format('OK    %s', p_label);
END $$;

\echo '== 1. Seed: organisation, slots, policy'
INSERT INTO app.zone (code, name) VALUES ('A', 'Khu A') RETURNING id AS zone_a \gset
INSERT INTO app.zone (code, name) VALUES ('B', 'Khu B') RETURNING id AS zone_b \gset
INSERT INTO app.zone (code, name) VALUES ('C', 'Khu C') RETURNING id AS zone_c \gset
SELECT set_config('app.zone_ids', format('{%s,%s,%s}', :'zone_a', :'zone_b', :'zone_c'), false) \gset ignored_

-- subzone_code replaces the v2 subzone table.
INSERT INTO app.building (zone_id, subzone_code, code, name, kind) VALUES (:'zone_a', 'A-S1', 'A1', 'Tòa A1', 'residential_tower') RETURNING id AS bld_a1 \gset
INSERT INTO app.building (zone_id, subzone_code, code, name, kind) VALUES (:'zone_a', 'A-S1', 'ALR', 'Cụm shophouse A', 'lowrise_cluster') RETURNING id AS bld_alr \gset
INSERT INTO app.building (zone_id, subzone_code, code, name, kind) VALUES (:'zone_a', 'A-S1', 'APL', 'Bãi công cộng A', 'public_lot') RETURNING id AS bld_apl \gset
INSERT INTO app.building (zone_id, subzone_code, code, name, kind) VALUES (:'zone_b', 'B-S1', 'B1', 'Tòa B1', 'residential_tower') RETURNING id AS bld_b1 \gset
INSERT INTO app.building (zone_id, subzone_code, code, name, kind) VALUES (:'zone_c', 'C-S1', 'C1', 'Tòa C1', 'residential_tower') RETURNING id AS bld_c1 \gset
INSERT INTO app.building (zone_id, subzone_code, code, name, kind) VALUES (:'zone_c', NULL, 'CPL', 'Bãi công cộng C', 'public_lot') RETURNING id AS bld_cpl \gset

INSERT INTO app.slot_pool (zone_id, building_id, slot_type, max_open_scope) VALUES (:'zone_a', :'bld_a1', 'TH1', 'building') RETURNING id AS pool_a1_th1 \gset
INSERT INTO app.slot_pool (zone_id, building_id, slot_type, max_open_scope, investor_consent_at) VALUES (:'zone_a', NULL, 'TH2', 'zone', now()) RETURNING id AS pool_a_th2 \gset
INSERT INTO app.slot_pool (zone_id, building_id, slot_type, max_open_scope) VALUES (:'zone_a', NULL, 'TH3', 'public') RETURNING id AS pool_a_th3 \gset
INSERT INTO app.slot_pool (zone_id, building_id, slot_type, max_open_scope) VALUES (:'zone_b', :'bld_b1', 'TH1', 'building') RETURNING id AS pool_b1_th1 \gset
INSERT INTO app.slot_pool (zone_id, building_id, slot_type, max_open_scope, investor_consent_at) VALUES (:'zone_c', NULL, 'TH2', 'chain', now()) RETURNING id AS pool_c_th2 \gset
INSERT INTO app.slot_pool (zone_id, building_id, slot_type, max_open_scope) VALUES (:'zone_c', NULL, 'TH3', 'public') RETURNING id AS pool_c_th3 \gset

-- level_code replaces the v2 basement table; size_class is the ordered enum S < M < L < XL.
INSERT INTO app.slot (zone_id, building_id, pool_id, slot_type, level_code, code, size_class) VALUES (:'zone_a', :'bld_a1', :'pool_a1_th1', 'TH1', 'B2', 'B2-045', 'M') RETURNING id AS s_045 \gset
INSERT INTO app.slot (zone_id, building_id, pool_id, slot_type, level_code, code, size_class) VALUES (:'zone_a', :'bld_a1', :'pool_a1_th1', 'TH1', 'B2', 'B2-046', 'S') RETURNING id AS s_046 \gset
INSERT INTO app.slot (zone_id, building_id, pool_id, slot_type, level_code, code, size_class) VALUES (:'zone_a', :'bld_a1', :'pool_a_th2', 'TH2', 'B2', 'B2-101', 'L') RETURNING id AS s_101 \gset
INSERT INTO app.slot (zone_id, building_id, pool_id, slot_type, level_code, code, size_class) VALUES (:'zone_a', :'bld_apl', :'pool_a_th3', 'TH3', 'G', 'TH3-012', 'L') RETURNING id AS s_th3_a \gset
INSERT INTO app.slot (zone_id, building_id, pool_id, slot_type, level_code, code, size_class) VALUES (:'zone_a', :'bld_apl', :'pool_a_th3', 'TH3', 'G', 'TH3-013', 'L') RETURNING id AS s_th3_a2 \gset
INSERT INTO app.slot (zone_id, building_id, pool_id, slot_type, level_code, code, size_class) VALUES (:'zone_b', :'bld_b1', :'pool_b1_th1', 'TH1', 'B1', 'B1-001', 'M') RETURNING id AS s_b1 \gset
INSERT INTO app.slot (zone_id, building_id, pool_id, slot_type, level_code, code, size_class) VALUES (:'zone_c', :'bld_c1', :'pool_c_th2', 'TH2', 'B1', 'B1-010', 'L') RETURNING id AS s_c010 \gset
INSERT INTO app.slot (zone_id, building_id, pool_id, slot_type, level_code, code, size_class) VALUES (:'zone_c', :'bld_cpl', :'pool_c_th3', 'TH3', 'G', 'TH3-001', 'L') RETURNING id AS s_th3_c \gset

-- Zone policies take every default from the column DEFAULTs, i.e. the researched defaults of docs/03-design/07-db-decision-log.md:
-- buffers 15/30 min, approval threshold 1 000 000 đ, hold ETA + 10 min (max 40, TH3 60), renter OTP 3 min, confirm 30 min, BR-16 carry-over 7 days,
-- OCR review threshold 0.800. ALL ARE "default, confirm with BQL".
-- Prices (D-01), default, confirm with BQL. Anchors: PRD §8 (~50 000 đ/day for L1–L2, outside parking 20–70 000 đ/h);
-- Hanoi 2026 street parking 45 000 đ/60 min inside Ring 1 (VOV, 2026-10-18). The rule engine caps hourly sums at the
-- day price. L3 sits between members and guests (PRD §8). v3: the v2 price_rule rows are this one jsonb document.
\set prices '{"TH1":{"L1":{"hour":10000,"day":50000},"L2":{"hour":10000,"day":50000}},"TH2":{"L1":{"hour":10000,"day":50000},"L2":{"hour":10000,"day":50000},"L3":{"hour":15000,"day":70000}},"TH3":{"L1":{"hour":20000},"L2":{"hour":20000},"L3":{"hour":20000},"L4":{"hour":30000}}}'
-- v3: the agreement text is part of the policy version (the v2 agreement_template table).
\set tpl '# Thỏa thuận chia sẻ chỗ đỗ — Bên cho thuê {{provider}} chia sẻ chỗ {{slot}} cho Bên thuê {{renter}} trong khoảng {{period}}, giá {{price_vnd}} đ. Hai bên xác nhận bằng mã OTP.'
INSERT INTO app.zone_policy (zone_id, version, effective_from, prices, agreement_template_md)
VALUES (:'zone_a', 1, now() - interval '30 days', :'prices'::jsonb, :'tpl') RETURNING id AS pol_a \gset
INSERT INTO app.zone_policy (zone_id, version, effective_from, prices, agreement_template_md)
VALUES (:'zone_c', 1, now() - interval '30 days', :'prices'::jsonb, :'tpl') RETURNING id AS pol_c \gset


\echo '== 2. Seed: people, eligibility, vehicles, holdings'
\set pw '$argon2id$v=19$m=65536,t=3,p=4$c2FsdHNhbHQ$ZGVtb2hhc2hkZW1vaGFzaA'
INSERT INTO app.app_user (full_name, phone_e164, password_hash) VALUES ('Nguyễn Thị Lan', '+84901000001', :'pw') RETURNING id AS u_lan \gset
INSERT INTO app.app_user (full_name, phone_e164, password_hash) VALUES ('Trần Văn Bình', '+84901000002', :'pw') RETURNING id AS u_binh \gset
INSERT INTO app.app_user (full_name, phone_e164, password_hash) VALUES ('Lê Minh', '+84901000003', :'pw') RETURNING id AS u_minh \gset
INSERT INTO app.app_user (full_name, phone_e164, password_hash) VALUES ('Phạm Thu Hoa', '+84901000004', :'pw') RETURNING id AS u_hoa \gset
INSERT INTO app.app_user (full_name, phone_e164, password_hash, role) VALUES ('Đỗ Tuấn', '+84901000005', :'pw', 'renter') RETURNING id AS u_tuan \gset
INSERT INTO app.app_user (full_name, phone_e164, password_hash, role) VALUES ('Khách Vãng Lai', '+84901000006', :'pw', 'renter') RETURNING id AS u_khach \gset
INSERT INTO app.app_user (full_name, phone_e164, password_hash) VALUES ('Vũ Văn', '+84901000007', :'pw') RETURNING id AS u_van \gset
-- v4: one zone per staff member (app_user.staff_zone_id replaces the staff_zone junction table).
INSERT INTO app.app_user (full_name, phone_e164, password_hash, role, staff_zone_id) VALUES ('BQL Khu A', '+84902000001', :'pw', 'zone_manager', :'zone_a') RETURNING id AS u_bql_a \gset
INSERT INTO app.app_user (full_name, phone_e164, password_hash, role, staff_zone_id) VALUES ('BQL Khu C', '+84902000003', :'pw', 'zone_manager', :'zone_c') RETURNING id AS u_bql_c \gset
INSERT INTO app.app_user (full_name, phone_e164, password_hash, role, staff_zone_id) VALUES ('Bảo vệ A', '+84903000001', :'pw', 'guard', :'zone_a') RETURNING id AS u_guard_a \gset
INSERT INTO app.app_user (full_name, phone_e164, password_hash, role) VALUES ('Vận hành chuỗi', '+84904000001', :'pw', 'chain_operator') RETURNING id AS u_op \gset
-- Registration consent (A-03 / BR-09): append-only evidence, one row per account (chain-wide, zone_id NULL).
INSERT INTO app.consent_record (user_id, zone_id, action, subject_type, subject_id, terms_version, decision, evidence)
SELECT id, NULL, 'registration_terms', 'app_user', id, 'v1', 'accepted', jsonb_build_object('channel', 'app') FROM app.app_user;

INSERT INTO app.asset (zone_id, building_id, kind, code) VALUES (:'zone_a', :'bld_a1', 'apartment', 'A1-12-05') RETURNING id AS a_lan \gset
INSERT INTO app.asset (zone_id, building_id, kind, code) VALUES (:'zone_a', :'bld_a1', 'apartment', 'A1-15-01') RETURNING id AS a_binh \gset
INSERT INTO app.asset (zone_id, building_id, kind, code) VALUES (:'zone_a', NULL, 'shophouse', 'ALR-S07') RETURNING id AS a_shop \gset
INSERT INTO app.asset (zone_id, building_id, kind, code) VALUES (:'zone_b', :'bld_b1', 'apartment', 'B1-08-02') RETURNING id AS a_minh_b \gset
INSERT INTO app.asset (zone_id, building_id, kind, code) VALUES (:'zone_b', :'bld_b1', 'apartment', 'B1-10-10') RETURNING id AS a_hoa \gset
INSERT INTO app.asset (zone_id, building_id, kind, code) VALUES (:'zone_a', :'bld_a1', 'apartment', 'A1-20-03') RETURNING id AS a_tuan \gset
INSERT INTO app.asset (zone_id, building_id, kind, code) VALUES (:'zone_c', :'bld_c1', 'apartment', 'C1-05-05') RETURNING id AS a_van \gset

INSERT INTO app.eligibility (user_id, asset_id, zone_id, role, valid_during, status, verified_by, verified_at) VALUES
  (:'u_lan',  :'a_lan',    :'zone_a', 'owner',  tstzrange('2020-01-01', NULL), 'verified', :'u_bql_a', now()),
  (:'u_binh', :'a_binh',   :'zone_a', 'owner',  tstzrange('2020-01-01', NULL), 'verified', :'u_bql_a', now()),
  (:'u_minh', :'a_shop',   :'zone_a', 'owner',  tstzrange('2021-01-01', NULL), 'verified', :'u_bql_a', now()),
  (:'u_minh', :'a_minh_b', :'zone_b', 'owner',  tstzrange('2021-01-01', NULL), 'verified', :'u_bql_a', now()),
  (:'u_hoa',  :'a_hoa',    :'zone_b', 'owner',  tstzrange('2022-01-01', NULL), 'verified', :'u_bql_a', now()),
  -- AC-22: lease ended at the end of yesterday (local).
  (:'u_tuan', :'a_tuan',   :'zone_a', 'tenant', tstzrange('2025-01-01', (:'d_yesterday' || ' 24:00+07')::timestamptz), 'verified', :'u_bql_a', now()),
  (:'u_van',  :'a_van',    :'zone_c', 'owner',  tstzrange('2020-01-01', NULL), 'verified', :'u_bql_c', now());

INSERT INTO app.slot_holding (zone_id, slot_id, slot_type, user_id, kind, held_during) VALUES
  (:'zone_a', :'s_045',  'TH1', :'u_lan',  'owner',  tstzrange('2020-01-01', NULL)),
  (:'zone_a', :'s_046',  'TH1', :'u_lan',  'owner',  tstzrange('2020-01-01', NULL)),
  (:'zone_a', :'s_101',  'TH2', :'u_binh', 'lessee', tstzrange('2024-01-01', NULL)),
  (:'zone_c', :'s_c010', 'TH2', :'u_van',  'lessee', tstzrange('2024-01-01', NULL));

-- Plates: demo encryption with pgcrypto; the app uses AES-GCM with a KMS/SSM key (docs/06-operations/02-database-security.md §3).
\set demo_key 'demo-plate-key'
\set pepper 'demo-plate-pepper'
INSERT INTO app.vehicle (user_id, plate_ciphertext, plate_hash, plate_masked, size_class)
SELECT u, pgp_sym_encrypt(p, :'demo_key'), hmac(p, :'pepper', 'sha256'), m, s::app.size_class
FROM (VALUES (:'u_lan'::uuid, '30A12345', '30A-•••.45', 'M'), (:'u_binh'::uuid, '30A22222', '30A-•••.22', 'M'),
             (:'u_binh'::uuid, '29C99999', '29C-•••.99', 'XL'), (:'u_minh'::uuid, '51G33333', '51G-•••.33', 'M'),
             (:'u_hoa'::uuid, '30E44444', '30E-•••.44', 'M'), (:'u_tuan'::uuid, '30F55555', '30F-•••.55', 'M'),
             (:'u_khach'::uuid, '29H66666', '29H-•••.66', 'M')) AS v(u, p, m, s);
SELECT id AS v_binh FROM app.vehicle WHERE user_id = :'u_binh' AND size_class = 'M' \gset
SELECT id AS v_binh_xl FROM app.vehicle WHERE user_id = :'u_binh' AND size_class = 'XL' \gset
SELECT id AS v_minh FROM app.vehicle WHERE user_id = :'u_minh' \gset
SELECT id AS v_hoa FROM app.vehicle WHERE user_id = :'u_hoa' \gset
SELECT id AS v_tuan FROM app.vehicle WHERE user_id = :'u_tuan' \gset
SELECT id AS v_khach FROM app.vehicle WHERE user_id = :'u_khach' \gset

\echo '== 3. Seed: main flow (share → request → booking → agreement → consent evidence → payment)'
-- Lan shares B2-045 tomorrow 07:45–18:00; default buffers 15 min before / 30 min after → bookable 08:00–17:30.
INSERT INTO app.share_window (zone_id, slot_id, owner_user_id, period, bookable_period, open_scope, idempotency_key, owner_otp_confirmed_at, expires_at)
VALUES (:'zone_a', :'s_045', :'u_lan',
        tstzrange((:'d1' || ' 07:45+07')::timestamptz, (:'d1' || ' 18:00+07')::timestamptz),
        tstzrange((:'d1' || ' 08:00+07')::timestamptz, (:'d1' || ' 17:30+07')::timestamptz), 'building', 'thread-lan:w2.publish', now(), now() + interval '30 minutes')
RETURNING id AS w_lan \gset
-- Van (zone C) lends TH2 B1-010 for a month, open to the whole chain (AC-20).
INSERT INTO app.share_window (zone_id, slot_id, owner_user_id, period, bookable_period, open_scope, idempotency_key, owner_otp_confirmed_at, expires_at)
VALUES (:'zone_c', :'s_c010', :'u_van',
        tstzrange((:'d1' || ' 06:30+07')::timestamptz, (:'d1' || ' 06:30+07')::timestamptz + interval '30 days'),
        tstzrange((:'d1' || ' 06:45+07')::timestamptz, (:'d1' || ' 06:00+07')::timestamptz + interval '30 days'),
        'chain', 'thread-van:w2.publish', now(), now() + interval '30 minutes')
RETURNING id AS w_van \gset

INSERT INTO app.parking_request (zone_id, building_id, requester_user_id, vehicle_id, requested_period,
                                 computed_level, outcome, idempotency_key)
VALUES (:'zone_a', :'bld_a1', :'u_binh', :'v_binh',
        tstzrange((:'d1' || ' 08:00+07')::timestamptz, (:'d1' || ' 12:00+07')::timestamptz), 'L1', 'matched', 'req-binh-1')
RETURNING id AS req_binh \gset
-- AC-22: the expired tenant's request is recorded as blocked (KPI) — no booking is created.
INSERT INTO app.parking_request (zone_id, building_id, requester_user_id, vehicle_id, requested_period,
                                 computed_level, outcome, block_reason, idempotency_key)
VALUES (:'zone_a', :'bld_a1', :'u_tuan', :'v_tuan',
        tstzrange((:'d1' || ' 13:00+07')::timestamptz, (:'d1' || ' 15:00+07')::timestamptz), 'L4', 'blocked', 'BR-16', 'req-tuan-1');
-- A matched request in zone C: the KPI view (section 17) aggregates parking_request per zone and day.
INSERT INTO app.parking_request (zone_id, building_id, requester_user_id, vehicle_id, requested_period,
                                 computed_level, outcome, idempotency_key)
VALUES (:'zone_c', :'bld_c1', :'u_hoa', :'v_hoa',
        tstzrange((:'d1' || ' 07:00+07')::timestamptz, (:'d1' || ' 19:00+07')::timestamptz), 'L3', 'matched', 'req-hoa-1');

INSERT INTO app.booking (zone_id, slot_id, request_id, share_window_id, provider_user_id, renter_user_id, vehicle_id,
                         period, eligibility_level, price_vnd, status, idempotency_key)
VALUES (:'zone_a', :'s_045', :'req_binh', :'w_lan', :'u_lan', :'u_binh', :'v_binh',
        tstzrange((:'d1' || ' 08:00+07')::timestamptz, (:'d1' || ' 12:00+07')::timestamptz), 'L1', 40000,   -- 4 h × 10 000
        'pending_agreement', 'thread-binh:w1.hold')
RETURNING id AS bk_binh \gset
INSERT INTO app.booking (zone_id, slot_id, share_window_id, provider_user_id, renter_user_id, vehicle_id,
                         period, eligibility_level, price_vnd, status, idempotency_key)
VALUES (:'zone_c', :'s_c010', :'w_van', :'u_van', :'u_hoa', :'v_hoa',
        tstzrange((:'d1' || ' 07:00+07')::timestamptz, (:'d1' || ' 07:00+07')::timestamptz + interval '21 days'), 'L3',
        1470000, 'pending_agreement', 'thread-hoa:w1.hold')                               -- 21 days × 70 000 (L3)
RETURNING id AS bk_hoa \gset
INSERT INTO app.booking (zone_id, slot_id, renter_user_id, vehicle_id, period, eligibility_level, price_vnd, status, idempotency_key)
VALUES (:'zone_a', :'s_th3_a', :'u_khach', :'v_khach',
        tstzrange((:'d1' || ' 10:00+07')::timestamptz, (:'d1' || ' 12:00+07')::timestamptz), 'L4', 60000,   -- 2 h × 30 000
        'confirmed', 'thread-khach:w1.th3')
RETURNING id AS bk_khach \gset

-- v3: no template_id; the text comes from the pinned zone_policy_id (zone_policy.agreement_template_md).
INSERT INTO app.agreement (zone_id, booking_id, zone_policy_id, provider_user_id, renter_user_id, price_vnd,
                           body_rendered, body_sha256, status, requires_approval, confirm_deadline,
                           provider_confirmed_at, renter_confirmed_at, effective_at)
VALUES (:'zone_a', :'bk_binh', :'pol_a', :'u_lan', :'u_binh', 40000, 'Thỏa thuận GD-1 …',
        sha256(convert_to('Thỏa thuận GD-1 …', 'UTF8')), 'effective', false, now() + interval '30 min', now(), now(), now())
RETURNING id AS ag_binh \gset
UPDATE app.booking SET status = 'confirmed' WHERE id = :'bk_binh';
-- FR-09 / AC-07: evidence of both confirmations (the OTP itself lives in Redis, ADR-0006): ids, hash and amount only.
INSERT INTO app.consent_record (user_id, zone_id, action, subject_type, subject_id, terms_version, decision, evidence)
SELECT u, :'zone_a', 'agreement_confirm', 'agreement', a.id, 'policy-v1', 'accepted',
       jsonb_build_object('body_sha256', encode(a.body_sha256, 'hex'), 'price_vnd', a.price_vnd, 'policy_version', 1)
FROM app.agreement a, LATERAL (VALUES (a.provider_user_id), (a.renter_user_id)) AS p(u) WHERE a.id = :'ag_binh';

-- Hoa's 21-day L3 rental (1 470 000 đ) is above the default threshold of 1 000 000 đ → HITL (AC-15, D-08).
-- v4: every approval_request points at its agent_thread (FK).
INSERT INTO app.agent_thread (thread_id, user_id, zone_id, workflow, status, pending_card)
VALUES ('thread-hoa', :'u_hoa', :'zone_c', 'W2', 'awaiting_manager', jsonb_build_object('card', 'agreement_over_threshold', 'price_vnd', 1470000));
INSERT INTO app.approval_request (zone_id, kind, subject_id, thread_id, summary)
VALUES (:'zone_c', 'agreement_over_threshold', app.uuid_v7(), 'thread-hoa', 'GD vượt ngưỡng') RETURNING id AS appr_hoa, subject_id AS appr_hoa_subject \gset
INSERT INTO app.agreement (id, zone_id, booking_id, zone_policy_id, provider_user_id, renter_user_id, price_vnd,
                           body_rendered, body_sha256, status, requires_approval, approval_request_id, confirm_deadline,
                           provider_confirmed_at, renter_confirmed_at)
VALUES (:'appr_hoa_subject', :'zone_c', :'bk_hoa', :'pol_c', :'u_van', :'u_hoa', 1470000, 'Thỏa thuận GD-2 …',
        sha256(convert_to('Thỏa thuận GD-2 …', 'UTF8')), 'pending_approval', true, :'appr_hoa', now() + interval '30 min', now(), now());

-- v3: no vouchers; the TH3 visit is paid in full.
-- v6: payment is a fee ledger; entries are 'recorded' (default), the parties settle outside the app (A-05).
INSERT INTO app.payment (zone_id, booking_id, payer_user_id, kind, amount_vnd, idempotency_key)
VALUES (:'zone_a', :'bk_khach', :'u_khach', 'th3_visit', 60000, 'pay-khach-1');
INSERT INTO app.payment (zone_id, booking_id, payer_user_id, kind, amount_vnd, idempotency_key)
VALUES (:'zone_a', :'bk_binh', :'u_binh', 'share_booking', 40000, 'pay-binh-1');

\echo '== 4. Seed: LPR, notifications'
INSERT INTO app.lpr_event (zone_id, source_code, source_event_id, gate_code, direction, occurred_at,
                           plate_ciphertext, plate_hash, plate_masked, ocr_confidence, status, matched_vehicle_id)
VALUES (:'zone_a', 'demo-weekday', 'EV-88419', 'G1', 'in', now() - interval '1 hour',
        pgp_sym_encrypt('30A22222', :'demo_key'), hmac('30A22222', :'pepper', 'sha256'), '30A-•••.22', 0.960, 'accepted', :'v_binh')
RETURNING id AS ev1, occurred_at AS ev1_at \gset
INSERT INTO app.lpr_event (zone_id, source_code, source_event_id, gate_code, direction, occurred_at,
                           plate_ciphertext, plate_hash, plate_masked, ocr_confidence, status)
VALUES (:'zone_a', 'demo-weekday', 'EV-88421', 'G1', 'in', now() - interval '50 min',
        pgp_sym_encrypt('30A12845', :'demo_key'), hmac('30A12845', :'pepper', 'sha256'), '30A-•••.45', 0.540, 'pending_review');

INSERT INTO app.notification (user_id, zone_id, kind, title, body, link, idempotency_key)
VALUES (:'u_binh', :'zone_a', 'agreement_pending', 'Có thỏa thuận chờ bạn xác nhận', 'Chỗ B2-045',
        jsonb_build_object('type', 'agreement', 'id', :'ag_binh'), 'thread-binh:w2.notify');
-- AI decision log (append-only): one deterministic step and one step escalated to the BQL; hashes only.
INSERT INTO app.ai_decision_log (thread_id, zone_id, user_hash, workflow, step, model_version, input_hash, output_hash,
                                 risk_level, outcome, human_approved, approval_request_id, trace_id, latency_ms, idempotency_key)
VALUES ('thread-hoa', :'zone_c', hmac(:'u_hoa', :'pepper', 'sha256'), 'W2', 'rule_engine.price_check', NULL,
        sha256('in-1'), sha256('out-1'), 'low', 'auto_applied', NULL, NULL, '4bf92f3577b34da6a3ce929d0e0e4736', 12, 'thread-hoa:c1:price_check'),
       ('thread-hoa', :'zone_c', hmac(:'u_hoa', :'pepper', 'sha256'), 'W2', 'hitl.escalate', 'claude-sonnet', sha256('in-2'), sha256('out-2'),
        'high', 'sent_to_human', NULL, :'appr_hoa', '4bf92f3577b34da6a3ce929d0e0e4736', 840, 'thread-hoa:c1:hitl_escalate');
-- KPI: no table to seed — app.kpi_daily_v aggregates the parking_request rows of section 3.

-- =====================================================================================================
\echo '== 5. Positive checks (business rules derived by the database)'
SELECT pg_temp.expect('AC-19 minh is L2 at tower A1 (low-rise shophouse in A)', (SELECT level FROM app.eligibility_level_at(:'u_minh', :'bld_a1')) = 'L2');
SELECT pg_temp.expect('AC-19 minh is L1 at his own tower B1', (SELECT level FROM app.eligibility_level_at(:'u_minh', :'bld_b1')) = 'L1');
SELECT pg_temp.expect('AC-21 minh is only L3 in zone C (BR-15)', (SELECT level FROM app.eligibility_level_at(:'u_minh', :'bld_c1')) = 'L3');
SELECT pg_temp.expect('AC-22 expired tenant tuan falls to L4 (BR-16)', (SELECT level FROM app.eligibility_level_at(:'u_tuan', :'bld_a1')) = 'L4');
SELECT pg_temp.expect('L4 guest has no expiry', (SELECT valid_until IS NULL FROM app.eligibility_level_at(:'u_khach', :'bld_a1')));
WITH ins AS (
  INSERT INTO app.lpr_event (zone_id, source_code, source_event_id, gate_code, direction, occurred_at, ocr_confidence, status)
  VALUES (:'zone_a', 'demo-weekday', 'EV-88419', 'G1', 'in', now(), 0.960, 'accepted')
  ON CONFLICT (zone_id, source_code, source_event_id) DO NOTHING RETURNING 1)
SELECT pg_temp.expect('LPR duplicate is ignored with ON CONFLICT DO NOTHING (AC-10a)', count(*) = 0) FROM ins;
SELECT pg_temp.expect('v4 staff_zone_id replaces staff_zone: BQL A / guard A -> zone A, BQL C -> zone C',
  (SELECT staff_zone_id FROM app.app_user WHERE id = :'u_bql_a') = :'zone_a'
  AND (SELECT staff_zone_id FROM app.app_user WHERE id = :'u_guard_a') = :'zone_a'
  AND (SELECT staff_zone_id FROM app.app_user WHERE id = :'u_bql_c') = :'zone_c'
  AND (SELECT count(*) FROM app.app_user WHERE staff_zone_id IS NOT NULL) = 3);
SELECT pg_temp.expect('consent_record: registration terms for every account + both agreement confirmations with body_sha256',
  (SELECT count(*) FROM app.consent_record WHERE action = 'registration_terms') = (SELECT count(*) FROM app.app_user)
  AND (SELECT count(*) FROM app.consent_record WHERE action = 'agreement_confirm' AND subject_id = :'ag_binh'
         AND evidence ->> 'body_sha256' = (SELECT encode(body_sha256, 'hex') FROM app.agreement WHERE id = :'ag_binh')) = 2);
SELECT pg_temp.expect('every approval_request has its agent_thread',
  NOT EXISTS (SELECT 1 FROM app.approval_request r WHERE NOT EXISTS (SELECT 1 FROM app.agent_thread t WHERE t.thread_id = r.thread_id)));
SELECT pg_temp.expect('size_class is an ordered enum, BR-11 compares with <=', 'M'::app.size_class <= 'L' AND NOT 'XL'::app.size_class <= 'L');

-- =====================================================================================================
\echo '== 6. Negative tests: the database must reject each statement'
-- Booking / sharing invariants
SELECT pg_temp.expect_fail('double booking of the same slot and time (EXCLUDE)', format(
  $$INSERT INTO app.booking (zone_id, slot_id, share_window_id, provider_user_id, renter_user_id, vehicle_id, period,
      eligibility_level, price_vnd, status, idempotency_key)
    VALUES (%L, %L, %L, %L, %L, %L, tstzrange(%L::timestamptz, %L::timestamptz), 'L1', 50000, 'pending_agreement', 'x1')$$,
  :'zone_a', :'s_045', :'w_lan', :'u_lan', :'u_binh', :'v_binh', :'d1' || ' 11:00+07', :'d1' || ' 13:00+07'), '23P01');
SELECT pg_temp.expect_fail('double booking via a temporary hold (EXCLUDE)', format(
  $$INSERT INTO app.booking (zone_id, slot_id, share_window_id, provider_user_id, renter_user_id, vehicle_id, period,
      eligibility_level, price_vnd, status, hold_expires_at, idempotency_key)
    VALUES (%L, %L, %L, %L, %L, %L, tstzrange(%L::timestamptz, %L::timestamptz), 'L1', 50000, 'held', now() + interval '10 min', 'x1b')$$,
  :'zone_a', :'s_045', :'w_lan', :'u_lan', :'u_binh', :'v_binh', :'d1' || ' 11:00+07', :'d1' || ' 13:00+07'), '23P01');
SELECT pg_temp.expect_fail('BR-01 L2 shophouse owner books TH1 open only to tower', format(
  $$INSERT INTO app.booking (zone_id, slot_id, share_window_id, provider_user_id, renter_user_id, vehicle_id, period,
      eligibility_level, price_vnd, status, hold_expires_at, idempotency_key)
    VALUES (%L, %L, %L, %L, %L, %L, tstzrange(%L::timestamptz, %L::timestamptz), 'L2', 50000, 'held', now() + interval '10 min', 'x2')$$,
  :'zone_a', :'s_045', :'w_lan', :'u_lan', :'u_minh', :'v_minh', :'d1' || ' 14:00+07', :'d1' || ' 16:00+07'), '23514', 'BR-01');
SELECT pg_temp.expect_fail('BR-16 expired tenant claims L1', format(
  $$INSERT INTO app.booking (zone_id, slot_id, share_window_id, provider_user_id, renter_user_id, vehicle_id, period,
      eligibility_level, price_vnd, status, hold_expires_at, idempotency_key)
    VALUES (%L, %L, %L, %L, %L, %L, tstzrange(%L::timestamptz, %L::timestamptz), 'L1', 50000, 'held', now() + interval '10 min', 'x3')$$,
  :'zone_a', :'s_045', :'w_lan', :'u_lan', :'u_tuan', :'v_tuan', :'d1' || ' 14:00+07', :'d1' || ' 16:00+07'), '23514', 'derived L4');
SELECT pg_temp.expect_fail('BR-11 XL pickup into an M slot', format(
  $$INSERT INTO app.booking (zone_id, slot_id, share_window_id, provider_user_id, renter_user_id, vehicle_id, period,
      eligibility_level, price_vnd, status, hold_expires_at, idempotency_key)
    VALUES (%L, %L, %L, %L, %L, %L, tstzrange(%L::timestamptz, %L::timestamptz), 'L1', 50000, 'held', now() + interval '10 min', 'x4')$$,
  :'zone_a', :'s_045', :'w_lan', :'u_lan', :'u_binh', :'v_binh_xl', :'d1' || ' 14:00+07', :'d1' || ' 16:00+07'), '23514', 'BR-11');
SELECT pg_temp.expect_fail('FR-06 booking eats into the owner buffer', format(
  $$INSERT INTO app.booking (zone_id, slot_id, share_window_id, provider_user_id, renter_user_id, vehicle_id, period,
      eligibility_level, price_vnd, status, hold_expires_at, idempotency_key)
    VALUES (%L, %L, %L, %L, %L, %L, tstzrange(%L::timestamptz, %L::timestamptz), 'L1', 50000, 'held', now() + interval '10 min', 'x5')$$,
  :'zone_a', :'s_045', :'w_lan', :'u_lan', :'u_binh', :'v_binh', :'d1' || ' 16:00+07', :'d1' || ' 17:40+07'), '23514', 'FR-06');
SELECT pg_temp.expect_fail('booking with provider but no share window', format(
  $$INSERT INTO app.booking (zone_id, slot_id, provider_user_id, renter_user_id, vehicle_id, period,
      eligibility_level, price_vnd, status, idempotency_key)
    VALUES (%L, %L, %L, %L, %L, tstzrange(now(), now() + interval '1 hour'), 'L1', 1, 'confirmed', 'x6')$$,
  :'zone_a', :'s_045', :'u_lan', :'u_binh', :'v_binh'), '23514', 'require a share window');
SELECT pg_temp.expect_fail('booking a zone-A slot under zone C (composite FK)', format(
  $$INSERT INTO app.booking (zone_id, slot_id, renter_user_id, vehicle_id, period, eligibility_level, price_vnd, status, idempotency_key)
    VALUES (%L, %L, %L, %L, tstzrange(now(), now() + interval '1 hour'), 'L4', 1, 'confirmed', 'x7')$$,
  :'zone_c', :'s_th3_a', :'u_khach', :'v_khach'), '23503');
SELECT pg_temp.expect_fail('renter uses someone else''s vehicle', format(
  $$INSERT INTO app.booking (zone_id, slot_id, renter_user_id, vehicle_id, period, eligibility_level, price_vnd, status, idempotency_key)
    VALUES (%L, %L, %L, %L, tstzrange(now() + interval '2 days', now() + interval '2 days 1 hour'), 'L4', 1, 'confirmed', 'x8')$$,
  :'zone_a', :'s_th3_a', :'u_khach', :'v_binh'), '23503');
SELECT pg_temp.expect_fail('empty / inverted booking period', format(
  $$INSERT INTO app.booking (zone_id, slot_id, renter_user_id, vehicle_id, period, eligibility_level, price_vnd, status, idempotency_key)
    VALUES (%L, %L, %L, %L, tstzrange(now(), now()), 'L4', 1, 'confirmed', 'x9')$$,
  :'zone_a', :'s_th3_a', :'u_khach', :'v_khach'), '23514');
SELECT pg_temp.expect_fail('negative price', format(
  $$INSERT INTO app.booking (zone_id, slot_id, renter_user_id, vehicle_id, period, eligibility_level, price_vnd, status, idempotency_key)
    VALUES (%L, %L, %L, %L, tstzrange(now() + interval '3 days', now() + interval '3 days 1 hour'), 'L4', -1, 'confirmed', 'x10')$$,
  :'zone_a', :'s_th3_a', :'u_khach', :'v_khach'), '23514');
SELECT pg_temp.expect_fail('replayed booking idempotency key', format(
  $$INSERT INTO app.booking (zone_id, slot_id, renter_user_id, vehicle_id, period, eligibility_level, price_vnd, status, idempotency_key)
    VALUES (%L, %L, %L, %L, tstzrange(now() + interval '4 days', now() + interval '4 days 1 hour'), 'L4', 1, 'confirmed', 'thread-khach:w1.th3')$$,
  :'zone_a', :'s_th3_a', :'u_khach', :'v_khach'), '23505');
SELECT pg_temp.expect_fail('BR-03 individual shares a TH3 slot', format(
  $$INSERT INTO app.share_window (zone_id, slot_id, owner_user_id, period, bookable_period, open_scope, idempotency_key, owner_otp_confirmed_at, expires_at)
    VALUES (%L, %L, %L, tstzrange(now() + interval '5 days', now() + interval '5 days 2 hours'),
            tstzrange(now() + interval '5 days', now() + interval '5 days 2 hours'), 'zone', gen_random_uuid()::text, now(), now() + interval '30 minutes')$$,
  :'zone_a', :'s_th3_a', :'u_lan'), '23514', 'BR-03');
SELECT pg_temp.expect_fail('AC-23 owner widens TH1 scope beyond tower rule', format(
  $$INSERT INTO app.share_window (zone_id, slot_id, owner_user_id, period, bookable_period, open_scope, idempotency_key, owner_otp_confirmed_at, expires_at)
    VALUES (%L, %L, %L, tstzrange(now() + interval '5 days', now() + interval '5 days 2 hours'),
            tstzrange(now() + interval '5 days', now() + interval '5 days 2 hours'), 'zone', gen_random_uuid()::text, now(), now() + interval '30 minutes')$$,
  :'zone_a', :'s_045', :'u_lan'), '23514', 'AC-23');
SELECT pg_temp.expect_fail('non-holder shares a slot', format(
  $$INSERT INTO app.share_window (zone_id, slot_id, owner_user_id, period, bookable_period, open_scope, idempotency_key, owner_otp_confirmed_at, expires_at)
    VALUES (%L, %L, %L, tstzrange(now() + interval '5 days', now() + interval '5 days 2 hours'),
            tstzrange(now() + interval '5 days', now() + interval '5 days 2 hours'), 'building', gen_random_uuid()::text, now(), now() + interval '30 minutes')$$,
  :'zone_a', :'s_045', :'u_binh'), '23514', 'does not hold');
SELECT pg_temp.expect_fail('overlapping open share windows on one slot', format(
  $$INSERT INTO app.share_window (zone_id, slot_id, owner_user_id, period, bookable_period, open_scope, idempotency_key, owner_otp_confirmed_at, expires_at)
    VALUES (%L, %L, %L, tstzrange(%L::timestamptz, %L::timestamptz), tstzrange(%L::timestamptz, %L::timestamptz), 'building', 'x-ov', now(), now() + interval '30 minutes')$$,
  :'zone_a', :'s_045', :'u_lan', :'d1' || ' 12:00+07', :'d1' || ' 20:00+07', :'d1' || ' 12:00+07', :'d1' || ' 20:00+07'), '23P01');
SELECT pg_temp.expect_fail('bookable period wider than the window', format(
  $$INSERT INTO app.share_window (zone_id, slot_id, owner_user_id, period, bookable_period, open_scope, idempotency_key, owner_otp_confirmed_at, expires_at)
    VALUES (%L, %L, %L, tstzrange(now() + interval '6 days', now() + interval '6 days 2 hours'),
            tstzrange(now() + interval '6 days', now() + interval '6 days 3 hours'), 'building', 'x-wide', now(), now() + interval '30 minutes')$$,
  :'zone_a', :'s_046', :'u_binh'), '23514');


-- Facility (v3: merged columns and the single-operator zone code)
SELECT pg_temp.expect_fail('duplicate zone code (globally unique, no chain)', $$INSERT INTO app.zone (code, name) VALUES ('A', 'Khu A bis')$$, '23505');
SELECT pg_temp.expect_fail('slot level_code must be upper-case', format(
  $$INSERT INTO app.slot (zone_id, building_id, pool_id, slot_type, level_code, code, size_class)
    VALUES (%L, %L, %L, 'TH1', 'b2', 'B2-900', 'M')$$, :'zone_a', :'bld_a1', :'pool_a1_th1'), '23514', 'level_code');
SELECT pg_temp.expect_fail('building subzone_code with a space', format(
  $$INSERT INTO app.building (zone_id, subzone_code, code, name, kind) VALUES (%L, 'A S1', 'A9', 'Tòa A9', 'residential_tower')$$, :'zone_a'), '23514', 'subzone_code');
SELECT pg_temp.expect_fail('slot size outside the size_class enum', format(
  $$INSERT INTO app.slot (zone_id, building_id, pool_id, slot_type, level_code, code, size_class)
    VALUES (%L, %L, %L, 'TH1', 'B2', 'B2-901', 'XXL')$$, :'zone_a', :'bld_a1', :'pool_a1_th1'), '22P02');

-- Pools, holdings, eligibility
SELECT pg_temp.expect_fail('BR-02 TH2 pool without developer consent', format(
  $$INSERT INTO app.slot_pool (zone_id, building_id, slot_type, max_open_scope) VALUES (%L, %L, 'TH2', 'zone')$$, :'zone_b', :'bld_b1'), '23514', 'slot_pool_scope_by_type');
SELECT pg_temp.expect_fail('PRD §4 TH1 pool opened to the whole chain', format(
  $$INSERT INTO app.slot_pool (zone_id, building_id, slot_type, max_open_scope) VALUES (%L, %L, 'TH1', 'chain')$$, :'zone_c', :'bld_c1'), '23514', 'slot_pool_scope_by_type');
SELECT pg_temp.expect_fail('TH3 slot given a private holder', format(
  $$INSERT INTO app.slot_holding (zone_id, slot_id, slot_type, user_id, kind, held_during)
    VALUES (%L, %L, 'TH3', %L, 'owner', tstzrange(now(), NULL))$$, :'zone_a', :'s_th3_a', :'u_lan'), '23514', 'slot_holding_type_kind');
SELECT pg_temp.expect_fail('two concurrent holders of one slot', format(
  $$INSERT INTO app.slot_holding (zone_id, slot_id, slot_type, user_id, kind, held_during)
    VALUES (%L, %L, 'TH1', %L, 'owner', tstzrange(now(), NULL))$$, :'zone_a', :'s_045', :'u_binh'), '23P01');
SELECT pg_temp.expect_fail('duplicate overlapping eligibility', format(
  $$INSERT INTO app.eligibility (user_id, asset_id, zone_id, role, valid_during) VALUES (%L, %L, %L, 'owner', tstzrange(now(), NULL))$$,
  :'u_lan', :'a_lan', :'zone_a'), '23P01');
SELECT pg_temp.expect_fail('eligibility zone differs from asset zone', format(
  $$INSERT INTO app.eligibility (user_id, asset_id, zone_id, role, valid_during) VALUES (%L, %L, %L, 'tenant', tstzrange(now(), NULL))$$,
  :'u_khach', :'a_lan', :'zone_c'), '23503');
SELECT pg_temp.expect_fail('verified eligibility without verifier', format(
  $$INSERT INTO app.eligibility (user_id, asset_id, zone_id, role, valid_during, status) VALUES (%L, %L, %L, 'tenant', tstzrange(now(), NULL), 'verified')$$,
  :'u_khach', :'a_lan', :'zone_a'), '23514');

-- Agreement, approvals
SELECT pg_temp.expect_fail('AC-07 agreement effective with one confirmation', format(
  $$UPDATE app.agreement SET status = 'effective', effective_at = now(), renter_confirmed_at = NULL WHERE id = %L$$, :'ag_binh'), '23514');
SELECT pg_temp.expect_fail('AC-15 over-threshold agreement effective without approval', format(
  $$UPDATE app.agreement SET status = 'effective', effective_at = now(), approval_request_id = NULL WHERE booking_id = %L$$, :'bk_hoa'), '23514');
SELECT pg_temp.expect_fail('second pending approval for the same subject', format(
  $$INSERT INTO app.approval_request (zone_id, kind, subject_id, thread_id) VALUES (%L, 'agreement_over_threshold', %L, 'thread-hoa')$$,
  :'zone_c', :'appr_hoa_subject'), '23505');
SELECT pg_temp.expect_fail('approval_request for a thread that does not exist (FK)', format(
  $$INSERT INTO app.approval_request (zone_id, kind, subject_id, thread_id) VALUES (%L, 'agreement_over_threshold', app.uuid_v7(), 'no-such-thread')$$,
  :'zone_c'), '23503');
SELECT pg_temp.expect_fail('approval marked approved without approver', format(
  $$UPDATE app.approval_request SET status = 'approved' WHERE id = %L$$, :'appr_hoa'), '23514');

-- Money, payments
SELECT pg_temp.expect_fail('negative payment amount', format(
  $$INSERT INTO app.payment (zone_id, booking_id, payer_user_id, kind, amount_vnd, idempotency_key)
    VALUES (%L, %L, %L, 'th3_visit', -1, 'p3')$$, :'zone_a', :'bk_khach', :'u_khach'), '23514');
SELECT pg_temp.expect_fail('A-05 v6 no QR status (payment is a ledger)', format(
  $$INSERT INTO app.payment (zone_id, booking_id, payer_user_id, kind, amount_vnd, status, idempotency_key)
    VALUES (%L, %L, %L, 'share_booking', 50000, 'paid_simulated', 'p8')$$, :'zone_a', :'bk_binh', :'u_binh'), '22P02');
SELECT pg_temp.expect_fail('second recorded entry of one kind for one booking', format(
  $$INSERT INTO app.payment (zone_id, booking_id, payer_user_id, kind, amount_vnd, idempotency_key)
    VALUES (%L, %L, %L, 'th3_visit', 50000, 'p7')$$, :'zone_a', :'bk_khach', :'u_khach'), '23505', 'payment_recorded_uq');

-- LPR, identity
SELECT pg_temp.expect_fail('LPR duplicate event id in the same zone and source (plain INSERT)', format(
  $$INSERT INTO app.lpr_event (zone_id, source_code, source_event_id, gate_code, direction, occurred_at, ocr_confidence, status)
    VALUES (%L, 'demo-weekday', 'EV-88419', 'G1', 'in', now(), 0.9, 'accepted')$$, :'zone_a'), '23505');
SELECT pg_temp.expect_fail('OCR confidence above 1', format(
  $$INSERT INTO app.lpr_event (zone_id, source_code, source_event_id, gate_code, direction, occurred_at, ocr_confidence, status)
    VALUES (%L, 'demo-weekday', 'EV-1', 'G1', 'in', now(), 1.5, 'accepted')$$, :'zone_a'), '23514');
SELECT pg_temp.expect_fail('manual OCR confirmation without reviewer', format(
  $$INSERT INTO app.lpr_event (zone_id, source_code, source_event_id, gate_code, direction, occurred_at, ocr_confidence, status)
    VALUES (%L, 'demo-weekday', 'EV-2', 'G1', 'in', now(), 0.5, 'confirmed_manual')$$, :'zone_a'), '23514');
SELECT pg_temp.expect_fail('LPR gate code in lower case', format(
  $$INSERT INTO app.lpr_event (zone_id, source_code, source_event_id, gate_code, direction, occurred_at, ocr_confidence, status)
    VALUES (%L, 'demo-weekday', 'EV-3', 'g1', 'in', now(), 0.9, 'accepted')$$, :'zone_a'), '23514', 'gate_code');
SELECT pg_temp.expect_fail('ON DELETE RESTRICT: deleting a user with history', format(
  $$DELETE FROM app.app_user WHERE id = %L$$, :'u_binh'), '23503');
SELECT pg_temp.expect_fail('ON DELETE RESTRICT: deleting a zone', format($$DELETE FROM app.zone WHERE id = %L$$, :'zone_a'), '23503');
SELECT pg_temp.expect_fail('raw (non-argon2id) password', $$INSERT INTO app.app_user (full_name, phone_e164, password_hash) VALUES ('X', '+84909999999', 'secret123')$$, '23514');
SELECT pg_temp.expect_fail('duplicate live phone number', $$INSERT INTO app.app_user (full_name, phone_e164, password_hash) VALUES ('X', '+84901000001', '$argon2id$x')$$, '23505');
SELECT pg_temp.expect_fail('malformed phone number', $$INSERT INTO app.app_user (full_name, phone_e164, password_hash) VALUES ('X', '0901', '$argon2id$x')$$, '23514');
SELECT pg_temp.expect_fail('blank name', $$INSERT INTO app.app_user (full_name, phone_e164, password_hash) VALUES ('   ', '+84909999998', '$argon2id$x')$$, '23514');
SELECT pg_temp.expect_fail('request longer than 31 days', format(
  $$INSERT INTO app.parking_request (zone_id, building_id, requester_user_id, vehicle_id, requested_period, computed_level, outcome, idempotency_key)
    VALUES (%L, %L, %L, %L, tstzrange(now(), now() + interval '40 days'), 'L1', 'no_match', 'r9')$$,
  :'zone_a', :'bld_a1', :'u_binh', :'v_binh'), '23514');
SELECT pg_temp.expect_fail('blocked request without the rule id', format(
  $$INSERT INTO app.parking_request (zone_id, building_id, requester_user_id, vehicle_id, requested_period, computed_level, outcome, idempotency_key)
    VALUES (%L, %L, %L, %L, tstzrange(now(), now() + interval '1 hour'), 'L4', 'blocked', 'r10')$$,
  :'zone_a', :'bld_a1', :'u_tuan', :'v_tuan'), '23514');

-- v3 merged columns: policy prices / template, BR-11 enum
SELECT pg_temp.expect_fail('zone_policy.prices must be a JSON object', format(
  $$INSERT INTO app.zone_policy (zone_id, version, effective_from, prices, agreement_template_md) VALUES (%L, 9, now(), '[]'::jsonb, 'x')$$, :'zone_b'), '23514', 'prices');
SELECT pg_temp.expect_fail('zone_policy.prices is required', format(
  $$INSERT INTO app.zone_policy (zone_id, version, effective_from, agreement_template_md) VALUES (%L, 9, now(), 'x')$$, :'zone_b'), '23502');
SELECT pg_temp.expect_fail('zone_policy agreement template must not be blank', format(
  $$INSERT INTO app.zone_policy (zone_id, version, effective_from, prices, agreement_template_md) VALUES (%L, 9, now(), '{}'::jsonb, '   ')$$, :'zone_b'), '23514', 'agreement_template_md');
SELECT pg_temp.expect_fail('size outside the enum on a vehicle', format(
  $$INSERT INTO app.vehicle (user_id, plate_masked, size_class) VALUES (%L, 'x', 'XXL')$$, :'u_binh'), '22P02');
\echo '== 7. v4 tables: staff zone, slot status, occupancy, agent_thread, recovery_case, consent_record, ai_decision_log'
-- app_user.staff_zone_id
SELECT pg_temp.expect_fail('staff_zone_id set on a resident (CHECK)', format(
  $$UPDATE app.app_user SET staff_zone_id = %L WHERE id = %L$$, :'zone_a', :'u_lan'), '23514', 'app_user_staff_zone_role');
SELECT pg_temp.expect_fail('staff_zone_id set on a chain operator (CHECK)', format(
  $$UPDATE app.app_user SET staff_zone_id = %L WHERE id = %L$$, :'zone_a', :'u_op'), '23514', 'app_user_staff_zone_role');
SELECT pg_temp.expect_fail('staff_zone_id of an unknown zone (FK)', format(
  $$UPDATE app.app_user SET staff_zone_id = gen_random_uuid() WHERE id = %L$$, :'u_bql_a'), '23503');
SELECT pg_temp.expect('a BQL / guard may carry a staff zone, a resident does not',
  (SELECT count(*) FROM app.app_user WHERE staff_zone_id IS NOT NULL AND role NOT IN ('guard', 'zone_manager')) = 0);

-- slot.operational_status
INSERT INTO app.slot (zone_id, building_id, pool_id, slot_type, level_code, code, size_class, operational_status)
VALUES (:'zone_a', :'bld_apl', :'pool_a_th3', 'TH3', 'G', 'TH3-099', 'L', 'maintenance') RETURNING id AS s_maint \gset
SELECT pg_temp.expect_fail('booking on a maintenance slot', format(
  $$INSERT INTO app.booking (zone_id, slot_id, renter_user_id, vehicle_id, period, eligibility_level, price_vnd, status, idempotency_key)
    VALUES (%L, %L, %L, %L, tstzrange(now() + interval '20 days', now() + interval '20 days 1 hour'), 'L4', 1, 'confirmed', 'maint-1')$$,
  :'zone_a', :'s_maint', :'u_khach', :'v_khach'), '23514', 'not bookable');
UPDATE app.slot SET operational_status = 'blocked' WHERE id = :'s_maint';
SELECT pg_temp.expect_fail('booking on a blocked slot', format(
  $$INSERT INTO app.booking (zone_id, slot_id, renter_user_id, vehicle_id, period, eligibility_level, price_vnd, status, idempotency_key)
    VALUES (%L, %L, %L, %L, tstzrange(now() + interval '20 days', now() + interval '20 days 1 hour'), 'L4', 1, 'confirmed', 'maint-2')$$,
  :'zone_a', :'s_maint', :'u_khach', :'v_khach'), '23514', 'not bookable');
SELECT pg_temp.expect_fail('slot status outside the enum', format(
  $$UPDATE app.slot SET operational_status = 'retired' WHERE id = %L$$, :'s_maint'), '22P02');
UPDATE app.slot SET operational_status = 'active' WHERE id = :'s_maint';
WITH b AS (INSERT INTO app.booking (zone_id, slot_id, renter_user_id, vehicle_id, period, eligibility_level, price_vnd, status, idempotency_key)
             VALUES (:'zone_a', :'s_maint', :'u_khach', :'v_khach', tstzrange(now() + interval '20 days', now() + interval '20 days 1 hour'),
                     'L4', 30000, 'confirmed', 'maint-3') RETURNING 1)
SELECT pg_temp.expect('the same slot is bookable again once it is active', count(*) = 1) FROM b;

-- booking.checked_in_at / checked_out_at
SELECT pg_temp.expect_fail('checked_out_at before checked_in_at', format(
  $$UPDATE app.booking SET checked_in_at = now(), checked_out_at = now() - interval '1 hour' WHERE id = %L$$, :'bk_khach'), '23514', 'booking_check_times');
SELECT pg_temp.expect_fail('checked_out_at without checked_in_at', format(
  $$UPDATE app.booking SET checked_out_at = now() WHERE id = %L$$, :'bk_khach'), '23514', 'booking_check_times');
UPDATE app.booking SET checked_in_at = now() - interval '2 hours', checked_out_at = now() - interval '1 hour' WHERE id = :'bk_khach';
SELECT pg_temp.expect('N1 occupancy: check-in then check-out is accepted',
  (SELECT checked_in_at < checked_out_at FROM app.booking WHERE id = :'bk_khach'));

-- agent_thread
SELECT pg_temp.expect_fail('agent_thread with an unknown workflow code', format(
  $$INSERT INTO app.agent_thread (thread_id, user_id, workflow) VALUES ('t-bad', %L, 'W9')$$, :'u_lan'), '22P02');
SELECT pg_temp.expect_fail('agent_thread pending_card must be a JSON object', format(
  $$INSERT INTO app.agent_thread (thread_id, user_id, workflow, pending_card) VALUES ('t-bad', %L, 'W1', '[]'::jsonb)$$, :'u_lan'), '23514');
SELECT pg_temp.expect_fail('duplicate agent_thread id', format(
  $$INSERT INTO app.agent_thread (thread_id, user_id, workflow) VALUES ('thread-hoa', %L, 'W1')$$, :'u_lan'), '23505');

-- recovery_case (W3): CHECKs and the one-open-case rule
SELECT pg_temp.expect_fail('recovery_case resolved without a renter decision', format(
  $$INSERT INTO app.recovery_case (zone_id, booking_id, new_return_at, deadline_at, status, idempotency_key)
    VALUES (%L, %L, now(), now() + interval '1 hour', 'resolved', 'rc-bad-1')$$, :'zone_a', :'bk_khach'), '23514', 'recovery_case_resolved_has_booking');
SELECT pg_temp.expect_fail('recovery_case escalated without an approval request', format(
  $$INSERT INTO app.recovery_case (zone_id, booking_id, new_return_at, deadline_at, status, idempotency_key)
    VALUES (%L, %L, now(), now() + interval '1 hour', 'escalated', 'rc-bad-2')$$, :'zone_a', :'bk_khach'), '23514', 'recovery_case_escalated_has_approval');
SELECT pg_temp.expect_fail('v6 recovery_case resolved as stay without an owner buffer slot', format(
  $$INSERT INTO app.recovery_case (zone_id, booking_id, new_return_at, deadline_at, renter_decision, status, idempotency_key)
    VALUES (%L, %L, now(), now() + interval '1 hour', 'stay', 'resolved', 'rc-bad-5')$$, :'zone_a', :'bk_khach'), '23514', 'recovery_case_resolved_has_booking');
SELECT pg_temp.expect_fail('v6 recovery_case move with an owner buffer slot', format(
  $$INSERT INTO app.recovery_case (zone_id, booking_id, new_return_at, deadline_at, renter_decision, owner_buffer_slot_id, idempotency_key)
    VALUES (%L, %L, now(), now() + interval '1 hour', 'move', %L, 'rc-bad-6')$$, :'zone_a', :'bk_khach', :'s_th3_a2'), '23514', 'recovery_case_move_has_no_buffer');
SELECT pg_temp.expect_fail('v6 recovery_case owner buffer slot of another zone (composite FK)', format(
  $$INSERT INTO app.recovery_case (zone_id, booking_id, new_return_at, deadline_at, owner_buffer_slot_id, idempotency_key)
    VALUES (%L, %L, now(), now() + interval '1 hour', %L, 'rc-bad-7')$$, :'zone_c', :'bk_hoa', :'s_th3_a2'), '23503');
SELECT pg_temp.expect_fail('recovery_case options must be a JSON array', format(
  $$INSERT INTO app.recovery_case (zone_id, booking_id, new_return_at, deadline_at, options, idempotency_key)
    VALUES (%L, %L, now(), now() + interval '1 hour', '{}'::jsonb, 'rc-bad-3')$$, :'zone_a', :'bk_khach'), '23514');
SELECT pg_temp.expect_fail('recovery_case booking of another zone (composite FK)', format(
  $$INSERT INTO app.recovery_case (zone_id, booking_id, new_return_at, deadline_at, idempotency_key)
    VALUES (%L, %L, now(), now() + interval '1 hour', 'rc-bad-4')$$, :'zone_c', :'bk_khach'), '23503');
INSERT INTO app.recovery_case (zone_id, booking_id, new_return_at, options, deadline_at, status, idempotency_key)
VALUES (:'zone_a', :'bk_khach', now() + interval '1 hour', jsonb_build_array(jsonb_build_object('slot_id', :'s_th3_a2', 'price_vnd', 40000)),
        now() + interval '30 minutes', 'options_ready', 'rc-open-1');
SELECT pg_temp.expect_fail('second open recovery_case on the same booking (partial UNIQUE)', format(
  $$INSERT INTO app.recovery_case (zone_id, booking_id, new_return_at, deadline_at, idempotency_key)
    VALUES (%L, %L, now(), now() + interval '1 hour', 'rc-open-2')$$, :'zone_a', :'bk_khach'), '23505');
SELECT pg_temp.expect_fail('replayed recovery_case idempotency key', format(
  $$INSERT INTO app.recovery_case (zone_id, booking_id, new_return_at, deadline_at, idempotency_key)
    VALUES (%L, %L, now(), now() + interval '1 hour', 'rc-open-1')$$, :'zone_c', :'bk_hoa'), '23505', 'recovery_case_idempotency_key_key');
UPDATE app.recovery_case SET status = 'cancelled' WHERE idempotency_key = 'rc-open-1';
WITH rc AS (INSERT INTO app.recovery_case (zone_id, booking_id, new_return_at, deadline_at, idempotency_key)
              VALUES (:'zone_a', :'bk_khach', now(), now() + interval '1 hour', 'rc-open-3') RETURNING 1)
SELECT pg_temp.expect('a cancelled case frees the booking for a new open case', count(*) = 1) FROM rc;

-- consent_record: append-only, natural idempotency
SELECT pg_temp.expect_fail('consent_record UPDATE (append-only)', $$UPDATE app.consent_record SET terms_version = 'v2'$$, '42501', 'append-only');
SELECT pg_temp.expect_fail('consent_record DELETE (append-only)', 'DELETE FROM app.consent_record', '42501', 'append-only');
SELECT pg_temp.expect_fail('consent_record TRUNCATE (append-only)', 'TRUNCATE app.consent_record CASCADE', '42501', 'append-only');
SELECT pg_temp.expect_fail('consent_record duplicate natural key (replayed confirmation)', format(
  $$INSERT INTO app.consent_record (user_id, zone_id, action, subject_type, subject_id, terms_version, decision)
    VALUES (%L, %L, 'agreement_confirm', 'agreement', %L, 'policy-v1', 'accepted')$$, :'u_lan', :'zone_a', :'ag_binh'), '23505', 'consent_record_natural_uq');
SELECT pg_temp.expect_fail('consent_record subject_type outside the allowed list', format(
  $$INSERT INTO app.consent_record (user_id, action, subject_type, subject_id, terms_version, decision)
    VALUES (%L, 'plate_processing', 'swap_proposal', app.uuid_v7(), 'v1', 'accepted')$$, :'u_lan'), '23514');
SELECT pg_temp.expect_fail('consent_record evidence must be a JSON object', format(
  $$INSERT INTO app.consent_record (user_id, action, subject_type, subject_id, terms_version, decision, evidence)
    VALUES (%L, 'plate_processing', 'app_user', %L, 'v1', 'accepted', '[]'::jsonb)$$, :'u_lan', :'u_lan'), '23514');
WITH w AS (INSERT INTO app.consent_record (user_id, action, subject_type, subject_id, terms_version, decision)
           VALUES (:'u_lan', 'registration_terms', 'app_user', :'u_lan', 'v1', 'withdrawn') RETURNING 1)
SELECT pg_temp.expect('a withdrawal is a new row, not an edit (same subject, different decision)', count(*) = 1) FROM w;

-- ai_decision_log: append-only, idempotent per node, no raw text columns
SELECT pg_temp.expect_fail('ai_decision_log UPDATE (append-only)', $$UPDATE app.ai_decision_log SET outcome = 'suggested'$$, '42501', 'append-only');
SELECT pg_temp.expect_fail('ai_decision_log DELETE (append-only)', 'DELETE FROM app.ai_decision_log', '42501', 'append-only');
SELECT pg_temp.expect_fail('ai_decision_log TRUNCATE (append-only)', 'TRUNCATE app.ai_decision_log', '42501', 'append-only');
SELECT pg_temp.expect_fail('ai_decision_log duplicate idempotency_key (node replay)', format(
  $$INSERT INTO app.ai_decision_log (thread_id, zone_id, user_hash, workflow, step, input_hash, output_hash, risk_level, outcome, idempotency_key)
    VALUES ('thread-hoa', %L, sha256('u'), 'W2', 'rule_engine.price_check', sha256('a'), sha256('b'), 'low', 'auto_applied', 'thread-hoa:c1:price_check')$$,
  :'zone_c'), '23505');
SELECT pg_temp.expect_fail('ai_decision_log hash of the wrong length (raw text is not a hash)', format(
  $$INSERT INTO app.ai_decision_log (zone_id, user_hash, workflow, step, input_hash, output_hash, risk_level, outcome, idempotency_key)
    VALUES (%L, sha256('u'), 'W2', 'x', '\x00', sha256('b'), 'low', 'auto_applied', 'bad-hash')$$, :'zone_c'), '23514');
SELECT pg_temp.expect_fail('ai_decision_log for an unknown thread (FK)', format(
  $$INSERT INTO app.ai_decision_log (thread_id, zone_id, user_hash, workflow, step, input_hash, output_hash, risk_level, outcome, idempotency_key)
    VALUES ('no-such-thread', %L, sha256('u'), 'W2', 'x', sha256('a'), sha256('b'), 'low', 'auto_applied', 'bad-thread')$$, :'zone_c'), '23503');
SELECT pg_temp.expect_fail('ai_decision_log outcome outside the enum', format(
  $$INSERT INTO app.ai_decision_log (zone_id, user_hash, workflow, step, input_hash, output_hash, risk_level, outcome, idempotency_key)
    VALUES (%L, sha256('u'), 'W2', 'x', sha256('a'), sha256('b'), 'low', 'approved', 'bad-outcome')$$, :'zone_c'), '22P02');
SELECT pg_temp.expect('ai_decision_log has no raw prompt / output / user-id column (hashes only, BR-14)',
  NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'app' AND table_name = 'ai_decision_log'
              AND column_name IN ('prompt', 'output', 'input', 'message', 'content', 'user_id', 'raw_text'))
  AND (SELECT count(*) FROM information_schema.columns WHERE table_schema = 'app' AND table_name = 'ai_decision_log'
       AND column_name IN ('user_hash', 'input_hash', 'output_hash')) = 3);

-- =====================================================================================================
\echo '== 8. RLS and privileges, as the application role'
DO $$ BEGIN EXECUTE format('GRANT USAGE ON SCHEMA %I TO parksmart_app', pg_my_temp_schema()::regnamespace); END $$;
GRANT EXECUTE ON FUNCTION pg_temp.expect(text, boolean), pg_temp.expect_fail(text, text, text, text) TO parksmart_app;

-- BQL of zone C
BEGIN;
SET LOCAL ROLE parksmart_app;
SELECT set_config('app.role', 'zone_manager', true), set_config('app.user_id', :'u_bql_c', true),
       set_config('app.zone_ids', format('{%s}', :'zone_c'), true) \gset ignored_
SELECT pg_temp.expect('BQL C sees no zone-A bookings', (SELECT count(*) FROM app.booking WHERE zone_id = :'zone_a') = 0);
SELECT pg_temp.expect('BQL C sees zone-C bookings', (SELECT count(*) FROM app.booking WHERE zone_id = :'zone_c') = 1);
SELECT pg_temp.expect('BR-17 BQL C sees no zone-A/B eligibility rows', (SELECT count(*) FROM app.eligibility WHERE zone_id <> :'zone_c') = 0);
SELECT pg_temp.expect('BR-17 BQL C sees no zone-B unit numbers', (SELECT count(*) FROM app.asset WHERE zone_id = :'zone_b') = 0);
SELECT pg_temp.expect('BR-17 BQL C still gets hoa''s attestation (L3)', (SELECT level FROM app.eligibility_level_at(:'u_hoa', :'bld_c1')) = 'L3');
SELECT pg_temp.expect('BQL C reads no zone-A consent evidence', (SELECT count(*) FROM app.consent_record WHERE zone_id = :'zone_a') = 0);
SELECT pg_temp.expect('BQL C reads no zone-A recovery cases', (SELECT count(*) FROM app.recovery_case WHERE zone_id = :'zone_a') = 0);
SELECT pg_temp.expect('BQL C reads the AI decision log of zone C only (2 rows)',
  (SELECT count(*) = 2 AND bool_and(zone_id = :'zone_c') FROM app.ai_decision_log));
SELECT pg_temp.expect('BQL C sees the thread awaiting its approval, and only that one',
  (SELECT count(*) = 1 AND bool_and(thread_id = 'thread-hoa') FROM app.agent_thread));
SELECT pg_temp.expect_fail('BQL C cannot UPDATE the AI decision log (no grant, no row)', 'UPDATE app.ai_decision_log SET outcome = ''failed''', '42501');
SELECT pg_temp.expect_fail('BQL C cannot DELETE consent evidence', 'DELETE FROM app.consent_record', '42501');
SELECT pg_temp.expect('BQL C sees only zone-C approvals', (SELECT bool_and(zone_id = :'zone_c') FROM app.approval_request));
SELECT pg_temp.expect_fail('BQL C cannot write zone-A config (RLS WITH CHECK)', format(
  $$INSERT INTO app.zone_policy (zone_id, version, effective_from, buffer_before, buffer_after, approval_threshold_vnd, hold_after_eta,
      agreement_confirm_ttl, prices, agreement_template_md) VALUES (%L, 2, now(), '0', '0', 0, '1 min', '1 min', '{}'::jsonb, 'x')$$, :'zone_a'), '42501');
SELECT pg_temp.expect('KPI view: BQL C sees only zone C (1 request)',
  (SELECT sum(requests_total) = 1 AND bool_and(zone_id = :'zone_c') FROM app.kpi_daily_v));
COMMIT;

-- BQL of zone A.
BEGIN;
SET LOCAL ROLE parksmart_app;
SELECT set_config('app.role', 'zone_manager', true), set_config('app.user_id', :'u_bql_a', true),
       set_config('app.zone_ids', format('{%s}', :'zone_a'), true) \gset ignored_
SELECT pg_temp.expect_fail('plate ciphertext is not selectable directly', 'SELECT plate_ciphertext FROM app.vehicle', '42501');
SELECT pg_temp.expect_fail('LPR plate ciphertext is not selectable directly (masked plates only, AC-12)', 'SELECT plate_ciphertext FROM app.lpr_event', '42501');
SELECT pg_temp.expect('BQL A reads the masked plate of an LPR event', (SELECT plate_masked FROM app.lpr_event WHERE id = :'ev1') = '30A-•••.22');
SELECT pg_temp.expect('BQL A reads zone-A consent evidence (2 agreement confirmations), not other users'' chain-wide registration rows',
  (SELECT count(*) FILTER (WHERE zone_id IS NOT NULL) = 2 AND bool_and(zone_id = :'zone_a' OR user_id = :'u_bql_a') FROM app.consent_record));
SELECT pg_temp.expect('BQL A reads the zone-A recovery case', (SELECT count(*) FROM app.recovery_case WHERE zone_id = :'zone_a') >= 1);
SELECT pg_temp.expect('BQL A cannot read the zone-C AI decisions', (SELECT count(*) FROM app.ai_decision_log WHERE zone_id = :'zone_c') = 0);
SELECT pg_temp.expect('zone_manager of another zone cannot read the zone-C thread', (SELECT count(*) FROM app.agent_thread) = 0);
SELECT pg_temp.expect('KPI view: BQL A sees only zone A (2 requests, 1 matched, 1 blocked)',
  (SELECT sum(requests_total) = 2 AND sum(matched) = 1 AND sum(blocked) = 1 AND bool_and(zone_id = :'zone_a') FROM app.kpi_daily_v));
COMMIT;

-- Resident hoa (zone B)
BEGIN;
SET LOCAL ROLE parksmart_app;
SELECT set_config('app.role', 'resident', true), set_config('app.user_id', :'u_hoa', true), set_config('app.zone_ids', '', true) \gset ignored_
SELECT pg_temp.expect('resident sees only own bookings', (SELECT count(*) = 1 AND bool_and(renter_user_id = :'u_hoa') FROM app.booking));
SELECT pg_temp.expect('resident sees only own eligibility', (SELECT bool_and(user_id = :'u_hoa') FROM app.eligibility));
SELECT pg_temp.expect('resident sees only self in app_user', (SELECT count(*) FROM app.app_user) = 1);
SELECT pg_temp.expect('resident sees open supply chain-wide (FR-27)', (SELECT count(*) FROM app.share_window) = 2);
SELECT pg_temp.expect('resident sees no LPR events', (SELECT count(*) FROM app.lpr_event) = 0);
SELECT pg_temp.expect('resident reads only own consent rows', (SELECT count(*) >= 1 AND bool_and(user_id = :'u_hoa') FROM app.consent_record));
SELECT pg_temp.expect('resident cannot read the AI decision log', (SELECT count(*) FROM app.ai_decision_log) = 0);
SELECT pg_temp.expect('resident reads only own agent threads', (SELECT count(*) = 1 AND bool_and(user_id = :'u_hoa') FROM app.agent_thread));
SELECT pg_temp.expect('resident sees no recovery case of other people', (SELECT count(*) FROM app.recovery_case) = 0);
SELECT pg_temp.expect('resident sees no KPI rows', (SELECT count(*) FROM app.kpi_daily_v) = 0);
SELECT pg_temp.expect('resident sees no parking requests of others', (SELECT count(*) FROM app.parking_request WHERE requester_user_id <> :'u_hoa') = 0);
SELECT pg_temp.expect_fail('IDOR: resident asks for another user''s level', format(
  $$SELECT * FROM app.eligibility_level_at(%L, %L)$$, :'u_minh', :'bld_a1'), '42501');
SELECT pg_temp.expect_fail('resident self-verifies a claim', format(
  $$INSERT INTO app.eligibility (user_id, asset_id, zone_id, role, valid_during, status, verified_by, verified_at)
    VALUES (%L, %L, %L, 'tenant', tstzrange(now(), NULL), 'verified', %L, now())$$, :'u_hoa', :'a_lan', :'zone_a', :'u_hoa'), '42501');
SELECT pg_temp.expect_fail('resident writes the AI decision log directly (RLS)', format(
  $$INSERT INTO app.ai_decision_log (zone_id, user_hash, workflow, step, input_hash, output_hash, risk_level, outcome, idempotency_key)
    VALUES (%L, sha256('u'), 'W2', 'x', sha256('a'), sha256('b'), 'low', 'auto_applied', 'res-1')$$, :'zone_c'), '42501');
SELECT pg_temp.expect_fail('resident writes consent evidence for someone else (RLS WITH CHECK)', format(
  $$INSERT INTO app.consent_record (user_id, action, subject_type, subject_id, terms_version, decision)
    VALUES (%L, 'plate_processing', 'app_user', %L, 'v1', 'accepted')$$, :'u_lan', :'u_lan'), '42501');
SELECT pg_temp.expect_fail('resident UPDATEs own consent row (no UPDATE grant)', $$UPDATE app.consent_record SET terms_version = 'v9'$$, '42501');
SELECT pg_temp.expect_fail('resident DELETEs own consent row (no DELETE grant)', 'DELETE FROM app.consent_record', '42501');
SELECT pg_temp.expect_fail('resident opens a thread in someone else''s name (RLS WITH CHECK)', format(
  $$INSERT INTO app.agent_thread (thread_id, user_id, workflow) VALUES ('t-x', %L, 'W1')$$, :'u_lan'), '42501');
SELECT pg_temp.expect_fail('app role has no DDL', 'CREATE TABLE app.evil (id int)', '42501');
SELECT pg_temp.expect_fail('app role cannot TRUNCATE', 'TRUNCATE app.notification', '42501');
COMMIT;

-- Chain operator: aggregates only (PRD §9).
BEGIN;
SET LOCAL ROLE parksmart_app;
SELECT set_config('app.role', 'chain_operator', true), set_config('app.user_id', :'u_op', true), set_config('app.zone_ids', '', true) \gset ignored_
SELECT pg_temp.expect('KPI view: chain operator reads every zone (3 requests in 2 zones)',
  (SELECT count(DISTINCT zone_id) = 2 AND sum(requests_total) = 3 FROM app.kpi_daily_v));
SELECT pg_temp.expect('chain operator reads no bookings', (SELECT count(*) FROM app.booking) = 0);
SELECT pg_temp.expect('chain operator reads no eligibility', (SELECT count(*) FROM app.eligibility) = 0);
SELECT pg_temp.expect('chain operator reads no parking requests (aggregates only)', (SELECT count(*) FROM app.parking_request) = 0);
SELECT pg_temp.expect('chain operator reads no consent evidence of others, AI decisions, threads or recovery cases',
  (SELECT count(*) FROM app.consent_record WHERE user_id <> :'u_op') + (SELECT count(*) FROM app.ai_decision_log)
  + (SELECT count(*) FROM app.agent_thread) + (SELECT count(*) FROM app.recovery_case) = 0);
COMMIT;

-- No context at all (a forgotten SET LOCAL): nothing private is visible.
BEGIN;
SET LOCAL ROLE parksmart_app;
SELECT set_config('app.role', '', true), set_config('app.user_id', '', true), set_config('app.zone_ids', '', true) \gset ignored_
SELECT pg_temp.expect('no context → no bookings, users, slots, KPI rows, evidence, threads', (SELECT count(*) FROM app.booking) + (SELECT count(*) FROM app.app_user)
                                                              + (SELECT count(*) FROM app.slot) + (SELECT count(*) FROM app.kpi_daily_v)
                                                              + (SELECT count(*) FROM app.consent_record) + (SELECT count(*) FROM app.agent_thread) = 0);
COMMIT;

-- =====================================================================================================
\echo '== 9. v2/v3/v4 checks: defaults, early-return settlement, rebooking, SET NULL, idempotency, v3 merged columns, agent schema'
-- Session context is back to role=system, all zones (set at the top).

-- 9.1 Researched defaults landed in the policy rows (D-01/02/04/08/16/21).
SELECT pg_temp.expect('zone policy carries the researched defaults', (
  SELECT buffer_before = '15 min' AND buffer_after = '30 min' AND approval_threshold_vnd = 1000000
     AND hold_after_eta = '10 min' AND hold_max = '40 min' AND th3_hold_max = '60 min'
     AND agreement_confirm_ttl = '30 min'
     AND eligibility_grace_max = '7 days' AND ocr_review_threshold = 0.800
     AND early_return_cost_rule = 'renter_priority_owner_buffer'
  FROM app.current_zone_policy(:'zone_a')));
SELECT pg_temp.expect('D-01 prices and the agreement template live in the policy row', (
  SELECT prices #>> '{TH1,L1,day}' = '50000' AND prices #>> '{TH2,L3,day}' = '70000' AND prices #>> '{TH3,L4,hour}' = '30000'
     AND agreement_template_md LIKE '# Thỏa thuận%'
  FROM app.current_zone_policy(:'zone_a')));

-- 9.2 Q9 / D-36 (v6, renter priority): owner reports an early return, ETA 10:00 from a one-time location. Binh is offered
-- TH3-013 for 10:00–12:00 and CHOOSES to move: same price, no extra charge, no refund entry; the owner gets the slot back.
-- (Had binh chosen 'stay', the owner would get a TH3 buffer slot instead — section 11.) One transaction (05 §2).
BEGIN;
SELECT id AS w_lan_locked FROM app.share_window WHERE id = :'w_lan' FOR UPDATE \gset ignored_
SELECT id AS bk_binh_locked FROM app.booking WHERE id = :'bk_binh' FOR UPDATE \gset ignored_
INSERT INTO app.booking (zone_id, slot_id, renter_user_id, vehicle_id, period, eligibility_level, price_vnd, status,
                         relocated_from_booking_id, idempotency_key)
VALUES (:'zone_a', :'s_th3_a2', :'u_binh', :'v_binh',
        tstzrange((:'d1' || ' 10:00+07')::timestamptz, (:'d1' || ' 12:00+07')::timestamptz), 'L2', 0,       -- covered by the original booking
        'confirmed', :'bk_binh', 'thread-er-1:w3.relocate')
RETURNING id AS bk_reloc \gset
UPDATE app.booking SET status = 'relocated' WHERE id = :'bk_binh';
UPDATE app.share_window SET status = 'closed_early', returned_at = (:'d1' || ' 10:00+07')::timestamptz WHERE id = :'w_lan';
-- v6: no payment rows for a voluntary move (D-36). v4: the W3 case (recovery_case) links the original and the replacement booking; the renter's acceptance is consent evidence.
INSERT INTO app.agent_thread (thread_id, user_id, zone_id, workflow, status) VALUES ('thread-er-1', :'u_lan', :'zone_a', 'W3', 'completed');
INSERT INTO app.recovery_case (zone_id, booking_id, new_return_at, eta_source, renter_decision, options, chosen_slot_id,
                               relocated_booking_id, status, deadline_at, resolution_note, idempotency_key)
VALUES (:'zone_a', :'bk_binh', (:'d1' || ' 10:00+07')::timestamptz, 'gps', 'move',
        jsonb_build_array(jsonb_build_object('slot_id', :'s_th3_a2', 'price_vnd', 0)), :'s_th3_a2', :'bk_reloc', 'resolved',
        (:'d1' || ' 09:55+07')::timestamptz, 'renter_moved', 'thread-er-1:w3.case')
RETURNING id AS rc_er \gset
INSERT INTO app.consent_record (user_id, zone_id, action, subject_type, subject_id, terms_version, decision, evidence)
VALUES (:'u_binh', :'zone_a', 'accept_relocation', 'recovery_case', :'rc_er', 'policy-v1', 'accepted',
        jsonb_build_object('replacement_booking_id', :'bk_reloc', 'decision', 'move'));
INSERT INTO app.ai_decision_log (thread_id, zone_id, user_hash, workflow, step, model_version, input_hash, output_hash, risk_level, outcome,
                                 human_approved, latency_ms, idempotency_key)
VALUES ('thread-er-1', :'zone_a', hmac(:'u_lan', :'pepper', 'sha256'), 'W3', 'rule_engine.relocation_options', NULL, sha256('er-in'), sha256('er-out'),
        'medium', 'suggested', true, 35, 'thread-er-1:c1:relocation_options');
COMMIT;
SELECT pg_temp.expect('D-36 a voluntary move records no charge and no refund',
  NOT EXISTS (SELECT 1 FROM app.payment WHERE booking_id IN (:'bk_binh', :'bk_reloc') AND idempotency_key LIKE 'thread-er-1:%'));
SELECT pg_temp.expect('D-36 the recovery_case links the original and the replacement booking, with the renter''s acceptance as evidence',
  (SELECT relocated_booking_id = :'bk_reloc' AND booking_id = :'bk_binh' AND status = 'resolved' FROM app.recovery_case WHERE id = :'rc_er')
  AND EXISTS (SELECT 1 FROM app.consent_record WHERE action = 'accept_relocation' AND subject_id = :'rc_er' AND decision = 'accepted')
  AND (SELECT relocated_from_booking_id FROM app.booking WHERE id = :'bk_reloc') = :'bk_binh');

-- 9.3 Check (a): a released slot/time can be taken again.
WITH w AS (INSERT INTO app.share_window (zone_id, slot_id, owner_user_id, period, bookable_period, open_scope, idempotency_key, owner_otp_confirmed_at, expires_at)
             VALUES (:'zone_a', :'s_045', :'u_lan',
                     tstzrange((:'d1' || ' 13:00+07')::timestamptz, (:'d1' || ' 18:00+07')::timestamptz),
                     tstzrange((:'d1' || ' 13:15+07')::timestamptz, (:'d1' || ' 17:30+07')::timestamptz), 'building',
                     'thread-lan:w2.publish-2', now(), now() + interval '30 minutes') RETURNING 1)
SELECT pg_temp.expect('(a) owner re-publishes B2-045 over the closed_early window''s time', count(*) = 1) FROM w;
SELECT pg_temp.expect('(a) relocated booking no longer blocks the TH1 slot at 10:00–12:00',
  NOT EXISTS (SELECT 1 FROM app.booking WHERE slot_id = :'s_045' AND status IN ('held','pending_agreement','pending_approval','confirmed')
              AND period && tstzrange((:'d1' || ' 10:00+07')::timestamptz, (:'d1' || ' 12:00+07')::timestamptz)));
INSERT INTO app.booking (zone_id, slot_id, renter_user_id, vehicle_id, period, eligibility_level, price_vnd, status, idempotency_key)
VALUES (:'zone_c', :'s_th3_c', :'u_khach', :'v_khach', tstzrange((:'d1' || ' 10:00+07')::timestamptz + interval '2 days',
        (:'d1' || ' 12:00+07')::timestamptz + interval '2 days'), 'L4', 60000, 'confirmed', 'rebook-1') RETURNING id AS bk_c1 \gset
UPDATE app.booking SET status = 'cancelled' WHERE id = :'bk_c1';
WITH b AS (INSERT INTO app.booking (zone_id, slot_id, renter_user_id, vehicle_id, period, eligibility_level, price_vnd, status, idempotency_key)
             VALUES (:'zone_c', :'s_th3_c', :'u_khach', :'v_khach', tstzrange((:'d1' || ' 10:00+07')::timestamptz + interval '2 days',
                     (:'d1' || ' 12:00+07')::timestamptz + interval '2 days'), 'L4', 60000, 'confirmed', 'rebook-2') RETURNING 1)
SELECT pg_temp.expect('(a) cancelled booking frees the same slot and time', count(*) = 1) FROM b;
INSERT INTO app.booking (zone_id, slot_id, renter_user_id, vehicle_id, period, eligibility_level, price_vnd, status, hold_expires_at, idempotency_key)
VALUES (:'zone_a', :'s_th3_a', :'u_khach', :'v_khach', tstzrange(now() + interval '3 days', now() + interval '3 days 1 hour'), 'L4', 30000,
        'held', now() - interval '1 minute', 'rebook-hold') RETURNING id AS bk_hold \gset
UPDATE app.booking SET status = 'expired' WHERE slot_id = :'s_th3_a' AND status = 'held' AND hold_expires_at < now();
WITH b AS (INSERT INTO app.booking (zone_id, slot_id, renter_user_id, vehicle_id, period, eligibility_level, price_vnd, status, idempotency_key)
             SELECT zone_id, slot_id, renter_user_id, vehicle_id, period, eligibility_level, price_vnd, 'confirmed', 'rebook-3'
             FROM app.booking WHERE id = :'bk_hold' RETURNING 1)
SELECT pg_temp.expect('(a) expired hold frees the same slot and time', count(*) = 1) FROM b;
INSERT INTO app.slot_holding (zone_id, slot_id, slot_type, user_id, kind, held_during)
VALUES (:'zone_b', :'s_b1', 'TH1', :'u_hoa', 'owner', tstzrange(now(), NULL)) RETURNING id AS hold_wrong \gset
SELECT pg_temp.expect_fail('(a) a live holding still blocks a second holder', format(
  $$INSERT INTO app.slot_holding (zone_id, slot_id, slot_type, user_id, kind, held_during) VALUES (%L, %L, 'TH1', %L, 'owner', tstzrange(now(), NULL))$$,
  :'zone_b', :'s_b1', :'u_minh'), '23P01');
UPDATE app.slot_holding SET voided_at = now(), void_reason = 'nhập nhầm chủ sở hữu' WHERE id = :'hold_wrong';
WITH h AS (INSERT INTO app.slot_holding (zone_id, slot_id, slot_type, user_id, kind, held_during)
             VALUES (:'zone_b', :'s_b1', 'TH1', :'u_minh', 'owner', tstzrange(now(), NULL)) RETURNING 1)
SELECT pg_temp.expect('(a) voided holding frees the slot for the right holder', count(*) = 1) FROM h;
SELECT pg_temp.expect_fail('(a) void without a reason', format(
  $$UPDATE app.slot_holding SET voided_at = now() WHERE slot_id = %L AND user_id = %L$$, :'s_b1', :'u_minh'), '23514');

-- 9.4 Check (c): ON DELETE SET NULL columns are not blocked by a CHECK or trigger.
INSERT INTO app.app_user (full_name, phone_e164, password_hash) VALUES ('Test Xóa', '+84909990001', :'pw') RETURNING id AS u_tmp \gset
INSERT INTO app.vehicle (user_id, plate_ciphertext, plate_hash, plate_masked, size_class)
VALUES (:'u_tmp', '\x01', hmac('99X99999', :'pepper', 'sha256'), '99X-•••.99', 'M') RETURNING id AS v_tmp \gset
INSERT INTO app.zone_policy (zone_id, version, effective_from, created_by, prices, agreement_template_md)
VALUES (:'zone_b', 1, now(), :'u_tmp', :'prices'::jsonb, :'tpl');
INSERT INTO app.lpr_event (zone_id, source_code, source_event_id, gate_code, direction, occurred_at, ocr_confidence, status, matched_vehicle_id)
VALUES (:'zone_a', 'demo-weekday', 'EV-SETNULL', 'G1', 'in', now() - interval '10 min', 0.95, 'accepted', :'v_tmp');
DELETE FROM app.vehicle WHERE id = :'v_tmp';
DELETE FROM app.app_user WHERE id = :'u_tmp';
SELECT pg_temp.expect('(c) SET NULL applied on lpr_event and zone_policy',
  (SELECT matched_vehicle_id IS NULL FROM app.lpr_event WHERE source_event_id = 'EV-SETNULL')
  AND (SELECT created_by IS NULL FROM app.zone_policy WHERE zone_id = :'zone_b'));
INSERT INTO app.app_user (full_name, phone_e164, password_hash, role) VALUES ('Bảo vệ tạm', '+84909990002', :'pw', 'guard') RETURNING id AS u_rev \gset
INSERT INTO app.lpr_event (zone_id, source_code, source_event_id, gate_code, direction, occurred_at, ocr_confidence, status, reviewed_by, reviewed_at)
VALUES (:'zone_a', 'demo-weekday', 'EV-REVIEWED', 'G1', 'in', now() - interval '5 min', 0.50, 'confirmed_manual', :'u_rev', now());
SELECT pg_temp.expect_fail('(c) reviewer of a reviewed LPR event cannot be deleted (RESTRICT, not a CHECK failure)', format(
  $$DELETE FROM app.app_user WHERE id = %L$$, :'u_rev'), '23503');

-- 9.5 Check (d): idempotency keys on the new write targets.
SELECT pg_temp.expect_fail('(d) replayed share-window publish', format(
  $$INSERT INTO app.share_window (zone_id, slot_id, owner_user_id, period, bookable_period, open_scope, idempotency_key, owner_otp_confirmed_at, expires_at)
    VALUES (%L, %L, %L, tstzrange(now() + interval '9 days', now() + interval '9 days 2 hours'),
            tstzrange(now() + interval '9 days', now() + interval '9 days 2 hours'), 'building', 'thread-lan:w2.publish', now(), now() + interval '30 minutes')$$,
  :'zone_a', :'s_045', :'u_lan'), '23505');
SELECT pg_temp.expect_fail('(d) replayed notification key', format(
  $$INSERT INTO app.notification (user_id, kind, title, body, idempotency_key) VALUES (%L, 'agreement_pending', 't', 'b', 'thread-binh:w2.notify')$$,
  :'u_binh'), '23505');
SELECT pg_temp.expect_fail('(d) replayed payment key', format(
  $$INSERT INTO app.payment (zone_id, booking_id, payer_user_id, kind, amount_vnd, idempotency_key) VALUES (%L, %L, %L, 'share_booking', 40000, 'pay-binh-1')$$,
  :'zone_a', :'bk_binh', :'u_binh'), '23505');
SELECT pg_temp.expect_fail('(d) replayed parking request key', format(
  $$INSERT INTO app.parking_request (zone_id, building_id, requester_user_id, vehicle_id, requested_period, computed_level, outcome, idempotency_key)
    VALUES (%L, %L, %L, %L, tstzrange(now(), now() + interval '1 hour'), 'L1', 'no_match', 'req-binh-1')$$,
  :'zone_a', :'bld_a1', :'u_binh', :'v_binh'), '23505');

-- 9.6 v3 checks: BR-11 through the ordered enum, LPR dedupe key, KPI view on the superuser/system context.
SELECT pg_temp.expect('BR-11 enum order S < M < L < XL', 'S'::app.size_class < 'M' AND 'M'::app.size_class < 'L' AND 'L'::app.size_class < 'XL');
INSERT INTO app.vehicle (user_id, plate_ciphertext, plate_hash, plate_masked, size_class)
VALUES (:'u_khach', pgp_sym_encrypt('29S11111', :'demo_key'), hmac('29S11111', :'pepper', 'sha256'), '29S-•••.11', 'S') RETURNING id AS v_khach_s \gset
WITH b AS (INSERT INTO app.booking (zone_id, slot_id, renter_user_id, vehicle_id, period, eligibility_level, price_vnd, status, idempotency_key)
             VALUES (:'zone_c', :'s_th3_c', :'u_khach', :'v_khach_s', tstzrange(now() + interval '10 days', now() + interval '10 days 1 hour'),
                     'L4', 30000, 'confirmed', 'br11-small') RETURNING 1)
SELECT pg_temp.expect('BR-11 a small vehicle fits a larger slot (enum <=)', count(*) = 1) FROM b;
WITH ins AS (INSERT INTO app.lpr_event (zone_id, source_code, source_event_id, gate_code, direction, occurred_at, ocr_confidence, status)
             VALUES (:'zone_c', 'demo-weekday', 'EV-88419', 'G1', 'in', now(), 0.9, 'accepted')
             ON CONFLICT (zone_id, source_code, source_event_id) DO NOTHING RETURNING 1)
SELECT pg_temp.expect('LPR dedupe key is scoped per zone: the same source event id is accepted in zone C', count(*) = 1) FROM ins;
WITH ins AS (INSERT INTO app.lpr_event (zone_id, source_code, source_event_id, gate_code, direction, occurred_at, ocr_confidence, status)
             VALUES (:'zone_a', 'demo-weekend', 'EV-88419', 'G1', 'in', now(), 0.9, 'accepted')
             ON CONFLICT (zone_id, source_code, source_event_id) DO NOTHING RETURNING 1)
SELECT pg_temp.expect('LPR dedupe key is scoped per source: another source with the same event id is accepted', count(*) = 1) FROM ins;
SELECT set_config('app.zone_ids', format('{%s}', :'zone_a'), false) \gset ignored_
SELECT pg_temp.expect('KPI view: system context scoped to zone A sees zone A only',
  (SELECT sum(requests_total) = 2 AND bool_and(zone_id = :'zone_a') FROM app.kpi_daily_v));
SELECT set_config('app.zone_ids', format('{%s,%s,%s}', :'zone_a', :'zone_b', :'zone_c'), false) \gset ignored_


-- 9.6b RLS of the early-return data (thread-er-1, recovery_case, accept_relocation evidence) now that it exists.
-- Another resident (binh) cannot read user lan's / hoa's thread, but reads his own consent and the case of his relocated booking.
BEGIN;
SET LOCAL ROLE parksmart_app;
SELECT set_config('app.role', 'resident', true), set_config('app.user_id', :'u_binh', true), set_config('app.zone_ids', '', true) \gset ignored_
SELECT pg_temp.expect('agent_thread: user B cannot read user A''s threads (thread-hoa, thread-er-1)',
  (SELECT count(*) FROM app.agent_thread WHERE thread_id IN ('thread-hoa', 'thread-er-1')) = 0);
SELECT pg_temp.expect('recovery_case: the renter of the relocated booking reads its case', (SELECT count(*) = 1 AND bool_and(status = 'resolved') FROM app.recovery_case));
SELECT pg_temp.expect('consent_record: binh reads own rows only', (SELECT count(*) = 3 AND bool_and(user_id = :'u_binh') FROM app.consent_record));
COMMIT;
BEGIN;
SET LOCAL ROLE parksmart_app;
SELECT set_config('app.role', 'resident', true), set_config('app.user_id', :'u_lan', true), set_config('app.zone_ids', '', true) \gset ignored_
SELECT pg_temp.expect('agent_thread: owner reads own thread', (SELECT count(*) FROM app.agent_thread WHERE thread_id = 'thread-er-1') = 1);
WITH u AS (UPDATE app.agent_thread SET status = 'failed' WHERE thread_id = 'thread-er-1' RETURNING 1)
SELECT pg_temp.expect('agent_thread: owner updates own thread', count(*) = 1) FROM u;
SELECT pg_temp.expect('recovery_case: the provider (owner) is a party too', (SELECT count(*) FROM app.recovery_case) = 1);
WITH w AS (INSERT INTO app.consent_record (user_id, action, subject_type, subject_id, terms_version, decision)
           VALUES (:'u_lan', 'plate_processing', 'app_user', :'u_lan', 'v1', 'accepted') RETURNING 1)
SELECT pg_temp.expect('consent_record: owner may append own evidence (INSERT + SELECT allowed)', count(*) = 1) FROM w;
ROLLBACK;
BEGIN;
SET LOCAL ROLE parksmart_app;
SELECT set_config('app.role', 'zone_manager', true), set_config('app.user_id', :'u_bql_a', true),
       set_config('app.zone_ids', format('{%s}', :'zone_a'), true) \gset ignored_
SELECT pg_temp.expect('BQL A reads all 3 zone-A consent rows (plus its own registration row) and the zone-A AI decision',
  (SELECT count(*) FILTER (WHERE zone_id IS NOT NULL) = 3 AND bool_and(zone_id = :'zone_a' OR user_id = :'u_bql_a') FROM app.consent_record)
  AND (SELECT count(*) = 1 AND bool_and(zone_id = :'zone_a') FROM app.ai_decision_log));
COMMIT;

-- 9.7 Check (b) / D-12: schema agent is isolated from the app role, and the checkpointer from schema app.
-- The real tables come from langgraph-checkpoint-postgres; this mock has the same key column (thread_id).
-- v3: no purge function (retention is deferred), so only the isolation is proven here.
GRANT USAGE, CREATE ON SCHEMA agent TO parksmart_checkpointer;
DO $$ BEGIN EXECUTE format('GRANT USAGE ON SCHEMA %I TO parksmart_checkpointer', pg_my_temp_schema()::regnamespace); END $$;
GRANT EXECUTE ON FUNCTION pg_temp.expect(text, boolean), pg_temp.expect_fail(text, text, text, text) TO parksmart_checkpointer;
SET ROLE parksmart_checkpointer;
CREATE TABLE agent.checkpoints (thread_id text NOT NULL, checkpoint_id text NOT NULL, checkpoint jsonb, PRIMARY KEY (thread_id, checkpoint_id));
INSERT INTO agent.checkpoints VALUES ('thread-done', 'c1', '{}'), ('thread-live', 'c1', '{}');
RESET ROLE;
BEGIN;
SET LOCAL ROLE parksmart_app;
SELECT pg_temp.expect_fail('(b) app role cannot read checkpoints', 'SELECT * FROM agent.checkpoints', '42501');
COMMIT;
BEGIN;
SET LOCAL ROLE parksmart_checkpointer;
SELECT pg_temp.expect_fail('(b) checkpointer role cannot read business tables', 'SELECT * FROM app.booking', '42501');
COMMIT;
SELECT pg_temp.expect('(b) owner was granted DELETE on checkpointer tables by default privileges',
  has_table_privilege('parksmart_owner', 'agent.checkpoints', 'DELETE'));

-- =====================================================================================================
\echo '== 10. v5: overstay fee (W4) and dispute (W5) — seed, constraints, RLS, KPI'
-- Kept at the end on purpose: sections 5-9 count rows (consent evidence, bookings, KPI requests) and must not see these.
SELECT pg_temp.expect('schema v7 has 26 tables in schema app (25 + bql_registry_import)',
  (SELECT count(*) FROM pg_tables WHERE schemaname = 'app') = 26);
SELECT pg_temp.expect('zone policy carries the D-03 overstay defaults (20 min reminder, 10 min grace, 50 000 đ/h, 15 min step)', (
  SELECT overstay_pre_reminder = '20 min' AND overstay_grace = '10 min' AND overstay_fee_per_hour_vnd = 50000
     AND overstay_billing_step = '15 min'
  FROM app.current_zone_policy(:'zone_a')));

-- 10.1 Seed: binh rented lan's TH1 slot B2-045 yesterday 08:00-12:00, left at 13:10 (70 min after the end, grace 10 min).
-- Fee (rule engine, D-03): ceil(70 / 15) = 5 steps x (50 000 đ/h x 15 min = 12 500 đ) = 62 500 đ, payee = provider lan.
INSERT INTO app.share_window (zone_id, slot_id, owner_user_id, period, bookable_period, open_scope, idempotency_key, owner_otp_confirmed_at, expires_at)
VALUES (:'zone_a', :'s_045', :'u_lan',
        tstzrange((:'d_yesterday' || ' 07:45+07')::timestamptz, (:'d_yesterday' || ' 18:00+07')::timestamptz),
        tstzrange((:'d_yesterday' || ' 08:00+07')::timestamptz, (:'d_yesterday' || ' 17:30+07')::timestamptz), 'building', 'thread-lan:w2.publish-over', now(), now() + interval '30 minutes')
RETURNING id AS w_over \gset
INSERT INTO app.booking (zone_id, slot_id, share_window_id, provider_user_id, renter_user_id, vehicle_id, period, eligibility_level,
                         price_vnd, status, checked_in_at, checked_out_at, idempotency_key)
VALUES (:'zone_a', :'s_045', :'w_over', :'u_lan', :'u_binh', :'v_binh',
        tstzrange((:'d_yesterday' || ' 08:00+07')::timestamptz, (:'d_yesterday' || ' 12:00+07')::timestamptz), 'L1', 40000, 'completed',
        (:'d_yesterday' || ' 08:05+07')::timestamptz, (:'d_yesterday' || ' 13:10+07')::timestamptz, 'thread-binh:w1.over')
RETURNING id AS bk_over \gset
INSERT INTO app.agreement (zone_id, booking_id, zone_policy_id, provider_user_id, renter_user_id, price_vnd, body_rendered, body_sha256,
                           status, requires_approval, confirm_deadline, provider_confirmed_at, renter_confirmed_at, effective_at)
VALUES (:'zone_a', :'bk_over', :'pol_a', :'u_lan', :'u_binh', 40000, 'Thỏa thuận GD-3 …', sha256(convert_to('Thỏa thuận GD-3 …', 'UTF8')),
        'effective', false, now() - interval '1 day', now() - interval '1 day', now() - interval '1 day', now() - interval '1 day')
RETURNING id AS ag_over \gset
INSERT INTO app.consent_record (user_id, zone_id, action, subject_type, subject_id, terms_version, decision, evidence)
SELECT u, :'zone_a', 'agreement_confirm', 'agreement', a.id, 'policy-v1', 'accepted',
       jsonb_build_object('body_sha256', encode(a.body_sha256, 'hex'), 'price_vnd', a.price_vnd, 'policy_version', 1)
FROM app.agreement a, LATERAL (VALUES (a.provider_user_id), (a.renter_user_id)) AS p(u) WHERE a.id = :'ag_over';
SELECT id AS cr_over FROM app.consent_record WHERE subject_id = :'ag_over' AND user_id = :'u_binh' \gset
-- N2: the two reminders (idempotent keys), then the fee at exit (N1). The fee is still unpaid when the dispute is opened.
INSERT INTO app.notification (user_id, zone_id, kind, title, body, link, idempotency_key) VALUES
  (:'u_binh', :'zone_a', 'overstay_pre_reminder', 'Sắp hết giờ đỗ', 'Chỗ B2-045 hết giờ lúc 12:00',
   jsonb_build_object('type', 'booking', 'id', :'bk_over'), 'overstay_pre:' || :'bk_over'),
  (:'u_binh', :'zone_a', 'overstay_due', 'Đã hết giờ đỗ', 'Quá 10 phút sẽ tính 12 500 đ mỗi 15 phút',
   jsonb_build_object('type', 'booking', 'id', :'bk_over'), 'overstay_due:' || :'bk_over');
INSERT INTO app.payment (zone_id, booking_id, payer_user_id, kind, amount_vnd, idempotency_key)
VALUES (:'zone_a', :'bk_over', :'u_binh', 'overstay_fee', 62500, 'overstay_fee:' || :'bk_over') RETURNING id AS pay_over \gset
SELECT pg_temp.expect('overstay_fee is a charge (direction) and is accepted once the booking is checked out',
  (SELECT direction = 'charge' AND status = 'recorded' FROM app.payment WHERE id = :'pay_over'));
INSERT INTO app.lpr_event (zone_id, source_code, source_event_id, gate_code, direction, occurred_at, plate_ciphertext, plate_hash,
                           plate_masked, ocr_confidence, status, matched_vehicle_id, matched_booking_id)
VALUES (:'zone_a', 'demo-weekday', 'EV-OVER-OUT', 'G1', 'out', (:'d_yesterday' || ' 13:10+07')::timestamptz,
        pgp_sym_encrypt('30A22222', :'demo_key'), hmac('30A22222', :'pepper', 'sha256'), '30A-•••.22', 0.940, 'accepted', :'v_binh', :'bk_over')
RETURNING id AS ev_over \gset

-- 10.2 Seed: binh disputes the fee ("the exit barrier was stuck"); W5 collects the evidence; lan is the respondent (payee).
INSERT INTO app.agent_thread (thread_id, user_id, zone_id, workflow, status) VALUES ('thread-disp-1', :'u_binh', :'zone_a', 'W5', 'active');
INSERT INTO app.dispute_case (zone_id, slot_id, booking_id, reporter_user_id, respondent_user_id, category, description, status,
                              thread_id, idempotency_key)
VALUES (:'zone_a', :'s_045', :'bk_over', :'u_binh', :'u_lan', 'overstay',
        'Thanh chắn cổng ra bị kẹt, xe chờ hơn một giờ mới ra được (biển số đã che).', 'collecting_evidence',
        'thread-disp-1', 'thread-disp-1:w5.open')
RETURNING id AS dc_1 \gset
INSERT INTO app.dispute_evidence (zone_id, case_id, kind, source, object_key_masked, object_key_original, sha256, submitted_by)
VALUES (:'zone_a', :'dc_1', 'photo', 'reporter', 'evidence/masked/tc-1-photo-1.jpg', 'evidence/original/tc-1-photo-1.jpg',
        sha256(convert_to('demo-photo-1', 'UTF8')), :'u_binh');
INSERT INTO app.dispute_evidence (zone_id, case_id, kind, source, lpr_event_id, snapshot)
SELECT zone_id, :'dc_1', 'lpr_event', 'system', id,
       jsonb_build_object('gate_code', gate_code, 'direction', direction, 'occurred_at', occurred_at, 'plate_masked', plate_masked,
                          'ocr_confidence', ocr_confidence)
FROM app.lpr_event WHERE id = :'ev_over';
INSERT INTO app.dispute_evidence (zone_id, case_id, kind, source, consent_record_id) VALUES (:'zone_a', :'dc_1', 'consent_record', 'system', :'cr_over');
INSERT INTO app.dispute_evidence (zone_id, case_id, kind, source, agreement_id) VALUES (:'zone_a', :'dc_1', 'agreement', 'system', :'ag_over');
INSERT INTO app.dispute_evidence (zone_id, case_id, kind, source, confidence, snapshot)
VALUES (:'zone_a', :'dc_1', 'ai_vision_extraction', 'system', 0.870,
        jsonb_build_object('observation', 'barrier arm down, one car waiting at the exit lane', 'suggestion_only', true));
INSERT INTO app.ai_decision_log (thread_id, zone_id, user_hash, workflow, step, model_version, input_hash, output_hash, risk_level, outcome,
                                 human_approved, latency_ms, idempotency_key)
VALUES ('thread-disp-1', :'zone_a', hmac(:'u_binh', :'pepper', 'sha256'), 'W5', 'vision.extract_masked_photo', 'claude-sonnet',
        sha256('disp-in'), sha256('disp-out'), 'medium', 'suggested', NULL, 1200, 'thread-disp-1:c1:vision');
UPDATE app.dispute_case SET ai_summary = 'Ảnh cho thấy thanh chắn cổng ra hạ xuống; LPR ghi xe ra lúc 13:10, quá giờ 70 phút. Gợi ý, chờ BQL quyết định.',
                            ai_confidence = 0.820 WHERE id = :'dc_1';
INSERT INTO app.approval_request (zone_id, kind, subject_id, thread_id, summary)
VALUES (:'zone_a', 'dispute_decision', :'dc_1', 'thread-disp-1', 'TC tranh chấp phí quá giờ') RETURNING id AS appr_dc \gset
UPDATE app.dispute_case SET status = 'awaiting_decision', ready_at = now(), approval_request_id = :'appr_dc' WHERE id = :'dc_1';
SELECT pg_temp.expect('dispute seeded: case awaiting the BQL decision with 5 evidence rows (photo, lpr_event, consent_record, agreement, ai_vision_extraction)',
  (SELECT status = 'awaiting_decision' AND ready_at IS NOT NULL AND approval_request_id = :'appr_dc' FROM app.dispute_case WHERE id = :'dc_1')
  AND (SELECT count(DISTINCT kind) = 5 AND count(*) = 5 FROM app.dispute_evidence WHERE case_id = :'dc_1'));
SELECT pg_temp.expect('LPR evidence snapshot carries the masked plate and no ciphertext',
  (SELECT snapshot ->> 'plate_masked' = '30A-•••.22' AND NOT snapshot ? 'plate_ciphertext' FROM app.dispute_evidence WHERE case_id = :'dc_1' AND kind = 'lpr_event'));

-- 10.3 Negative tests, owner / system context
SELECT pg_temp.expect_fail('overstay_fee before checkout (booking has no checked_out_at)', format(
  $$INSERT INTO app.payment (zone_id, booking_id, payer_user_id, kind, amount_vnd, idempotency_key)
    VALUES (%L, %L, %L, 'overstay_fee', 12500, 'overstay_fee:early')$$, :'zone_a', :'bk_binh', :'u_binh'), '23514', 'checked-out');
SELECT pg_temp.expect_fail('duplicate overstay pre-reminder (notification key overstay_pre:<booking_id>)', format(
  $$INSERT INTO app.notification (user_id, kind, title, body, idempotency_key) VALUES (%L, 'overstay_pre_reminder', 't', 'b', %L)$$,
  :'u_binh', 'overstay_pre:' || :'bk_over'), '23505', 'notification_idempotency_key_key');
SELECT pg_temp.expect_fail('zone_policy overstay_billing_step = 0', format(
  $$INSERT INTO app.zone_policy (zone_id, version, effective_from, prices, agreement_template_md, overstay_billing_step)
    VALUES (%L, 9, now(), '{}'::jsonb, 'x', interval '0')$$, :'zone_b'), '23514', 'overstay_billing_step');
SELECT pg_temp.expect_fail('zone_policy negative overstay_grace', format(
  $$INSERT INTO app.zone_policy (zone_id, version, effective_from, prices, agreement_template_md, overstay_grace)
    VALUES (%L, 9, now(), '{}'::jsonb, 'x', interval '-1 minute')$$, :'zone_b'), '23514', 'overstay_grace');
SELECT pg_temp.expect_fail('zone_policy negative overstay_pre_reminder', format(
  $$INSERT INTO app.zone_policy (zone_id, version, effective_from, prices, agreement_template_md, overstay_pre_reminder)
    VALUES (%L, 9, now(), '{}'::jsonb, 'x', interval '-5 minutes')$$, :'zone_b'), '23514', 'overstay_pre_reminder');
SELECT pg_temp.expect_fail('zone_policy negative overstay_fee_per_hour_vnd', format(
  $$INSERT INTO app.zone_policy (zone_id, version, effective_from, prices, agreement_template_md, overstay_fee_per_hour_vnd)
    VALUES (%L, 9, now(), '{}'::jsonb, 'x', -1)$$, :'zone_b'), '23514', 'overstay_fee_per_hour_vnd');

SELECT pg_temp.expect_fail('dispute_case in zone C on a zone-A slot (composite FK)', format(
  $$INSERT INTO app.dispute_case (zone_id, slot_id, reporter_user_id, category, description, idempotency_key)
    VALUES (%L, %L, %L, 'slot_occupied', 'x', 'dc-bad-1')$$, :'zone_c', :'s_th3_a', :'u_binh'), '23503');
SELECT pg_temp.expect_fail('dispute_case about a booking of another zone (composite FK)', format(
  $$INSERT INTO app.dispute_case (zone_id, slot_id, booking_id, reporter_user_id, category, description, idempotency_key)
    VALUES (%L, %L, %L, %L, 'overstay', 'x', 'dc-bad-2')$$, :'zone_a', :'s_045', :'bk_hoa', :'u_binh'), '23503');
SELECT pg_temp.expect_fail('dispute_case respondent = reporter', format(
  $$INSERT INTO app.dispute_case (zone_id, slot_id, reporter_user_id, respondent_user_id, category, description, idempotency_key)
    VALUES (%L, %L, %L, %L, 'damage', 'x', 'dc-bad-3')$$, :'zone_a', :'s_045', :'u_binh', :'u_binh'), '23514', 'dispute_case_parties_differ');
SELECT pg_temp.expect_fail('dispute_case awaiting_decision without ready_at', format(
  $$INSERT INTO app.dispute_case (zone_id, slot_id, reporter_user_id, category, description, status, idempotency_key)
    VALUES (%L, %L, %L, 'damage', 'x', 'awaiting_decision', 'dc-bad-4')$$, :'zone_a', :'s_045', :'u_lan'), '23514', 'dispute_case_ready_before_decision');
SELECT pg_temp.expect_fail('dispute_case resolved without resolved_by / resolved_at', format(
  $$UPDATE app.dispute_case SET status = 'resolved', resolution_code = 'fee_waived' WHERE id = %L$$, :'dc_1'), '23514', 'dispute_case_resolution_consistent');
SELECT pg_temp.expect_fail('dispute_case resolved_by set on an unresolved case', format(
  $$UPDATE app.dispute_case SET resolved_by = %L, resolved_at = now() WHERE id = %L$$, :'u_bql_a', :'dc_1'), '23514', 'dispute_case_resolution_consistent');
SELECT pg_temp.expect_fail('dispute_case resolution_code outside the list', format(
  $$UPDATE app.dispute_case SET status = 'resolved', resolution_code = 'refunded', resolved_by = %L, resolved_at = now() WHERE id = %L$$,
  :'u_bql_a', :'dc_1'), '23514', 'resolution_code');
SELECT pg_temp.expect_fail('dispute_case resolution_code on an open case', format(
  $$UPDATE app.dispute_case SET resolution_code = 'other' WHERE id = %L$$, :'dc_1'), '23514', 'dispute_case_resolution_code_final');
SELECT pg_temp.expect_fail('second open dispute_case, same reporter / booking / category', format(
  $$INSERT INTO app.dispute_case (zone_id, slot_id, booking_id, reporter_user_id, category, description, idempotency_key)
    VALUES (%L, %L, %L, %L, 'overstay', 'again', 'dc-dup-1')$$, :'zone_a', :'s_045', :'bk_over', :'u_binh'), '23505', 'dispute_case_open_booking_uq');
SELECT pg_temp.expect_fail('dispute_case approval_request of another zone (composite FK)', format(
  $$UPDATE app.dispute_case SET approval_request_id = %L WHERE id = %L$$, :'appr_hoa', :'dc_1'), '23503');
SELECT pg_temp.expect_fail('dispute_case replayed idempotency key', format(
  $$INSERT INTO app.dispute_case (zone_id, slot_id, reporter_user_id, category, description, idempotency_key)
    VALUES (%L, %L, %L, 'damage', 'x', 'thread-disp-1:w5.open')$$, :'zone_a', :'s_045', :'u_lan'), '23505');
BEGIN;
INSERT INTO app.dispute_case (zone_id, slot_id, reporter_user_id, category, description, idempotency_key)
VALUES (:'zone_a', :'s_th3_a', :'u_binh', 'slot_occupied', 'Có xe lạ đỗ ở chỗ của tôi', 'dc-noslot-1');
SELECT pg_temp.expect_fail('second open case without a booking: deduplicated per reporter / slot / category', format(
  $$INSERT INTO app.dispute_case (zone_id, slot_id, reporter_user_id, category, description, idempotency_key)
    VALUES (%L, %L, %L, 'slot_occupied', 'again', 'dc-noslot-2')$$, :'zone_a', :'s_th3_a', :'u_binh'), '23505', 'dispute_case_open_slot_uq');
ROLLBACK;

SELECT pg_temp.expect_fail('photo evidence without sha256', format(
  $$INSERT INTO app.dispute_evidence (zone_id, case_id, kind, source, object_key_masked, object_key_original, submitted_by)
    VALUES (%L, %L, 'photo', 'reporter', 'm.jpg', 'o.jpg', %L)$$, :'zone_a', :'dc_1', :'u_binh'), '23514', 'dispute_evidence_kind_required');
SELECT pg_temp.expect_fail('lpr_event evidence without snapshot', format(
  $$INSERT INTO app.dispute_evidence (zone_id, case_id, kind, source, lpr_event_id) VALUES (%L, %L, 'lpr_event', 'system', %L)$$,
  :'zone_a', :'dc_1', :'ev1'), '23514', 'dispute_evidence_kind_required');
SELECT pg_temp.expect_fail('ai_vision_extraction evidence without confidence', format(
  $$INSERT INTO app.dispute_evidence (zone_id, case_id, kind, source, snapshot) VALUES (%L, %L, 'ai_vision_extraction', 'system', '{}'::jsonb)$$,
  :'zone_a', :'dc_1'), '23514', 'dispute_evidence_kind_required');
SELECT pg_temp.expect_fail('note evidence carrying an lpr_event reference (column does not match the kind)', format(
  $$INSERT INTO app.dispute_evidence (zone_id, case_id, kind, source, lpr_event_id, snapshot, submitted_by)
    VALUES (%L, %L, 'note', 'zone_manager', %L, '{"text":"x"}'::jsonb, %L)$$, :'zone_a', :'dc_1', :'ev1', :'u_bql_a'), '23514', 'dispute_evidence_kind_exclusive');
SELECT pg_temp.expect_fail('reporter evidence without submitted_by', format(
  $$INSERT INTO app.dispute_evidence (zone_id, case_id, kind, source, snapshot) VALUES (%L, %L, 'note', 'reporter', '{"text":"x"}'::jsonb)$$,
  :'zone_a', :'dc_1'), '23514', 'dispute_evidence_submitter');
SELECT pg_temp.expect_fail('evidence source outside the list', format(
  $$INSERT INTO app.dispute_evidence (zone_id, case_id, kind, source, snapshot) VALUES (%L, %L, 'note', 'ai', '{"text":"x"}'::jsonb)$$,
  :'zone_a', :'dc_1'), '23514');
SELECT pg_temp.expect_fail('evidence confidence above 1', format(
  $$INSERT INTO app.dispute_evidence (zone_id, case_id, kind, source, confidence, snapshot) VALUES (%L, %L, 'ai_vision_extraction', 'system', 1.5, '{}'::jsonb)$$,
  :'zone_a', :'dc_1'), '23514');
SELECT pg_temp.expect_fail('evidence for a case of another zone (composite FK)', format(
  $$INSERT INTO app.dispute_evidence (zone_id, case_id, kind, source, snapshot) VALUES (%L, %L, 'note', 'system', '{"text":"x"}'::jsonb)$$,
  :'zone_c', :'dc_1'), '23503');
SELECT pg_temp.expect_fail('agreement evidence from another zone (composite FK)', format(
  $$INSERT INTO app.dispute_evidence (zone_id, case_id, kind, source, agreement_id) VALUES (%L, %L, 'agreement', 'system', %L)$$,
  :'zone_a', :'dc_1', :'appr_hoa_subject'), '23503');
SELECT pg_temp.expect_fail('the same LPR event added twice to one case (idempotent collection)', format(
  $$INSERT INTO app.dispute_evidence (zone_id, case_id, kind, source, lpr_event_id, snapshot) VALUES (%L, %L, 'lpr_event', 'system', %L, '{}'::jsonb)$$,
  :'zone_a', :'dc_1', :'ev_over'), '23505', 'dispute_evidence_lpr_uq');
SELECT pg_temp.expect_fail('the same consent record added twice to one case', format(
  $$INSERT INTO app.dispute_evidence (zone_id, case_id, kind, source, consent_record_id) VALUES (%L, %L, 'consent_record', 'system', %L)$$,
  :'zone_a', :'dc_1', :'cr_over'), '23505', 'dispute_evidence_consent_uq');
SELECT pg_temp.expect_fail('the same agreement added twice to one case', format(
  $$INSERT INTO app.dispute_evidence (zone_id, case_id, kind, source, agreement_id) VALUES (%L, %L, 'agreement', 'system', %L)$$,
  :'zone_a', :'dc_1', :'ag_over'), '23505', 'dispute_evidence_agreement_uq');
SELECT pg_temp.expect_fail('the same photo (sha256) added twice to one case', format(
  $$INSERT INTO app.dispute_evidence (zone_id, case_id, kind, source, object_key_masked, object_key_original, sha256, submitted_by)
    VALUES (%L, %L, 'photo', 'reporter', 'm2.jpg', 'o2.jpg', sha256(convert_to('demo-photo-1', 'UTF8')), %L)$$, :'zone_a', :'dc_1', :'u_binh'), '23505', 'dispute_evidence_photo_uq');
SELECT pg_temp.expect_fail('dispute_evidence UPDATE (append-only)', $$UPDATE app.dispute_evidence SET source = 'system'$$, '42501', 'append-only');
SELECT pg_temp.expect_fail('dispute_evidence DELETE (append-only)', 'DELETE FROM app.dispute_evidence', '42501', 'append-only');
SELECT pg_temp.expect_fail('dispute_evidence TRUNCATE (append-only)', 'TRUNCATE app.dispute_evidence', '42501', 'append-only');
SELECT pg_temp.expect_fail('dispute_case with evidence cannot be deleted (RESTRICT)', format($$DELETE FROM app.dispute_case WHERE id = %L$$, :'dc_1'), '23503');

-- 10.4 Second recorded overstay fee for the same booking, and the KPI columns (rolled back: leaves no data behind).
-- bk_khach (TH3, zone A) is already checked out (section 7), so a fee is allowed; the zone receives it (no provider).
BEGIN;
INSERT INTO app.payment (zone_id, booking_id, payer_user_id, kind, amount_vnd, idempotency_key)
VALUES (:'zone_a', :'bk_khach', :'u_khach', 'overstay_fee', 25000, 'overstay_fee:kpi-1');
SELECT pg_temp.expect_fail('second recorded overstay_fee for the same booking', format(
  $$INSERT INTO app.payment (zone_id, booking_id, payer_user_id, kind, amount_vnd, idempotency_key)
    VALUES (%L, %L, %L, 'overstay_fee', 12500, 'overstay_fee:kpi-2')$$, :'zone_a', :'bk_khach', :'u_khach'), '23505', 'payment_recorded_uq');
SELECT pg_temp.expect('KPI view: zone A keeps its request columns and adds overstay_fees, disputes_opened, dispute_prep_minutes_avg',
  (SELECT sum(requests_total) = 2 AND sum(matched) = 1 AND sum(blocked) = 1
      AND sum(overstay_fees) = 87500                        -- v6: binh's 62 500 is recorded (counted until waived) + 25 000
      AND sum(disputes_opened) = 1 AND bool_or(dispute_prep_minutes_avg IS NOT NULL)
   FROM app.kpi_daily_v WHERE zone_id = :'zone_a'));
SELECT pg_temp.expect('KPI view: zone C has no overstay fee and no dispute',
  (SELECT sum(overstay_fees) = 0 AND sum(disputes_opened) = 0 FROM app.kpi_daily_v WHERE zone_id = :'zone_c'));
ROLLBACK;

-- 10.5 RLS as the application role
-- binh: reporter. Reads own case and the masked evidence; adds a photo / note; cannot read the original key; cannot decide.
BEGIN;
SET LOCAL ROLE parksmart_app;
SELECT set_config('app.role', 'resident', true), set_config('app.user_id', :'u_binh', true), set_config('app.zone_ids', '', true) \gset ignored_
SELECT pg_temp.expect('reporter reads own dispute case', (SELECT count(*) = 1 AND bool_and(reporter_user_id = :'u_binh') FROM app.dispute_case));
SELECT pg_temp.expect('reporter reads the evidence of own case (5 rows) incl. the masked photo key',
  (SELECT count(*) = 5 AND count(*) FILTER (WHERE kind = 'photo' AND object_key_masked IS NOT NULL) = 1 FROM app.dispute_evidence));
SELECT pg_temp.expect_fail('original photo key is not selectable (explicit column)', 'SELECT object_key_original FROM app.dispute_evidence', '42501');
SELECT pg_temp.expect_fail('original photo key is not selectable (SELECT *)', 'SELECT * FROM app.dispute_evidence', '42501');
WITH n AS (INSERT INTO app.dispute_evidence (zone_id, case_id, kind, source, snapshot, submitted_by)
           VALUES (:'zone_a', :'dc_1', 'note', 'reporter', jsonb_build_object('text', 'Camera cổng ra có ghi lại.'), :'u_binh') RETURNING 1)
SELECT pg_temp.expect('reporter may add a note to own open case', count(*) = 1) FROM n;
SELECT pg_temp.expect_fail('reporter cannot write system evidence (lpr_event kind, RLS WITH CHECK)', format(
  $$INSERT INTO app.dispute_evidence (zone_id, case_id, kind, source, lpr_event_id, snapshot, submitted_by)
    VALUES (%L, %L, 'lpr_event', 'reporter', %L, '{}'::jsonb, %L)$$, :'zone_a', :'dc_1', :'ev1', :'u_binh'), '42501');
SELECT pg_temp.expect_fail('reporter cannot pose as the system (source system, RLS WITH CHECK)', format(
  $$INSERT INTO app.dispute_evidence (zone_id, case_id, kind, source, snapshot) VALUES (%L, %L, 'note', 'system', '{"text":"x"}'::jsonb)$$,
  :'zone_a', :'dc_1'), '42501');
SELECT pg_temp.expect_fail('reporter UPDATEs evidence (no UPDATE grant)', $$UPDATE app.dispute_evidence SET source = 'system'$$, '42501');
SELECT pg_temp.expect_fail('reporter DELETEs evidence (no DELETE grant)', 'DELETE FROM app.dispute_evidence', '42501');
WITH u AS (UPDATE app.dispute_case SET status = 'dismissed', resolution_code = 'rejected', resolved_by = :'u_binh', resolved_at = now() RETURNING 1)
SELECT pg_temp.expect('reporter cannot decide or change the case (UPDATE matches no row under RLS)', count(*) = 0) FROM u;
WITH c AS (INSERT INTO app.dispute_case (zone_id, slot_id, reporter_user_id, category, description, idempotency_key)
           VALUES (:'zone_a', :'s_045', :'u_binh', 'damage', 'Xước cản sau', 'dc-binh-2') RETURNING 1)
SELECT pg_temp.expect('reporter files a new case for themselves (status open)', count(*) = 1) FROM c;
SELECT pg_temp.expect_fail('reporter files a case in someone else''s name (RLS WITH CHECK)', format(
  $$INSERT INTO app.dispute_case (zone_id, slot_id, reporter_user_id, category, description, idempotency_key)
    VALUES (%L, %L, %L, 'damage', 'x', 'dc-binh-3')$$, :'zone_a', :'s_045', :'u_lan'), '42501');
SELECT pg_temp.expect_fail('reporter files a case that is already resolved (RLS WITH CHECK)', format(
  $$INSERT INTO app.dispute_case (zone_id, slot_id, reporter_user_id, category, description, status, ready_at, resolved_by, resolved_at, idempotency_key)
    VALUES (%L, %L, %L, 'damage', 'x', 'dismissed', now(), %L, now(), 'dc-binh-4')$$, :'zone_a', :'s_045', :'u_binh', :'u_binh'), '42501');
SELECT pg_temp.expect_fail('reporter names a respondent themselves (RLS WITH CHECK: system derives it)', format(
  $$INSERT INTO app.dispute_case (zone_id, slot_id, reporter_user_id, respondent_user_id, category, description, idempotency_key)
    VALUES (%L, %L, %L, %L, 'damage', 'x', 'dc-binh-5')$$, :'zone_a', :'s_045', :'u_binh', :'u_lan'), '42501');
SELECT pg_temp.expect_fail('reporter links a booking they are not a party to (RLS WITH CHECK, IDOR)', format(
  $$INSERT INTO app.dispute_case (zone_id, slot_id, booking_id, reporter_user_id, category, description, idempotency_key)
    VALUES (%L, %L, %L, %L, 'overstay', 'x', 'dc-binh-6')$$, :'zone_a', :'s_045', :'bk_khach', :'u_binh'), '42501');
SELECT pg_temp.expect_fail('reporter pre-fills the AI summary (RLS WITH CHECK)', format(
  $$INSERT INTO app.dispute_case (zone_id, slot_id, reporter_user_id, category, description, ai_summary, ai_confidence, idempotency_key)
    VALUES (%L, %L, %L, 'damage', 'x', 'Bên kia có lỗi', 0.99, 'dc-binh-7')$$, :'zone_a', :'s_045', :'u_binh'), '42501');
ROLLBACK;

-- lan: respondent. Sees the case and the evidence, but not the original key.
BEGIN;
SET LOCAL ROLE parksmart_app;
SELECT set_config('app.role', 'resident', true), set_config('app.user_id', :'u_lan', true), set_config('app.zone_ids', '', true) \gset ignored_
SELECT pg_temp.expect('respondent reads the case and its 5 evidence rows',
  (SELECT count(*) = 1 AND bool_and(respondent_user_id = :'u_lan') FROM app.dispute_case)
  AND (SELECT count(*) = 5 FROM app.dispute_evidence));
SELECT pg_temp.expect_fail('respondent cannot select the original key either', 'SELECT object_key_original FROM app.dispute_evidence', '42501');
SELECT pg_temp.expect_fail('respondent cannot add evidence (not the reporter, RLS WITH CHECK)', format(
  $$INSERT INTO app.dispute_evidence (zone_id, case_id, kind, source, snapshot, submitted_by)
    VALUES (%L, %L, 'note', 'reporter', '{"text":"x"}'::jsonb, %L)$$, :'zone_a', :'dc_1', :'u_lan'), '42501');
ROLLBACK;

-- minh: a resident of the same zone who is not a party. hoa / van: residents of other zones. Nobody sees the case.
BEGIN;
SET LOCAL ROLE parksmart_app;
SELECT set_config('app.role', 'resident', true), set_config('app.user_id', :'u_minh', true), set_config('app.zone_ids', '', true) \gset ignored_
SELECT pg_temp.expect('a resident who is not a party sees no dispute case and no evidence (same zone)',
  (SELECT count(*) FROM app.dispute_case) = 0 AND (SELECT count(*) FROM app.dispute_evidence) = 0);
SELECT pg_temp.expect_fail('a non-party cannot add evidence to the case (RLS WITH CHECK)', format(
  $$INSERT INTO app.dispute_evidence (zone_id, case_id, kind, source, snapshot, submitted_by)
    VALUES (%L, %L, 'note', 'reporter', '{"text":"x"}'::jsonb, %L)$$, :'zone_a', :'dc_1', :'u_minh'), '42501');
ROLLBACK;
BEGIN;
SET LOCAL ROLE parksmart_app;
SELECT set_config('app.role', 'resident', true), set_config('app.user_id', :'u_van', true), set_config('app.zone_ids', '', true) \gset ignored_
SELECT pg_temp.expect('a resident of another zone sees no dispute case and no evidence',
  (SELECT count(*) FROM app.dispute_case) = 0 AND (SELECT count(*) FROM app.dispute_evidence) = 0);
ROLLBACK;

-- BQL of zone C: another zone, no access to zone-A cases or evidence.
BEGIN;
SET LOCAL ROLE parksmart_app;
SELECT set_config('app.role', 'zone_manager', true), set_config('app.user_id', :'u_bql_c', true),
       set_config('app.zone_ids', format('{%s}', :'zone_c'), true) \gset ignored_
SELECT pg_temp.expect('BQL of another zone sees no dispute case and no evidence',
  (SELECT count(*) FROM app.dispute_case) = 0 AND (SELECT count(*) FROM app.dispute_evidence) = 0);
WITH u AS (UPDATE app.dispute_case SET status = 'dismissed' RETURNING 1)
SELECT pg_temp.expect('BQL of another zone cannot update the case (no row visible)', count(*) = 0) FROM u;
SELECT pg_temp.expect_fail('BQL of another zone cannot file evidence into it (RLS WITH CHECK)', format(
  $$INSERT INTO app.dispute_evidence (zone_id, case_id, kind, source, snapshot, submitted_by)
    VALUES (%L, %L, 'note', 'zone_manager', '{"text":"x"}'::jsonb, %L)$$, :'zone_a', :'dc_1', :'u_bql_c'), '42501');
ROLLBACK;

-- Chain operator: aggregates only (the KPI view), never the case.
BEGIN;
SET LOCAL ROLE parksmart_app;
SELECT set_config('app.role', 'chain_operator', true), set_config('app.user_id', :'u_op', true), set_config('app.zone_ids', '', true) \gset ignored_
SELECT pg_temp.expect('chain operator reads no dispute rows, only the KPI aggregates (1 dispute opened in zone A)',
  (SELECT count(*) FROM app.dispute_case) + (SELECT count(*) FROM app.dispute_evidence) = 0
  AND (SELECT sum(disputes_opened) = 1 FROM app.kpi_daily_v));
ROLLBACK;

-- BQL of zone A: works the queue, adds a note, decides. Waiver: dispute resolution 'fee_waived' + payment 'cancelled'.
BEGIN;
SET LOCAL ROLE parksmart_app;
SELECT set_config('app.role', 'zone_manager', true), set_config('app.user_id', :'u_bql_a', true),
       set_config('app.zone_ids', format('{%s}', :'zone_a'), true) \gset ignored_
SELECT pg_temp.expect('BQL of the slot''s zone sees the dispute queue (1 case awaiting a decision) and its 5 evidence rows',
  (SELECT count(*) = 1 AND bool_and(status = 'awaiting_decision' AND zone_id = :'zone_a') FROM app.dispute_case)
  AND (SELECT count(*) = 5 FROM app.dispute_evidence));
SELECT pg_temp.expect_fail('BQL cannot select the original photo key either', 'SELECT object_key_original FROM app.dispute_evidence', '42501');
SELECT pg_temp.expect('BQL sees the dispute_decision approval request', (SELECT count(*) = 1 FROM app.approval_request WHERE kind = 'dispute_decision' AND subject_id = :'dc_1'));
INSERT INTO app.dispute_evidence (zone_id, case_id, kind, source, snapshot, submitted_by)
VALUES (:'zone_a', :'dc_1', 'note', 'zone_manager', jsonb_build_object('text', 'Đã kiểm tra nhật ký thanh chắn: lỗi kỹ thuật.'), :'u_bql_a');
UPDATE app.approval_request SET status = 'approved', decided_by = :'u_bql_a', decided_at = now(), decision_note = 'Miễn phí quá giờ' WHERE id = :'appr_dc';
UPDATE app.dispute_case SET status = 'resolved', resolution_code = 'fee_waived', resolution_note = 'Thanh chắn lỗi, miễn phí quá giờ',
                            resolved_by = :'u_bql_a', resolved_at = now() WHERE id = :'dc_1';
UPDATE app.payment SET status = 'cancelled' WHERE id = :'pay_over';
COMMIT;

-- 10.6 Outcome of the decision flow
SELECT pg_temp.expect('decision flow: case resolved with fee_waived by the BQL, approval approved, overstay fee cancelled',
  (SELECT status = 'resolved' AND resolution_code = 'fee_waived' AND resolved_by = :'u_bql_a' AND resolved_at IS NOT NULL
     FROM app.dispute_case WHERE id = :'dc_1')
  AND (SELECT status = 'approved' AND decided_by = :'u_bql_a' FROM app.approval_request WHERE id = :'appr_dc')
  AND (SELECT status = 'cancelled' AND kind = 'overstay_fee' FROM app.payment WHERE id = :'pay_over')
  AND (SELECT count(*) = 6 FROM app.dispute_evidence WHERE case_id = :'dc_1'));
SELECT pg_temp.expect('a resolved case frees the booking for a new report (partial UNIQUE only covers open cases)',
  NOT EXISTS (SELECT 1 FROM app.dispute_case WHERE booking_id = :'bk_over' AND status NOT IN ('resolved', 'dismissed')));
SELECT pg_temp.expect('KPI view after the waiver: the cancelled fee is not counted, the dispute stays counted',
  (SELECT sum(overstay_fees) = 0 AND sum(disputes_opened) = 1 FROM app.kpi_daily_v WHERE zone_id = :'zone_a'));
BEGIN;
SET LOCAL ROLE parksmart_app;
SELECT set_config('app.role', 'resident', true), set_config('app.user_id', :'u_binh', true), set_config('app.zone_ids', '', true) \gset ignored_
SELECT pg_temp.expect_fail('reporter cannot add evidence once the case is resolved (RLS WITH CHECK)', format(
  $$INSERT INTO app.dispute_evidence (zone_id, case_id, kind, source, snapshot, submitted_by)
    VALUES (%L, %L, 'note', 'reporter', '{"text":"late"}'::jsonb, %L)$$, :'zone_a', :'dc_1', :'u_binh'), '42501');
SELECT pg_temp.expect('reporter still reads the resolved case with resolution_code fee_waived',
  (SELECT count(*) = 1 AND bool_and(resolution_code = 'fee_waived') FROM app.dispute_case WHERE id = :'dc_1'));
ROLLBACK;

-- =====================================================================================================
\echo '== 11. v6 pilot: queue, owner exit, renter decision, intake pause, fee ledger (rolled back)'
BEGIN;
-- 11.1 Queue (BR-21, D-34)
INSERT INTO app.parking_request (zone_id, building_id, requester_user_id, vehicle_id, requested_period, computed_level, outcome,
                                 queue_status, queued_at, idempotency_key)
VALUES (:'zone_a', :'bld_a1', :'u_tuan', :'v_tuan', tstzrange(now(), now() + interval '3 hours'), 'L1', 'queued', 'queued', now(), 'q-tuan-1');
SELECT pg_temp.expect('a queued request waits in the building queue',
  (SELECT count(*) = 1 FROM app.parking_request WHERE building_id = :'bld_a1' AND queue_status = 'queued'));
SELECT pg_temp.expect_fail('queued request without a queue status', format(
  $$INSERT INTO app.parking_request (zone_id, building_id, requester_user_id, vehicle_id, requested_period, computed_level, outcome, idempotency_key)
    VALUES (%L, %L, %L, %L, tstzrange(now(), now() + interval '1 hour'), 'L1', 'queued', 'q-bad-1')$$,
  :'zone_a', :'bld_a1', :'u_binh', :'v_binh'), '23514', 'parking_request_queue_shape');
SELECT pg_temp.expect_fail('matched request carrying a queue status', format(
  $$INSERT INTO app.parking_request (zone_id, building_id, requester_user_id, vehicle_id, requested_period, computed_level, outcome,
                                     queue_status, queued_at, idempotency_key)
    VALUES (%L, %L, %L, %L, tstzrange(now(), now() + interval '1 hour'), 'L1', 'matched', 'queued', now(), 'q-bad-2')$$,
  :'zone_a', :'bld_a1', :'u_binh', :'v_binh'), '23514', 'parking_request_queue_shape');
SELECT pg_temp.expect_fail('second waiting request of one renter in one building', format(
  $$INSERT INTO app.parking_request (zone_id, building_id, requester_user_id, vehicle_id, requested_period, computed_level, outcome,
                                     queue_status, queued_at, idempotency_key)
    VALUES (%L, %L, %L, %L, tstzrange(now(), now() + interval '1 hour'), 'L1', 'queued', 'queued', now(), 'q-tuan-2')$$,
  :'zone_a', :'bld_a1', :'u_tuan', :'v_tuan'), '23505', 'parking_request_one_live_uq');
UPDATE app.parking_request SET queue_status = 'assigned' WHERE idempotency_key = 'q-tuan-1';
SELECT pg_temp.expect('an assigned queue entry leaves the queued set and keeps its history',
  (SELECT outcome = 'queued' AND queue_status = 'assigned' FROM app.parking_request WHERE idempotency_key = 'q-tuan-1'));
-- 11.2 Owner exit (BR-20, D-35): posted is not free until the owner's car left.
SELECT pg_temp.expect('a posted window with the owner''s car inside is not offered',
  NOT EXISTS (SELECT 1 FROM app.share_window WHERE idempotency_key = 'thread-lan:w2.publish-2' AND owner_exited_at IS NOT NULL));
UPDATE app.share_window SET owner_exited_at = now() WHERE idempotency_key = 'thread-lan:w2.publish-2';
SELECT pg_temp.expect('after the gate saw the owner leave, the window is available',
  (SELECT count(*) = 1 FROM app.share_window WHERE zone_id = :'zone_a' AND status = 'open' AND owner_exited_at IS NOT NULL));
-- 11.3 Renter stays (BR-07, D-36): resolved with a TH3 buffer slot for the owner; no booking moves.
WITH rc AS (INSERT INTO app.recovery_case (zone_id, booking_id, new_return_at, eta_source, renter_decision, owner_buffer_slot_id,
                                           status, deadline_at, idempotency_key)
            VALUES (:'zone_c', :'bk_hoa', now() + interval '25 minutes', 'gps', 'stay', :'s_th3_c', 'resolved',
                    now() + interval '20 minutes', 'rc-stay-1') RETURNING 1)
SELECT pg_temp.expect('a stay decision resolves with an owner buffer slot', count(*) = 1) FROM rc;
-- 11.4 Intake pause (BR-24)
SELECT pg_temp.expect_fail('intake paused without a reason', format(
  $$UPDATE app.building SET intake_paused_at = now() WHERE id = %L$$, :'bld_a1'), '23514');
UPDATE app.building SET intake_paused_at = now(), intake_pause_reason = 'no free buffer slot (recovery case rc-x)' WHERE id = :'bld_a1';
SELECT pg_temp.expect('building intake pause is recorded with its reason',
  (SELECT intake_paused_at IS NOT NULL AND intake_pause_reason IS NOT NULL FROM app.building WHERE id = :'bld_a1'));
-- 11.5 Fee ledger (D-37): a cancel refund is a refund; location consent is evidence.
INSERT INTO app.payment (zone_id, booking_id, payer_user_id, kind, amount_vnd, idempotency_key)
VALUES (:'zone_c', :'bk_hoa', :'u_hoa', 'cancel_refund', 30000, 'cancel:hoa-1');
SELECT pg_temp.expect('cancel_refund is a recorded refund',
  (SELECT direction = 'refund' AND status = 'recorded' FROM app.payment WHERE idempotency_key = 'cancel:hoa-1'));
WITH c AS (INSERT INTO app.consent_record (user_id, zone_id, action, subject_type, subject_id, terms_version, decision)
           VALUES (:'u_lan', :'zone_a', 'location_share', 'app_user', :'u_lan', 'v1', 'accepted') RETURNING 1)
SELECT pg_temp.expect('one-time location consent is recorded (A-11)', count(*) = 1) FROM c;
ROLLBACK;
-- 11.6 RLS: W3 (system, zone A) may pause intake of a zone-A building, not of a zone-C building.
BEGIN;
SET LOCAL ROLE parksmart_app;
SELECT set_config('app.role', 'system', true), set_config('app.user_id', '', true),
       set_config('app.zone_ids', format('{%s}', :'zone_a'), true) \gset ignored_
WITH u AS (UPDATE app.building SET intake_paused_at = now(), intake_pause_reason = 'test' WHERE id = :'bld_a1' RETURNING 1)
SELECT pg_temp.expect('system pauses intake of its own zone''s building', count(*) = 1) FROM u;
WITH u AS (UPDATE app.building SET intake_paused_at = now(), intake_pause_reason = 'test' WHERE id = :'bld_c1' RETURNING 1)
SELECT pg_temp.expect('system cannot pause a building of another zone', count(*) = 0) FROM u;
ROLLBACK;

\echo '== done: all assertions passed'
