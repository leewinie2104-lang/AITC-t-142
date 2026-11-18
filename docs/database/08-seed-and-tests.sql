-- =====================================================================================================
-- ParkSmart AI — demo seed + constraint / RLS proofs
-- Run after 02-schema.sql on an EMPTY database, as the schema owner (or a superuser in a scratch DB):
--   psql -v ON_ERROR_STOP=1 -f 08-seed-and-tests.sql
-- Every negative test goes through pg_temp.expect_fail(): it runs the statement in a sub-transaction and
-- aborts the whole script ("FAIL …") if the database ACCEPTS it or rejects it with an unexpected SQLSTATE.
-- Expected output: only "PASS …" / "OK …" lines.
--
-- Scenario (Scope §1): chain of 3 zones.
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
INSERT INTO app.chain (code, name) VALUES ('PARKSMART', 'Chuỗi khu đô thị demo') RETURNING id AS chain \gset
INSERT INTO app.zone (chain_id, code, name) VALUES (:'chain', 'A', 'Khu A') RETURNING id AS zone_a \gset
INSERT INTO app.zone (chain_id, code, name) VALUES (:'chain', 'B', 'Khu B') RETURNING id AS zone_b \gset
INSERT INTO app.zone (chain_id, code, name) VALUES (:'chain', 'C', 'Khu C') RETURNING id AS zone_c \gset
SELECT set_config('app.zone_ids', format('{%s,%s,%s}', :'zone_a', :'zone_b', :'zone_c'), false) \gset ignored_

INSERT INTO app.subzone (zone_id, code, name) VALUES (:'zone_a', 'A-S1', 'Phân khu A1') RETURNING id AS sz_a \gset
INSERT INTO app.subzone (zone_id, code, name) VALUES (:'zone_b', 'B-S1', 'Phân khu B1') RETURNING id AS sz_b \gset
INSERT INTO app.subzone (zone_id, code, name) VALUES (:'zone_c', 'C-S1', 'Phân khu C1') RETURNING id AS sz_c \gset

INSERT INTO app.building (zone_id, subzone_id, code, name, kind) VALUES (:'zone_a', :'sz_a', 'A1', 'Tòa A1', 'residential_tower') RETURNING id AS bld_a1 \gset
INSERT INTO app.building (zone_id, subzone_id, code, name, kind) VALUES (:'zone_a', :'sz_a', 'ALR', 'Cụm shophouse A', 'lowrise_cluster') RETURNING id AS bld_alr \gset
INSERT INTO app.building (zone_id, subzone_id, code, name, kind) VALUES (:'zone_a', :'sz_a', 'APL', 'Bãi công cộng A', 'public_lot') RETURNING id AS bld_apl \gset
INSERT INTO app.building (zone_id, subzone_id, code, name, kind) VALUES (:'zone_b', :'sz_b', 'B1', 'Tòa B1', 'residential_tower') RETURNING id AS bld_b1 \gset
INSERT INTO app.building (zone_id, subzone_id, code, name, kind) VALUES (:'zone_c', :'sz_c', 'C1', 'Tòa C1', 'residential_tower') RETURNING id AS bld_c1 \gset
INSERT INTO app.building (zone_id, subzone_id, code, name, kind) VALUES (:'zone_c', :'sz_c', 'CPL', 'Bãi công cộng C', 'public_lot') RETURNING id AS bld_cpl \gset

INSERT INTO app.basement (zone_id, building_id, code) VALUES (:'zone_a', :'bld_a1', 'B2') RETURNING id AS bm_a1 \gset
INSERT INTO app.basement (zone_id, building_id, code) VALUES (:'zone_a', :'bld_apl', 'G') RETURNING id AS bm_apl \gset
INSERT INTO app.basement (zone_id, building_id, code) VALUES (:'zone_b', :'bld_b1', 'B1') RETURNING id AS bm_b1 \gset
INSERT INTO app.basement (zone_id, building_id, code) VALUES (:'zone_c', :'bld_c1', 'B1') RETURNING id AS bm_c1 \gset
INSERT INTO app.basement (zone_id, building_id, code) VALUES (:'zone_c', :'bld_cpl', 'G') RETURNING id AS bm_cpl \gset

INSERT INTO app.size_class (code, rank, label_vi, max_length_cm, max_width_cm) VALUES
  ('S', 10, 'Xe nhỏ (hatchback)', 400, 175),
  ('M', 20, 'Sedan / CUV', 480, 190),
  ('L', 30, 'SUV 7 chỗ', 520, 200),
  ('XL', 40, 'Bán tải / van', 560, 210);

INSERT INTO app.slot_pool (zone_id, building_id, slot_type, max_open_scope) VALUES (:'zone_a', :'bld_a1', 'TH1', 'building') RETURNING id AS pool_a1_th1 \gset
INSERT INTO app.slot_pool (zone_id, building_id, slot_type, max_open_scope, investor_consent_at) VALUES (:'zone_a', NULL, 'TH2', 'zone', now()) RETURNING id AS pool_a_th2 \gset
INSERT INTO app.slot_pool (zone_id, building_id, slot_type, max_open_scope) VALUES (:'zone_a', NULL, 'TH3', 'public') RETURNING id AS pool_a_th3 \gset
INSERT INTO app.slot_pool (zone_id, building_id, slot_type, max_open_scope) VALUES (:'zone_b', :'bld_b1', 'TH1', 'building') RETURNING id AS pool_b1_th1 \gset
INSERT INTO app.slot_pool (zone_id, building_id, slot_type, max_open_scope, investor_consent_at) VALUES (:'zone_c', NULL, 'TH2', 'chain', now()) RETURNING id AS pool_c_th2 \gset
INSERT INTO app.slot_pool (zone_id, building_id, slot_type, max_open_scope) VALUES (:'zone_c', NULL, 'TH3', 'public') RETURNING id AS pool_c_th3 \gset

INSERT INTO app.slot (zone_id, building_id, basement_id, pool_id, slot_type, code, size_class_code) VALUES (:'zone_a', :'bld_a1', :'bm_a1', :'pool_a1_th1', 'TH1', 'B2-045', 'M') RETURNING id AS s_045 \gset
INSERT INTO app.slot (zone_id, building_id, basement_id, pool_id, slot_type, code, size_class_code) VALUES (:'zone_a', :'bld_a1', :'bm_a1', :'pool_a1_th1', 'TH1', 'B2-046', 'S') RETURNING id AS s_046 \gset
INSERT INTO app.slot (zone_id, building_id, basement_id, pool_id, slot_type, code, size_class_code) VALUES (:'zone_a', :'bld_a1', :'bm_a1', :'pool_a_th2', 'TH2', 'B2-101', 'L') RETURNING id AS s_101 \gset
INSERT INTO app.slot (zone_id, building_id, basement_id, pool_id, slot_type, code, size_class_code) VALUES (:'zone_a', :'bld_apl', :'bm_apl', :'pool_a_th3', 'TH3', 'TH3-012', 'L') RETURNING id AS s_th3_a \gset
INSERT INTO app.slot (zone_id, building_id, basement_id, pool_id, slot_type, code, size_class_code) VALUES (:'zone_a', :'bld_apl', :'bm_apl', :'pool_a_th3', 'TH3', 'TH3-013', 'L') RETURNING id AS s_th3_a2 \gset
INSERT INTO app.slot (zone_id, building_id, basement_id, pool_id, slot_type, code, size_class_code) VALUES (:'zone_b', :'bld_b1', :'bm_b1', :'pool_b1_th1', 'TH1', 'B1-001', 'M') RETURNING id AS s_b1 \gset
INSERT INTO app.slot (zone_id, building_id, basement_id, pool_id, slot_type, code, size_class_code) VALUES (:'zone_c', :'bld_c1', :'bm_c1', :'pool_c_th2', 'TH2', 'B1-010', 'L') RETURNING id AS s_c010 \gset
INSERT INTO app.slot (zone_id, building_id, basement_id, pool_id, slot_type, code, size_class_code) VALUES (:'zone_c', :'bld_cpl', :'bm_cpl', :'pool_c_th3', 'TH3', 'TH3-001', 'L') RETURNING id AS s_th3_c \gset

INSERT INTO app.gate (zone_id, building_id, code) VALUES (:'zone_a', :'bld_a1', 'G1') RETURNING id AS gate_a1 \gset
INSERT INTO app.lpr_source (zone_id, kind, name, ocr_review_threshold) VALUES (:'zone_a', 'simulated', 'demo-weekday', 0.800) RETURNING id AS src_a \gset

-- Zone policies take every value from the column DEFAULTs, i.e. the researched defaults of 10-decision-log.md:
-- buffers 15/30 min, approval threshold 1 000 000 đ, hold 10 min, confirm 30 min, overstay grace 10 min,
-- overstay 50 000 đ/h, reminders every 15 min, BR-16 carry-over 7 days, swap needs party consent.
-- ALL ARE "default, confirm with BQL".
INSERT INTO app.zone_policy (zone_id, version, effective_from) VALUES (:'zone_a', 1, now() - interval '30 days') RETURNING id AS pol_a \gset
INSERT INTO app.zone_policy (zone_id, version, effective_from) VALUES (:'zone_c', 1, now() - interval '30 days') RETURNING id AS pol_c \gset
-- Prices (D-01), default, confirm with BQL. Anchors: PRD §8 (~50 000 đ/day for L1–L2, outside parking 20–70 000 đ/h);
-- Hanoi 2026 street parking 45 000 đ/60 min inside Ring 1 (VOV, 2026-10-18). The rule engine caps hourly sums at the
-- day price. L3 sits between members and guests (PRD §8).
INSERT INTO app.price_rule (zone_policy_id, slot_type, level, unit, price_vnd) VALUES
  (:'pol_a', 'TH1', 'L1', 'day', 50000), (:'pol_a', 'TH1', 'L1', 'hour', 10000),
  (:'pol_a', 'TH2', 'L1', 'day', 50000), (:'pol_a', 'TH2', 'L1', 'hour', 10000),
  (:'pol_a', 'TH2', 'L2', 'day', 50000), (:'pol_a', 'TH2', 'L2', 'hour', 10000),
  (:'pol_a', 'TH3', 'L1', 'hour', 20000), (:'pol_a', 'TH3', 'L2', 'hour', 20000), (:'pol_a', 'TH3', 'L3', 'hour', 20000),
  (:'pol_a', 'TH3', 'L4', 'hour', 30000),
  (:'pol_c', 'TH2', 'L1', 'day', 50000), (:'pol_c', 'TH2', 'L2', 'day', 50000),
  (:'pol_c', 'TH2', 'L3', 'day', 70000), (:'pol_c', 'TH2', 'L3', 'hour', 15000),
  (:'pol_c', 'TH3', 'L1', 'hour', 20000), (:'pol_c', 'TH3', 'L2', 'hour', 20000), (:'pol_c', 'TH3', 'L3', 'hour', 20000),
  (:'pol_c', 'TH3', 'L4', 'hour', 30000);
INSERT INTO app.agreement_template (zone_id, version, body_md, effective_from)
VALUES (:'zone_a', 1, '# Thỏa thuận chia sẻ chỗ đỗ (mẫu khu A)', now() - interval '30 days') RETURNING id AS tpl_a \gset
INSERT INTO app.agreement_template (zone_id, version, body_md, effective_from)
VALUES (:'zone_c', 1, '# Thỏa thuận chia sẻ chỗ đỗ (mẫu khu C)', now() - interval '30 days') RETURNING id AS tpl_c \gset
INSERT INTO app.dispute_category (code, label_vi) VALUES ('occupied_by_other', 'Xe khác đỗ vào chỗ của tôi'), ('other', 'Khác');
INSERT INTO app.holiday (chain_id, day, name) VALUES (:'chain', '2027-02-06', 'Tết Nguyên đán');

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
INSERT INTO app.consent (user_id, kind, text_version)
SELECT id, 'plate_photo_processing', 'v1' FROM app.app_user;

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

-- Plates: demo encryption with pgcrypto; the app uses AES-GCM with a KMS/SSM key (07-operations.md §3).
\set demo_key 'demo-plate-key'
\set pepper 'demo-plate-pepper'
INSERT INTO app.vehicle (user_id, plate_ciphertext, plate_hash, plate_masked, size_class_code)
SELECT u, pgp_sym_encrypt(p, :'demo_key'), hmac(p, :'pepper', 'sha256'), m, s
FROM (VALUES (:'u_lan'::uuid, '30A12345', '30A-•••.45', 'M'), (:'u_binh'::uuid, '30A22222', '30A-•••.22', 'M'),
             (:'u_binh'::uuid, '29C99999', '29C-•••.99', 'XL'), (:'u_minh'::uuid, '51G33333', '51G-•••.33', 'M'),
             (:'u_hoa'::uuid, '30E44444', '30E-•••.44', 'M'), (:'u_tuan'::uuid, '30F55555', '30F-•••.55', 'M'),
             (:'u_khach'::uuid, '29H66666', '29H-•••.66', 'M')) AS v(u, p, m, s);
SELECT id AS v_binh FROM app.vehicle WHERE user_id = :'u_binh' AND size_class_code = 'M' \gset
SELECT id AS v_binh_xl FROM app.vehicle WHERE user_id = :'u_binh' AND size_class_code = 'XL' \gset
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

INSERT INTO app.agreement (zone_id, booking_id, template_id, zone_policy_id, provider_user_id, renter_user_id, price_vnd,
                           body_rendered, body_sha256, status, requires_approval, confirm_deadline,
                           provider_confirmed_at, renter_confirmed_at, effective_at)
VALUES (:'zone_a', :'bk_binh', :'tpl_a', :'pol_a', :'u_lan', :'u_binh', 40000, 'Thỏa thuận GD-1 …',
        sha256(convert_to('Thỏa thuận GD-1 …', 'UTF8')), 'effective', false, now() + interval '30 min', now(), now(), now())
RETURNING id AS ag_binh \gset
UPDATE app.booking SET status = 'confirmed' WHERE id = :'bk_binh';
SELECT seq AS led1 FROM app.ledger_append(:'zone_a', 'agreement_effective', 'agreement', :'ag_binh',
       jsonb_build_object('booking_id', :'bk_binh', 'price_vnd', 40000), 'thread-binh:w2.ledger') \gset

-- Hoa's 21-day L3 rental (1 470 000 đ) is above the default threshold of 1 000 000 đ → HITL (AC-15, D-08).
INSERT INTO app.approval_request (zone_id, kind, subject_id, thread_id, summary)
VALUES (:'zone_c', 'agreement_over_threshold', app.uuid_v7(), 'thread-hoa', 'GD vượt ngưỡng') RETURNING id AS appr_hoa, subject_id AS appr_hoa_subject \gset
INSERT INTO app.agreement (id, zone_id, booking_id, template_id, zone_policy_id, provider_user_id, renter_user_id, price_vnd,
                           body_rendered, body_sha256, status, requires_approval, approval_request_id, confirm_deadline,
                           provider_confirmed_at, renter_confirmed_at)
VALUES (:'appr_hoa_subject', :'zone_c', :'bk_hoa', :'tpl_c', :'pol_c', :'u_van', :'u_hoa', 1470000, 'Thỏa thuận GD-2 …',
        sha256(convert_to('Thỏa thuận GD-2 …', 'UTF8')), 'pending_approval', true, :'appr_hoa', now() + interval '30 min', now(), now());

INSERT INTO app.voucher (zone_id, issuer_user_id, issuer_asset_id, code, value_vnd, valid_until, idempotency_key)
VALUES (:'zone_a', :'u_minh', :'a_shop', 'VC7K-Q2MX-81ZD', 20000, now() + interval '7 days', 'voucher-minh-1') RETURNING id AS vc1 \gset
INSERT INTO app.payment (zone_id, booking_id, payer_user_id, kind, gross_vnd, discount_vnd, voucher_id, status, paid_at, idempotency_key)
VALUES (:'zone_a', :'bk_khach', :'u_khach', 'th3_visit', 60000, 20000, :'vc1', 'paid_simulated', now(), 'pay-khach-1');
UPDATE app.voucher SET status = 'redeemed', redeemed_at = now() WHERE id = :'vc1';
INSERT INTO app.payment (zone_id, booking_id, payer_user_id, kind, gross_vnd, idempotency_key)
VALUES (:'zone_a', :'bk_binh', :'u_binh', 'share_booking', 40000, 'pay-binh-1');

\echo '== 4. Seed: LPR, dispute, swap, notifications, KPI'
INSERT INTO app.lpr_event (zone_id, source_id, source_event_id, gate_id, direction, occurred_at,
                           plate_ciphertext, plate_hash, plate_masked, ocr_confidence, status, matched_vehicle_id)
VALUES (:'zone_a', :'src_a', 'EV-88419', :'gate_a1', 'in', now() - interval '1 hour',
        pgp_sym_encrypt('30A22222', :'demo_key'), hmac('30A22222', :'pepper', 'sha256'), '30A-•••.22', 0.960, 'accepted', :'v_binh')
RETURNING id AS ev1, occurred_at AS ev1_at \gset
INSERT INTO app.lpr_event (zone_id, source_id, source_event_id, gate_id, direction, occurred_at,
                           plate_ciphertext, plate_hash, plate_masked, ocr_confidence, status)
VALUES (:'zone_a', :'src_a', 'EV-88421', :'gate_a1', 'in', now() - interval '50 min',
        pgp_sym_encrypt('30A12845', :'demo_key'), hmac('30A12845', :'pepper', 'sha256'), '30A-•••.45', 0.540, 'pending_review');
INSERT INTO app.parking_session (zone_id, booking_id, vehicle_id, entry_event_id, entered_at)
VALUES (:'zone_a', :'bk_binh', :'v_binh', :'ev1', :'ev1_at');

INSERT INTO app.dispute_ticket (zone_id, slot_id, booking_id, source, category_code, description, status, ai_summary, ai_confidence, idempotency_key)
VALUES (:'zone_a', :'s_045', :'bk_binh', 'app', 'occupied_by_other', 'Xe lạ đỗ vào chỗ', 'awaiting_verification',
        'NT-7 có giao dịch hiệu lực; xe trong ảnh không khớp (gợi ý).', 0.720, 'thread-dispute-1:w5.ticket')
RETURNING id AS tk1 \gset
INSERT INTO app.dispute_party (ticket_id, zone_id, user_id, role) VALUES (:'tk1', :'zone_a', :'u_lan', 'reporter'), (:'tk1', :'zone_a', :'u_binh', 'respondent');
INSERT INTO app.dispute_evidence (zone_id, ticket_id, kind, object_key_original, object_key_masked, sha256)
VALUES (:'zone_a', :'tk1', 'photo', 'zone-a/disputes/tk1/orig.jpg', 'zone-a/disputes/tk1/masked.jpg', sha256('photo'::bytea));
INSERT INTO app.dispute_evidence (zone_id, ticket_id, kind, ledger_seq) VALUES (:'zone_a', :'tk1', 'ledger_entry', :'led1');

-- Two-party swap in zone A (W6): lan's narrow TH1 B2-046 ↔ binh's wide TH2 B2-101, approved then applied.
INSERT INTO app.approval_request (zone_id, kind, subject_id, thread_id, status, decided_by, decided_at)
VALUES (:'zone_a', 'swap', app.uuid_v7(), 'thread-swap-1', 'approved', :'u_bql_a', now()) RETURNING id AS appr_swap, subject_id AS sw1 \gset
INSERT INTO app.swap_proposal (id, zone_id, kind, status, reason, score, approval_request_id, effective_from, idempotency_key)
VALUES (:'sw1', :'zone_a', 'two_party', 'pending_approval', 'Xe SUV ở ô hẹp', 0.910, :'appr_swap', now(), 'thread-swap-1:w6.propose');
INSERT INTO app.swap_leg (proposal_id, zone_id, slot_id, from_user_id, to_user_id, ordinal, accepted_at) VALUES
  (:'sw1', :'zone_a', :'s_046', :'u_lan', :'u_binh', 1, now()), (:'sw1', :'zone_a', :'s_101', :'u_binh', :'u_lan', 2, now());
UPDATE app.swap_proposal SET status = 'approved' WHERE id = :'sw1';   -- both parties accepted (D-10)
-- Apply: close current holdings, open swap_usage holdings, mark applied, ledger — one transaction (05-concurrency §6).
BEGIN;
UPDATE app.slot_holding SET held_during = tstzrange(lower(held_during), now())
 WHERE slot_id IN (:'s_046', :'s_101') AND upper_inf(held_during);
INSERT INTO app.slot_holding (zone_id, slot_id, slot_type, user_id, kind, held_during, swap_proposal_id) VALUES
  (:'zone_a', :'s_046', 'TH1', :'u_binh', 'swap_usage', tstzrange(now(), NULL), :'sw1'),
  (:'zone_a', :'s_101', 'TH2', :'u_lan',  'swap_usage', tstzrange(now(), NULL), :'sw1');
UPDATE app.swap_proposal SET status = 'applied', applied_at = now() WHERE id = :'sw1';
SELECT 1 AS ok FROM app.ledger_append(:'zone_a', 'swap_applied', 'swap_proposal', :'sw1', jsonb_build_object('legs', 2), 'thread-swap-1:w6.ledger') \gset ignored_
COMMIT;

INSERT INTO app.notification (user_id, zone_id, kind, title, body, link, idempotency_key)
VALUES (:'u_binh', :'zone_a', 'agreement_pending', 'Có thỏa thuận chờ bạn xác nhận', 'Chỗ B2-045',
        jsonb_build_object('type', 'agreement', 'id', :'ag_binh'), 'outbox:1');
INSERT INTO app.outbox (event_type, zone_id, payload) VALUES ('AgreementEffective', :'zone_a', jsonb_build_object('agreement_id', :'ag_binh'));
INSERT INTO app.kpi_daily (zone_id, day, metric, value) VALUES
  (:'zone_a', current_date - 1, 'blocked_ineligible_tx', 1), (:'zone_c', current_date - 1, 'match_rate', 0.82);

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
  INSERT INTO app.lpr_event (zone_id, source_id, source_event_id, gate_id, direction, occurred_at, ocr_confidence, status)
  VALUES (:'zone_a', :'src_a', 'EV-88419', :'gate_a1', 'in', :'ev1_at', 0.960, 'accepted')
  ON CONFLICT (source_id, source_event_id, occurred_at) DO NOTHING RETURNING 1)
SELECT pg_temp.expect('LPR duplicate is ignored with ON CONFLICT DO NOTHING (AC-10a)', count(*) = 0) FROM ins;
SELECT pg_temp.expect('swap applied: binh now uses B2-046, lan uses B2-101',
  EXISTS (SELECT 1 FROM app.slot_holding WHERE slot_id = :'s_046' AND user_id = :'u_binh' AND held_during @> now())
  AND EXISTS (SELECT 1 FROM app.slot_holding WHERE slot_id = :'s_101' AND user_id = :'u_lan' AND held_during @> now()));
SELECT pg_temp.expect('audit log captured eligibility inserts', (SELECT count(*) FROM app.audit_log WHERE table_name = 'eligibility') >= 7);

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
SELECT pg_temp.expect_fail('plate access log DELETE (append-only)', 'DELETE FROM app.plate_access_log', '42501');

-- Money, vouchers, payments
SELECT pg_temp.expect_fail('AC-16 voucher on a TH1 share booking', format(
  $$INSERT INTO app.payment (zone_id, booking_id, payer_user_id, kind, gross_vnd, discount_vnd, voucher_id, idempotency_key)
    VALUES (%L, %L, %L, 'share_booking', 50000, 1000, %L, 'p2')$$, :'zone_a', :'bk_binh', :'u_binh', :'vc1'), '23514', 'AC-16');
SELECT pg_temp.expect_fail('discount larger than amount', format(
  $$INSERT INTO app.payment (zone_id, booking_id, payer_user_id, kind, gross_vnd, discount_vnd, idempotency_key)
    VALUES (%L, %L, %L, 'th3_visit', 1000, 2000, 'p3')$$, :'zone_a', :'bk_khach', :'u_khach'), '23514');
SELECT pg_temp.expect_fail('discount without a voucher', format(
  $$INSERT INTO app.payment (zone_id, booking_id, payer_user_id, kind, gross_vnd, discount_vnd, idempotency_key)
    VALUES (%L, %L, %L, 'th3_visit', 5000, 1000, 'p4')$$, :'zone_a', :'bk_khach', :'u_khach'), '23514');
SELECT pg_temp.expect_fail('voucher redeemed twice', format(
  $$INSERT INTO app.payment (zone_id, booking_id, payer_user_id, kind, gross_vnd, discount_vnd, voucher_id, idempotency_key)
    VALUES (%L, %L, %L, 'th3_visit', 50000, 20000, %L, 'p5')$$, :'zone_a', :'bk_khach', :'u_khach', :'vc1'), '23505');
SELECT pg_temp.expect_fail('A-05 real payment provider', format(
  $$INSERT INTO app.payment (zone_id, booking_id, payer_user_id, kind, gross_vnd, provider, idempotency_key)
    VALUES (%L, %L, %L, 'share_booking', 50000, 'momo', 'p6')$$, :'zone_a', :'bk_binh', :'u_binh'), '23514');
SELECT pg_temp.expect_fail('second successful payment for one booking', format(
  $$INSERT INTO app.payment (zone_id, booking_id, payer_user_id, kind, gross_vnd, status, paid_at, idempotency_key)
    VALUES (%L, %L, %L, 'th3_visit', 50000, 'paid_simulated', now(), 'p7')$$, :'zone_a', :'bk_khach', :'u_khach'), '23505');

-- LPR, disputes, swaps, identity
SELECT pg_temp.expect_fail('LPR duplicate event id (plain INSERT)', format(
  $$INSERT INTO app.lpr_event (zone_id, source_id, source_event_id, gate_id, direction, occurred_at, ocr_confidence, status)
    VALUES (%L, %L, 'EV-88419', %L, 'in', %L, 0.9, 'accepted')$$, :'zone_a', :'src_a', :'gate_a1', :'ev1_at'), '23505');
SELECT pg_temp.expect_fail('OCR confidence above 1', format(
  $$INSERT INTO app.lpr_event (zone_id, source_id, source_event_id, gate_id, direction, occurred_at, ocr_confidence, status)
    VALUES (%L, %L, 'EV-1', %L, 'in', now(), 1.5, 'accepted')$$, :'zone_a', :'src_a', :'gate_a1'), '23514');
SELECT pg_temp.expect_fail('manual OCR confirmation without reviewer', format(
  $$INSERT INTO app.lpr_event (zone_id, source_id, source_event_id, gate_id, direction, occurred_at, ocr_confidence, status)
    VALUES (%L, %L, 'EV-2', %L, 'in', now(), 0.5, 'confirmed_manual')$$, :'zone_a', :'src_a', :'gate_a1'), '23514');
SELECT pg_temp.expect_fail('dispute resolved without resolver', format(
  $$UPDATE app.dispute_ticket SET status = 'resolved' WHERE id = %L$$, :'tk1'), '23514');
SELECT pg_temp.expect_fail('BR-10 swap leg with a slot of another zone', format(
  $$INSERT INTO app.swap_leg (proposal_id, zone_id, slot_id, from_user_id, to_user_id, ordinal) VALUES (%L, %L, %L, %L, %L, 3)$$,
  :'sw1', :'zone_a', :'s_c010', :'u_van', :'u_lan'), '23503');
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
SELECT pg_temp.expect_fail('BQL C cannot reveal a zone-A plate', format($$SELECT app.reveal_lpr_plate(%s, %L, 'checking dispute')$$, :'ev1', :'ev1_at'), '42501');
SELECT pg_temp.expect_fail('BQL C cannot write zone-A config (RLS WITH CHECK)', format(
  $$INSERT INTO app.zone_policy (zone_id, version, effective_from, buffer_before, buffer_after, approval_threshold_vnd, hold_ttl,
      agreement_confirm_ttl, overstay_grace, overstay_fee_per_hour_vnd) VALUES (%L, 2, now(), '0', '0', 0, '1 min', '1 min', '0', 0)$$, :'zone_a'), '42501');
COMMIT;

-- BQL of zone A: may reveal a plate, and the read is logged.
BEGIN;
SET LOCAL ROLE parksmart_app;
SELECT set_config('app.role', 'zone_manager', true), set_config('app.user_id', :'u_bql_a', true),
       set_config('app.zone_ids', format('{%s}', :'zone_a'), true) \gset ignored_
SELECT pg_temp.expect('AC-12 BQL A reveals a plate', convert_from(pgp_sym_decrypt_bytea(
         app.reveal_lpr_plate(:'ev1', :'ev1_at', 'Xác minh ticket TC-1'), :'demo_key'), 'UTF8') = '30A22222');
SELECT pg_temp.expect('AC-12 the reveal is in plate_access_log', (SELECT count(*) FROM app.plate_access_log WHERE viewer_user_id = :'u_bql_a') = 1);
SELECT pg_temp.expect_fail('plate ciphertext is not selectable directly', 'SELECT plate_ciphertext FROM app.vehicle', '42501');
SELECT pg_temp.expect_fail('original dispute photo key is not selectable directly', 'SELECT object_key_original FROM app.dispute_evidence', '42501');
SELECT pg_temp.expect_fail('reveal without a reason', format($$SELECT app.reveal_lpr_plate(%s, %L, '')$$, :'ev1', :'ev1_at'), '23514');
SELECT pg_temp.expect('ledger zone A verifies under BQL A', app.ledger_verify(:'zone_a') IS NULL);
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
SELECT pg_temp.expect('resident sees no KPI rows', (SELECT count(*) FROM app.kpi_daily) = 0);
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
SELECT pg_temp.expect('chain operator reads KPI of every zone', (SELECT count(DISTINCT zone_id) FROM app.kpi_daily) = 2);
SELECT pg_temp.expect('chain operator reads no bookings', (SELECT count(*) FROM app.booking) = 0);
SELECT pg_temp.expect('chain operator reads no eligibility', (SELECT count(*) FROM app.eligibility) = 0);
COMMIT;

-- No context at all (a forgotten SET LOCAL): nothing private is visible.
BEGIN;
SET LOCAL ROLE parksmart_app;
SELECT set_config('app.role', '', true), set_config('app.user_id', '', true), set_config('app.zone_ids', '', true) \gset ignored_
SELECT pg_temp.expect('no context → no bookings, users, slots', (SELECT count(*) FROM app.booking) + (SELECT count(*) FROM app.app_user)
                                                              + (SELECT count(*) FROM app.slot) = 0);
COMMIT;

-- =====================================================================================================
\echo '== 9. v2 checks: defaults, early-return settlement, rebooking, SET NULL, idempotency, consent, erasure, retention, agent schema'
-- Session context is back to role=system, all zones (set at the top).

-- 9.1 Researched defaults landed in the policy rows (D-02/03/04/08/16).
SELECT pg_temp.expect('zone policy carries the researched defaults', (
  SELECT buffer_before = '15 min' AND buffer_after = '30 min' AND approval_threshold_vnd = 1000000
     AND hold_ttl = '10 min' AND agreement_confirm_ttl = '30 min' AND overstay_grace = '10 min'
     AND overstay_fee_per_hour_vnd = 50000 AND overstay_reminder_every = '15 min'
     AND eligibility_grace_max = '7 days' AND swap_requires_party_consent
     AND early_return_cost_rule = 'renter_pays_th3_relocated'
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
INSERT INTO app.payment (zone_id, booking_id, payer_user_id, kind, gross_vnd, idempotency_key)
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
INSERT INTO app.vehicle (user_id, plate_ciphertext, plate_hash, plate_masked, size_class_code)
VALUES (:'u_tmp', '\x01', hmac('99X99999', :'pepper', 'sha256'), '99X-•••.99', 'M') RETURNING id AS v_tmp \gset
INSERT INTO app.zone_policy (zone_id, version, effective_from, created_by) VALUES (:'zone_b', 1, now(), :'u_tmp');
INSERT INTO app.workflow_run (thread_id, workflow, initiator_user_id) VALUES ('thread-tmp', 'W0', :'u_tmp');
INSERT INTO app.lpr_event (zone_id, source_id, source_event_id, gate_id, direction, occurred_at, ocr_confidence, status, matched_vehicle_id)
VALUES (:'zone_a', :'src_a', 'EV-SETNULL', :'gate_a1', 'in', now() - interval '10 min', 0.95, 'accepted', :'v_tmp');
DELETE FROM app.vehicle WHERE id = :'v_tmp';
DELETE FROM app.app_user WHERE id = :'u_tmp';
SELECT pg_temp.expect('(c) SET NULL applied on lpr_event, zone_policy, workflow_run',
  (SELECT matched_vehicle_id IS NULL FROM app.lpr_event WHERE source_event_id = 'EV-SETNULL')
  AND (SELECT created_by IS NULL FROM app.zone_policy WHERE zone_id = :'zone_b')
  AND (SELECT initiator_user_id IS NULL FROM app.workflow_run WHERE thread_id = 'thread-tmp'));
INSERT INTO app.app_user (full_name, phone_e164, password_hash, role) VALUES ('Bảo vệ tạm', '+84909990002', :'pw', 'guard') RETURNING id AS u_rev \gset
INSERT INTO app.lpr_event (zone_id, source_id, source_event_id, gate_id, direction, occurred_at, ocr_confidence, status, reviewed_by, reviewed_at)
VALUES (:'zone_a', :'src_a', 'EV-REVIEWED', :'gate_a1', 'in', now() - interval '5 min', 0.50, 'confirmed_manual', :'u_rev', now());
SELECT pg_temp.expect_fail('(c) reviewer of a reviewed LPR event cannot be deleted (RESTRICT, not a CHECK failure)', format(
  $$DELETE FROM app.app_user WHERE id = %L$$, :'u_rev'), '23503');

-- 9.5 Check (d): idempotency keys on the new write targets.
SELECT pg_temp.expect_fail('(d) replayed share-window publish', format(
  $$INSERT INTO app.share_window (zone_id, slot_id, owner_user_id, period, bookable_period, open_scope, idempotency_key)
    VALUES (%L, %L, %L, tstzrange(now() + interval '9 days', now() + interval '9 days 2 hours'),
            tstzrange(now() + interval '9 days', now() + interval '9 days 2 hours'), 'building', 'thread-lan:w2.publish')$$,
  :'zone_a', :'s_045', :'u_lan'), '23505');
SELECT pg_temp.expect_fail('(d) replayed voucher creation', format(
  $$INSERT INTO app.voucher (zone_id, issuer_user_id, issuer_asset_id, code, value_vnd, valid_until, idempotency_key)
    VALUES (%L, %L, %L, 'ZZZZ-ZZZZ-ZZZZ', 20000, now() + interval '7 days', 'voucher-minh-1')$$, :'zone_a', :'u_minh', :'a_shop'), '23505');
SELECT pg_temp.expect_fail('(d) the same photo attached twice to a ticket', format(
  $$INSERT INTO app.dispute_evidence (zone_id, ticket_id, kind, object_key_original, object_key_masked, sha256)
    VALUES (%L, %L, 'photo', 'k2', 'k2m', sha256('photo'::bytea))$$, :'zone_a', :'tk1'), '23505');
SELECT pg_temp.expect_fail('D-05 LPR evidence without a snapshot', format(
  $$INSERT INTO app.dispute_evidence (zone_id, ticket_id, kind, lpr_event_id, lpr_occurred_at) VALUES (%L, %L, 'lpr_event', %s, %L)$$,
  :'zone_a', :'tk1', :'ev1', :'ev1_at'), '23514');

-- 9.6 D-10: swap parties must accept before approval.
INSERT INTO app.swap_proposal (zone_id, kind, reason, idempotency_key) VALUES (:'zone_a', 'two_party', 'thử nghiệm', 'thread-swap-2:w6.propose')
RETURNING id AS sw2 \gset
INSERT INTO app.swap_leg (proposal_id, zone_id, slot_id, from_user_id, to_user_id, ordinal) VALUES
  (:'sw2', :'zone_a', :'s_045', :'u_lan', :'u_binh', 1), (:'sw2', :'zone_a', :'s_046', :'u_binh', :'u_lan', 2);
INSERT INTO app.approval_request (zone_id, kind, subject_id, thread_id, status, decided_by, decided_at)
VALUES (:'zone_a', 'swap', :'sw2', 'thread-swap-2', 'approved', :'u_bql_a', now()) RETURNING id AS appr_sw2 \gset
SELECT pg_temp.expect_fail('D-10 approve a swap a party has not accepted', format(
  $$UPDATE app.swap_proposal SET status = 'approved', approval_request_id = %L WHERE id = %L$$, :'appr_sw2', :'sw2'), '23514', 'D-10');

-- 9.7 D-14 / D-15: erasure keeps ids, removes personal data; requests carry legal deadlines.
INSERT INTO app.app_user (full_name, phone_e164, email, password_hash) VALUES ('Ngô Erin', '+84909990003', 'erin@example.com', :'pw') RETURNING id AS u_erin \gset
INSERT INTO app.vehicle (user_id, plate_ciphertext, plate_hash, plate_masked, size_class_code)
VALUES (:'u_erin', pgp_sym_encrypt('30K77777', :'demo_key'), hmac('30K77777', :'pepper', 'sha256'), '30K-•••.77', 'M');
INSERT INTO app.consent (user_id, kind, text_version) VALUES (:'u_erin', 'plate_photo_processing', 'v1');
INSERT INTO app.privacy_request (user_id, kind, due_at) VALUES (:'u_erin', 'delete', now() + interval '20 days') RETURNING id AS pr_erin \gset
SELECT pg_temp.expect_fail('D-15 second open delete request for the same user', format(
  $$INSERT INTO app.privacy_request (user_id, kind, due_at) VALUES (%L, 'delete', now() + interval '20 days')$$, :'u_erin'), '23505');
SELECT pg_temp.expect_fail('D-15 deadline beyond 60 days', format(
  $$INSERT INTO app.privacy_request (user_id, kind, due_at) VALUES (%L, 'access', now() + interval '90 days')$$, :'u_erin'), '23514');
INSERT INTO app.privacy_request (user_id, kind, due_at) VALUES (:'u_khach', 'delete', now() + interval '20 days') RETURNING id AS pr_khach \gset
SELECT pg_temp.expect_fail('D-14 erase a user with live bookings', format(
  $$SELECT app.erase_user(%L, %L)$$, :'u_khach', :'pr_khach'), '23514', 'live bookings');
SELECT app.erase_user(:'u_erin', :'pr_erin') \gset ignored_
SELECT pg_temp.expect('D-14 erased user: no name, phone, email, plate; request completed', (
  SELECT u.full_name = '[đã xóa]' AND u.phone_e164 IS NULL AND u.email IS NULL AND u.status = 'deleted'
     AND v.plate_ciphertext IS NULL AND v.plate_hash IS NULL AND NOT v.is_active
     AND r.status = 'completed' AND r.completed_at <= r.due_at
  FROM app.app_user u JOIN app.vehicle v ON v.user_id = u.id JOIN app.privacy_request r ON r.user_id = u.id
  WHERE u.id = :'u_erin'));
SELECT pg_temp.expect_fail('D-14 active vehicle without a plate', format(
  $$INSERT INTO app.vehicle (user_id, plate_masked, size_class_code) VALUES (%L, 'x', 'M')$$, :'u_binh'), '23514');
SELECT pg_temp.expect_fail('D-14 live account without a phone', $$INSERT INTO app.app_user (full_name, password_hash) VALUES ('No Phone', '$argon2id$x')$$, '23514');

-- 9.8 D-05 / D-06: retention purge and LPR partition drop.
INSERT INTO app.notification (user_id, kind, title, body, idempotency_key, created_at)
VALUES (:'u_binh', 'old', 't', 'b', 'old-notif', now() - interval '200 days');
INSERT INTO app.audit_log (actor_role, table_name, row_id, action, at) VALUES ('system', 'x', 'x', 'INSERT', now() - interval '6 years');
INSERT INTO app.plate_access_log (viewer_user_id, subject_type, subject_ref, reason, viewed_at)
VALUES (:'u_bql_a', 'vehicle', 'x', 'old audit', now() - interval '6 years');
SELECT pg_temp.expect_fail('D-06 audit_log still append-only outside the purge job',
  $$DELETE FROM app.audit_log WHERE at < now() - interval '5 years'$$, '42501');
CREATE TEMP TABLE purge_result AS SELECT * FROM app.purge_expired();
SELECT pg_temp.expect('D-06 purge removed the expired rows only',
  (SELECT deleted FROM purge_result WHERE data_class = 'notification') = 1
  AND (SELECT deleted FROM purge_result WHERE data_class = 'audit_log') = 1
  AND (SELECT deleted FROM purge_result WHERE data_class = 'plate_access_log') = 1
  AND (SELECT count(*) FROM app.audit_log) > 0 AND (SELECT count(*) FROM app.plate_access_log) > 0);
CREATE TABLE app.lpr_event_202501 PARTITION OF app.lpr_event FOR VALUES FROM ('2025-01-01 00:00:00+00') TO ('2025-02-01 00:00:00+00');
INSERT INTO app.lpr_event (zone_id, source_id, source_event_id, gate_id, direction, occurred_at, ocr_confidence, status)
VALUES (:'zone_a', :'src_a', 'EV-OLD', :'gate_a1', 'in', '2025-01-15 08:00+07', 0.95, 'accepted');
CREATE TEMP TABLE dropped AS SELECT * FROM app.drop_expired_lpr_partitions() AS part;
SELECT pg_temp.expect('D-05 partition older than 90 days dropped, current partitions kept',
  (SELECT count(*) FROM dropped WHERE part = 'app.lpr_event_202501') = 1
  AND (SELECT count(*) FROM app.lpr_event WHERE source_event_id = 'EV-88419') = 1);

-- 9.9 Check (b) / D-12: schema agent is isolated from the app role, and the checkpointer from schema app.
-- The real tables come from langgraph-checkpoint-postgres; this mock has the same key column (thread_id).
GRANT USAGE, CREATE ON SCHEMA agent TO parksmart_checkpointer;
DO $$ BEGIN EXECUTE format('GRANT USAGE ON SCHEMA %I TO parksmart_checkpointer', pg_my_temp_schema()::regnamespace); END $$;
GRANT EXECUTE ON FUNCTION pg_temp.expect(text, boolean), pg_temp.expect_fail(text, text, text, text) TO parksmart_checkpointer;
SET ROLE parksmart_checkpointer;
CREATE TABLE agent.checkpoints (thread_id text NOT NULL, checkpoint_id text NOT NULL, checkpoint jsonb, PRIMARY KEY (thread_id, checkpoint_id));
INSERT INTO agent.checkpoints VALUES ('thread-done', 'c1', '{}'), ('thread-live', 'c1', '{}');
RESET ROLE;
INSERT INTO app.workflow_run (thread_id, workflow, status, finished_at) VALUES
  ('thread-done', 'W2', 'completed', now() - interval '40 days'), ('thread-live', 'W2', 'waiting_approval', NULL);
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
SELECT app.purge_agent_checkpoints() AS purged \gset
-- separate statement: a sub-select in the same statement would still see the pre-DELETE snapshot
SELECT pg_temp.expect('D-12 purge removes finished threads older than 30 days, keeps waiting ones',
  :purged = 1 AND (SELECT array_agg(thread_id) FROM agent.checkpoints) = ARRAY['thread-live']);

\echo '== done: all assertions passed'
