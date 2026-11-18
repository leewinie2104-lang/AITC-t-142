-- =====================================================================================================
-- ParkSmart AI — demo seed + constraint / RLS proofs (v3, MVP 27 tables)
-- Run after docs/03-design/sql/schema.sql on an EMPTY database, as the schema owner (or a superuser in a scratch DB):
--   psql -v ON_ERROR_STOP=1 -f docs/03-design/sql/seed-and-tests.sql
-- Every negative test goes through pg_temp.expect_fail(): it runs the statement in a sub-transaction and
-- aborts the whole script ("FAIL …") if the database ACCEPTS it or rejects it with an unexpected SQLSTATE.
-- Expected output: only "PASS …" / "OK …" lines.
-- v3: proofs of the 30 deferred tables (swaps, disputes, vouchers, erasure, retention, partitions, plate
-- reveal) are gone with them; the v2 script is in git: git show 333b85b:docs/database/08-seed-and-tests.sql
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
-- buffers 15/30 min, approval threshold 1 000 000 đ, hold 10 min, confirm 30 min, BR-16 carry-over 7 days,
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
INSERT INTO app.app_user (full_name, phone_e164, password_hash, role) VALUES ('BQL Khu A', '+84902000001', :'pw', 'zone_manager') RETURNING id AS u_bql_a \gset
INSERT INTO app.app_user (full_name, phone_e164, password_hash, role) VALUES ('BQL Khu C', '+84902000003', :'pw', 'zone_manager') RETURNING id AS u_bql_c \gset
INSERT INTO app.app_user (full_name, phone_e164, password_hash, role) VALUES ('Bảo vệ A', '+84903000001', :'pw', 'guard') RETURNING id AS u_guard_a \gset
INSERT INTO app.app_user (full_name, phone_e164, password_hash, role) VALUES ('Vận hành chuỗi', '+84904000001', :'pw', 'chain_operator') RETURNING id AS u_op \gset
INSERT INTO app.staff_zone (user_id, zone_id) VALUES (:'u_bql_a', :'zone_a'), (:'u_bql_c', :'zone_c'), (:'u_guard_a', :'zone_a');
-- Registration consent (A-03 / BR-09): the v2 consent table is two columns on app_user.
UPDATE app.app_user SET consent_text_version = 'v1', consented_at = now();

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

-- Plates: demo encryption with pgcrypto; the app uses AES-GCM with a KMS/SSM key (docs/08-operations/01-database-operations.md §3).
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

\echo '== 3. Seed: main flow (share → request → booking → agreement → ledger → payment)'
-- Lan shares B2-045 tomorrow 07:45–18:00; default buffers 15 min before / 30 min after → bookable 08:00–17:30.
INSERT INTO app.share_window (zone_id, slot_id, owner_user_id, period, bookable_period, open_scope, idempotency_key)
VALUES (:'zone_a', :'s_045', :'u_lan',
        tstzrange((:'d1' || ' 07:45+07')::timestamptz, (:'d1' || ' 18:00+07')::timestamptz),
        tstzrange((:'d1' || ' 08:00+07')::timestamptz, (:'d1' || ' 17:30+07')::timestamptz), 'building', 'thread-lan:w2.publish')
RETURNING id AS w_lan \gset
-- Van (zone C) lends TH2 B1-010 for a month, open to the whole chain (AC-20).
INSERT INTO app.share_window (zone_id, slot_id, owner_user_id, period, bookable_period, open_scope, idempotency_key)
VALUES (:'zone_c', :'s_c010', :'u_van',
        tstzrange((:'d1' || ' 06:30+07')::timestamptz, (:'d1' || ' 06:30+07')::timestamptz + interval '30 days'),
        tstzrange((:'d1' || ' 06:45+07')::timestamptz, (:'d1' || ' 06:00+07')::timestamptz + interval '30 days'),
        'chain', 'thread-van:w2.publish')
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
SELECT seq AS led1 FROM app.ledger_append(:'zone_a', 'agreement_effective', 'agreement', :'ag_binh',
       jsonb_build_object('booking_id', :'bk_binh', 'price_vnd', 40000), 'thread-binh:w2.ledger') \gset

-- Hoa's 21-day L3 rental (1 470 000 đ) is above the default threshold of 1 000 000 đ → HITL (AC-15, D-08).
INSERT INTO app.approval_request (zone_id, kind, subject_id, thread_id, summary)
VALUES (:'zone_c', 'agreement_over_threshold', app.uuid_v7(), 'thread-hoa', 'GD vượt ngưỡng') RETURNING id AS appr_hoa, subject_id AS appr_hoa_subject \gset
INSERT INTO app.agreement (id, zone_id, booking_id, zone_policy_id, provider_user_id, renter_user_id, price_vnd,
                           body_rendered, body_sha256, status, requires_approval, approval_request_id, confirm_deadline,
                           provider_confirmed_at, renter_confirmed_at)
VALUES (:'appr_hoa_subject', :'zone_c', :'bk_hoa', :'pol_c', :'u_van', :'u_hoa', 1470000, 'Thỏa thuận GD-2 …',
        sha256(convert_to('Thỏa thuận GD-2 …', 'UTF8')), 'pending_approval', true, :'appr_hoa', now() + interval '30 min', now(), now());

-- v3: no vouchers; the TH3 visit is paid in full.
INSERT INTO app.payment (zone_id, booking_id, payer_user_id, kind, amount_vnd, status, paid_at, idempotency_key)
VALUES (:'zone_a', :'bk_khach', :'u_khach', 'th3_visit', 60000, 'paid_simulated', now(), 'pay-khach-1');
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
        jsonb_build_object('type', 'agreement', 'id', :'ag_binh'), 'outbox:1');
INSERT INTO app.outbox (event_type, zone_id, payload) VALUES ('AgreementEffective', :'zone_a', jsonb_build_object('agreement_id', :'ag_binh'));
-- KPI: no table to seed — app.kpi_daily_v aggregates the parking_request rows of section 3.

-- =====================================================================================================
\echo '== 5. Positive checks (business rules derived by the database)'
SELECT pg_temp.expect('AC-19 minh is L2 at tower A1 (low-rise shophouse in A)', (SELECT level FROM app.eligibility_level_at(:'u_minh', :'bld_a1')) = 'L2');
SELECT pg_temp.expect('AC-19 minh is L1 at his own tower B1', (SELECT level FROM app.eligibility_level_at(:'u_minh', :'bld_b1')) = 'L1');
SELECT pg_temp.expect('AC-21 minh is only L3 in zone C (BR-15)', (SELECT level FROM app.eligibility_level_at(:'u_minh', :'bld_c1')) = 'L3');
SELECT pg_temp.expect('AC-22 expired tenant tuan falls to L4 (BR-16)', (SELECT level FROM app.eligibility_level_at(:'u_tuan', :'bld_a1')) = 'L4');
SELECT pg_temp.expect('L4 guest has no expiry', (SELECT valid_until IS NULL FROM app.eligibility_level_at(:'u_khach', :'bld_a1')));
SELECT pg_temp.expect('ledger chain of zone A verifies', app.ledger_verify(:'zone_a') IS NULL);
SELECT pg_temp.expect('ledger_append is idempotent on its key',
  (SELECT seq FROM app.ledger_append(:'zone_a', 'agreement_effective', 'agreement', :'ag_binh', '{}'::jsonb, 'thread-binh:w2.ledger')) = :'led1'
  AND (SELECT count(*) FROM app.ledger_entry WHERE idempotency_key = 'thread-binh:w2.ledger') = 1);
WITH ins AS (
  INSERT INTO app.lpr_event (zone_id, source_code, source_event_id, gate_code, direction, occurred_at, ocr_confidence, status)
  VALUES (:'zone_a', 'demo-weekday', 'EV-88419', 'G1', 'in', now(), 0.960, 'accepted')
  ON CONFLICT (zone_id, source_code, source_event_id) DO NOTHING RETURNING 1)
SELECT pg_temp.expect('LPR duplicate is ignored with ON CONFLICT DO NOTHING (AC-10a)', count(*) = 0) FROM ins;
SELECT pg_temp.expect('audit log captured eligibility inserts', (SELECT count(*) FROM app.audit_log WHERE table_name = 'eligibility') >= 7);
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
  $$INSERT INTO app.share_window (zone_id, slot_id, owner_user_id, period, bookable_period, open_scope, idempotency_key)
    VALUES (%L, %L, %L, tstzrange(now() + interval '5 days', now() + interval '5 days 2 hours'),
            tstzrange(now() + interval '5 days', now() + interval '5 days 2 hours'), 'zone', gen_random_uuid()::text)$$,
  :'zone_a', :'s_th3_a', :'u_lan'), '23514', 'BR-03');
SELECT pg_temp.expect_fail('AC-23 owner widens TH1 scope beyond tower rule', format(
  $$INSERT INTO app.share_window (zone_id, slot_id, owner_user_id, period, bookable_period, open_scope, idempotency_key)
    VALUES (%L, %L, %L, tstzrange(now() + interval '5 days', now() + interval '5 days 2 hours'),
            tstzrange(now() + interval '5 days', now() + interval '5 days 2 hours'), 'zone', gen_random_uuid()::text)$$,
  :'zone_a', :'s_045', :'u_lan'), '23514', 'AC-23');
SELECT pg_temp.expect_fail('non-holder shares a slot', format(
  $$INSERT INTO app.share_window (zone_id, slot_id, owner_user_id, period, bookable_period, open_scope, idempotency_key)
    VALUES (%L, %L, %L, tstzrange(now() + interval '5 days', now() + interval '5 days 2 hours'),
            tstzrange(now() + interval '5 days', now() + interval '5 days 2 hours'), 'building', gen_random_uuid()::text)$$,
  :'zone_a', :'s_045', :'u_binh'), '23514', 'does not hold');
SELECT pg_temp.expect_fail('overlapping open share windows on one slot', format(
  $$INSERT INTO app.share_window (zone_id, slot_id, owner_user_id, period, bookable_period, open_scope, idempotency_key)
    VALUES (%L, %L, %L, tstzrange(%L::timestamptz, %L::timestamptz), tstzrange(%L::timestamptz, %L::timestamptz), 'building', 'x-ov')$$,
  :'zone_a', :'s_045', :'u_lan', :'d1' || ' 12:00+07', :'d1' || ' 20:00+07', :'d1' || ' 12:00+07', :'d1' || ' 20:00+07'), '23P01');
SELECT pg_temp.expect_fail('bookable period wider than the window', format(
  $$INSERT INTO app.share_window (zone_id, slot_id, owner_user_id, period, bookable_period, open_scope, idempotency_key)
    VALUES (%L, %L, %L, tstzrange(now() + interval '6 days', now() + interval '6 days 2 hours'),
            tstzrange(now() + interval '6 days', now() + interval '6 days 3 hours'), 'building', 'x-wide')$$,
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

-- Agreement, approvals, ledger
SELECT pg_temp.expect_fail('AC-07 agreement effective with one confirmation', format(
  $$UPDATE app.agreement SET status = 'effective', effective_at = now(), renter_confirmed_at = NULL WHERE id = %L$$, :'ag_binh'), '23514');
SELECT pg_temp.expect_fail('AC-15 over-threshold agreement effective without approval', format(
  $$UPDATE app.agreement SET status = 'effective', effective_at = now(), approval_request_id = NULL WHERE booking_id = %L$$, :'bk_hoa'), '23514');
SELECT pg_temp.expect_fail('second pending approval for the same subject', format(
  $$INSERT INTO app.approval_request (zone_id, kind, subject_id, thread_id) VALUES (%L, 'agreement_over_threshold', %L, 't2')$$,
  :'zone_c', :'appr_hoa_subject'), '23505');
SELECT pg_temp.expect_fail('approval marked approved without approver', format(
  $$UPDATE app.approval_request SET status = 'approved' WHERE id = %L$$, :'appr_hoa'), '23514');
SELECT pg_temp.expect_fail('ledger UPDATE (append-only)', format(
  $$UPDATE app.ledger_entry SET payload = '{"price_vnd": 1}' WHERE zone_id = %L$$, :'zone_a'), '42501');
SELECT pg_temp.expect_fail('ledger DELETE (append-only)', format($$DELETE FROM app.ledger_entry WHERE zone_id = %L$$, :'zone_a'), '42501');
SELECT pg_temp.expect_fail('ledger TRUNCATE (append-only)', 'TRUNCATE app.ledger_entry CASCADE', '42501');

-- Money, payments
SELECT pg_temp.expect_fail('negative payment amount', format(
  $$INSERT INTO app.payment (zone_id, booking_id, payer_user_id, kind, amount_vnd, idempotency_key)
    VALUES (%L, %L, %L, 'th3_visit', -1, 'p3')$$, :'zone_a', :'bk_khach', :'u_khach'), '23514');
SELECT pg_temp.expect_fail('A-05 real payment provider', format(
  $$INSERT INTO app.payment (zone_id, booking_id, payer_user_id, kind, amount_vnd, provider, idempotency_key)
    VALUES (%L, %L, %L, 'share_booking', 50000, 'momo', 'p6')$$, :'zone_a', :'bk_binh', :'u_binh'), '23514');
SELECT pg_temp.expect_fail('paid payment without a paid_at timestamp', format(
  $$INSERT INTO app.payment (zone_id, booking_id, payer_user_id, kind, amount_vnd, status, idempotency_key)
    VALUES (%L, %L, %L, 'share_booking', 50000, 'paid_simulated', 'p8')$$, :'zone_a', :'bk_binh', :'u_binh'), '23514');
SELECT pg_temp.expect_fail('second successful payment for one booking', format(
  $$INSERT INTO app.payment (zone_id, booking_id, payer_user_id, kind, amount_vnd, status, paid_at, idempotency_key)
    VALUES (%L, %L, %L, 'th3_visit', 50000, 'paid_simulated', now(), 'p7')$$, :'zone_a', :'bk_khach', :'u_khach'), '23505');

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

-- v3 merged columns: policy prices / template, consent pair, BR-11 enum
SELECT pg_temp.expect_fail('zone_policy.prices must be a JSON object', format(
  $$INSERT INTO app.zone_policy (zone_id, version, effective_from, prices, agreement_template_md) VALUES (%L, 9, now(), '[]'::jsonb, 'x')$$, :'zone_b'), '23514', 'prices');
SELECT pg_temp.expect_fail('zone_policy.prices is required', format(
  $$INSERT INTO app.zone_policy (zone_id, version, effective_from, agreement_template_md) VALUES (%L, 9, now(), 'x')$$, :'zone_b'), '23502');
SELECT pg_temp.expect_fail('zone_policy agreement template must not be blank', format(
  $$INSERT INTO app.zone_policy (zone_id, version, effective_from, prices, agreement_template_md) VALUES (%L, 9, now(), '{}'::jsonb, '   ')$$, :'zone_b'), '23514', 'agreement_template_md');
SELECT pg_temp.expect_fail('consent pair: version without timestamp', format(
  $$UPDATE app.app_user SET consented_at = NULL WHERE id = %L$$, :'u_lan'), '23514', 'app_user_consent_pair');
SELECT pg_temp.expect_fail('consent pair: timestamp without version', $$INSERT INTO app.app_user (full_name, phone_e164, password_hash, consented_at) VALUES ('X', '+84909999997', '$argon2id$x', now())$$, '23514', 'app_user_consent_pair');
SELECT pg_temp.expect_fail('size outside the enum on a vehicle', format(
  $$INSERT INTO app.vehicle (user_id, plate_masked, size_class) VALUES (%L, 'x', 'XXL')$$, :'u_binh'), '22P02');
SELECT pg_temp.expect_fail('ledger subject_type of a removed table', format(
  $$SELECT * FROM app.ledger_append(%L, 'agreement_effective', 'swap_proposal', %L, '{}', 'k-swap')$$, :'zone_a', :'ag_binh'), '23514');
SELECT pg_temp.expect_fail('audit_log DELETE (strictly append-only)', 'DELETE FROM app.audit_log', '42501');
SELECT pg_temp.expect_fail('audit_log TRUNCATE (strictly append-only)', 'TRUNCATE app.audit_log', '42501');

\echo '== 7. Tamper detection: a row edited behind the triggers is found by ledger_verify'
BEGIN;
ALTER TABLE app.ledger_entry DISABLE TRIGGER ledger_entry_no_update;
UPDATE app.ledger_entry SET payload = payload || '{"price_vnd": 1}' WHERE zone_id = :'zone_a' AND seq = 1;
SELECT pg_temp.expect('tampered seq 1 is reported', app.ledger_verify(:'zone_a') = 1);
ROLLBACK;

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
SELECT pg_temp.expect('BQL C reads no zone-A ledger', (SELECT count(*) FROM app.ledger_entry WHERE zone_id = :'zone_a') = 0);
SELECT pg_temp.expect('BQL C sees only zone-C approvals', (SELECT bool_and(zone_id = :'zone_c') FROM app.approval_request));
SELECT pg_temp.expect_fail('BQL C cannot verify the zone-A chain', format($$SELECT app.ledger_verify(%L)$$, :'zone_a'), '42501');
SELECT pg_temp.expect_fail('BQL C cannot write zone-A config (RLS WITH CHECK)', format(
  $$INSERT INTO app.zone_policy (zone_id, version, effective_from, buffer_before, buffer_after, approval_threshold_vnd, hold_ttl,
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
SELECT pg_temp.expect('ledger zone A verifies under BQL A', app.ledger_verify(:'zone_a') IS NULL);
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
SELECT pg_temp.expect('resident sees no ledger rows', (SELECT count(*) FROM app.ledger_entry) = 0);
SELECT pg_temp.expect('resident sees no KPI rows', (SELECT count(*) FROM app.kpi_daily_v) = 0);
SELECT pg_temp.expect('resident sees no parking requests of others', (SELECT count(*) FROM app.parking_request WHERE requester_user_id <> :'u_hoa') = 0);
SELECT pg_temp.expect_fail('IDOR: resident asks for another user''s level', format(
  $$SELECT * FROM app.eligibility_level_at(%L, %L)$$, :'u_minh', :'bld_a1'), '42501');
SELECT pg_temp.expect_fail('resident self-verifies a claim', format(
  $$INSERT INTO app.eligibility (user_id, asset_id, zone_id, role, valid_during, status, verified_by, verified_at)
    VALUES (%L, %L, %L, 'tenant', tstzrange(now(), NULL), 'verified', %L, now())$$, :'u_hoa', :'a_lan', :'zone_a', :'u_hoa'), '42501');
SELECT pg_temp.expect_fail('resident writes the ledger directly', format(
  $$INSERT INTO app.ledger_entry (zone_id, seq, entry_type, subject_type, subject_id, payload, idempotency_key, created_at, prev_hash, hash)
    VALUES (%L, 99, 'agreement_effective', 'agreement', %L, '{}', 'k', now(), '\x00', '\x00')$$, :'zone_a', :'ag_binh'), '42501');
SELECT pg_temp.expect_fail('resident appends to the ledger via function', format(
  $$SELECT * FROM app.ledger_append(%L, 'agreement_effective', 'agreement', %L, '{}', 'k2')$$, :'zone_a', :'ag_binh'), '42501');
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
COMMIT;

-- No context at all (a forgotten SET LOCAL): nothing private is visible.
BEGIN;
SET LOCAL ROLE parksmart_app;
SELECT set_config('app.role', '', true), set_config('app.user_id', '', true), set_config('app.zone_ids', '', true) \gset ignored_
SELECT pg_temp.expect('no context → no bookings, users, slots, KPI rows', (SELECT count(*) FROM app.booking) + (SELECT count(*) FROM app.app_user)
                                                              + (SELECT count(*) FROM app.slot) + (SELECT count(*) FROM app.kpi_daily_v) = 0);
COMMIT;

-- =====================================================================================================
\echo '== 9. v2/v3 checks: defaults, early-return settlement, rebooking, SET NULL, idempotency, v3 merged columns, agent schema'
-- Session context is back to role=system, all zones (set at the top).

-- 9.1 Researched defaults landed in the policy rows (D-01/02/04/08/16/21).
SELECT pg_temp.expect('zone policy carries the researched defaults', (
  SELECT buffer_before = '15 min' AND buffer_after = '30 min' AND approval_threshold_vnd = 1000000
     AND hold_ttl = '10 min' AND agreement_confirm_ttl = '30 min'
     AND eligibility_grace_max = '7 days' AND ocr_review_threshold = 0.800
     AND early_return_cost_rule = 'renter_pays_th3_relocated'
  FROM app.current_zone_policy(:'zone_a')));
SELECT pg_temp.expect('D-01 prices and the agreement template live in the policy row', (
  SELECT prices #>> '{TH1,L1,day}' = '50000' AND prices #>> '{TH2,L3,day}' = '70000' AND prices #>> '{TH3,L4,hour}' = '30000'
     AND agreement_template_md LIKE '# Thỏa thuận%'
  FROM app.current_zone_policy(:'zone_a')));

-- 9.2 Q9 / D-09: owner returns early at 10:00. Renter moved to TH3-013 for 10:00–12:00, pays the TH3 price for that
-- period only; the unused 2 h of the share are refunded; the provider pays nothing. One transaction (05 §2).
BEGIN;
SELECT id AS w_lan_locked FROM app.share_window WHERE id = :'w_lan' FOR UPDATE \gset ignored_
SELECT id AS bk_binh_locked FROM app.booking WHERE id = :'bk_binh' FOR UPDATE \gset ignored_
INSERT INTO app.booking (zone_id, slot_id, renter_user_id, vehicle_id, period, eligibility_level, price_vnd, status,
                         relocated_from_booking_id, idempotency_key)
VALUES (:'zone_a', :'s_th3_a2', :'u_binh', :'v_binh',
        tstzrange((:'d1' || ' 10:00+07')::timestamptz, (:'d1' || ' 12:00+07')::timestamptz), 'L2', 40000,   -- 2 h × 20 000 (TH3 L2)
        'confirmed', :'bk_binh', 'thread-er-1:w3.relocate')
RETURNING id AS bk_reloc \gset
UPDATE app.booking SET status = 'relocated' WHERE id = :'bk_binh';
UPDATE app.share_window SET status = 'closed_early', returned_at = (:'d1' || ' 10:00+07')::timestamptz WHERE id = :'w_lan';
INSERT INTO app.payment (zone_id, booking_id, payer_user_id, kind, amount_vnd, idempotency_key)
VALUES (:'zone_a', :'bk_binh', :'u_binh', 'early_return_refund', 20000, 'thread-er-1:w3.refund'),
       (:'zone_a', :'bk_reloc', :'u_binh', 'relocation_th3', 40000, 'thread-er-1:w3.th3');
SELECT seq AS led_er FROM app.ledger_append(:'zone_a', 'early_return_settlement', 'booking', :'bk_binh',
       jsonb_build_object('replacement_booking_id', :'bk_reloc', 'refund_vnd', 20000, 'th3_charge_vnd', 40000,
                          'provider_extra_cost_vnd', 0, 'rule', 'renter_pays_th3_relocated'),
       'thread-er-1:w3.ledger') \gset
COMMIT;
SELECT pg_temp.expect('D-09 refund is a refund, TH3 charge is a charge',
  (SELECT count(*) FROM app.payment WHERE idempotency_key = 'thread-er-1:w3.refund' AND direction = 'refund') = 1
  AND (SELECT count(*) FROM app.payment WHERE idempotency_key = 'thread-er-1:w3.th3' AND direction = 'charge') = 1);
SELECT pg_temp.expect('D-09 settlement is in the ledger and the chain still verifies',
  EXISTS (SELECT 1 FROM app.ledger_entry WHERE entry_type = 'early_return_settlement' AND seq = :'led_er')
  AND app.ledger_verify(:'zone_a') IS NULL);

-- 9.3 Check (a): a released slot/time can be taken again.
WITH w AS (INSERT INTO app.share_window (zone_id, slot_id, owner_user_id, period, bookable_period, open_scope, idempotency_key)
             VALUES (:'zone_a', :'s_045', :'u_lan',
                     tstzrange((:'d1' || ' 13:00+07')::timestamptz, (:'d1' || ' 18:00+07')::timestamptz),
                     tstzrange((:'d1' || ' 13:15+07')::timestamptz, (:'d1' || ' 17:30+07')::timestamptz), 'building',
                     'thread-lan:w2.publish-2') RETURNING 1)
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
  $$INSERT INTO app.share_window (zone_id, slot_id, owner_user_id, period, bookable_period, open_scope, idempotency_key)
    VALUES (%L, %L, %L, tstzrange(now() + interval '9 days', now() + interval '9 days 2 hours'),
            tstzrange(now() + interval '9 days', now() + interval '9 days 2 hours'), 'building', 'thread-lan:w2.publish')$$,
  :'zone_a', :'s_045', :'u_lan'), '23505');

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

\echo '== done: all assertions passed'
