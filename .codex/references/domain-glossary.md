# Domain glossary (Vietnamese ↔ English)

Use the Vietnamese term in user-facing text and the English identifier in code.

| Vietnamese | English / code identifier | Meaning |
|------------|---------------------------|---------|
| Chuỗi | `chain` | Chain of urban areas run by one operator (developer) |
| Khu (khu đô thị) | `zone` / `zone_id` | One urban area; unit of data ownership, RLS and HITL approval |
| Phân khu, Tòa, Hầm, Ô | `subzone`, `building`, `basement`, `slot` | Facility hierarchy: Chain → Zone → Subzone → Building → Basement → Slot |
| BQL (Ban quản lý khu) | `zone_manager` / BQL | Zone management board: operates TH3, verifies eligibility, approves HITL |
| Đơn vị vận hành chuỗi | `chain_operator` | Configures chain-wide pricing, TH2 pool scope, chain reports |
| Ban quản trị tòa | `building_board` | Building rules, including TH1 open scope |
| Tư cách | `eligibility` | A (asset, role, expiry) entitlement of a person |
| Cấp tư cách L1–L4 | `EligibilityLevel.L1…L4` | Level at the slot's location: L1 building member, L2 zone member, L3 chain member (other zone), L4 guest (no valid eligibility) |
| Phạm vi mở | `open_scope` (`building` / `zone` / `chain`) | Who may rent a slot: building = L1, zone = L1–L2, chain = L1–L3 |
| TH1 | `SlotType.TH1` | Slot bought by a resident; rentable within open scope (BR-01) |
| TH2 | `SlotType.TH2` | Slot leased from the developer; pool sub-letting with one-time consent (BR-02) |
| TH3 | `SlotType.TH3` | Zone-operated public slot; individuals cannot share it (BR-03) |
| Bên cung cấp / bên cần chỗ | `provider` / `seeker` | Slot owner sharing vs person needing a slot |
| Chia sẻ chỗ | `share` / `sharing` | Owner publishes free time windows (M4, W2) |
| Đặt chỗ, giữ chỗ tạm | `booking`, `hold` | Request and temporary hold of a slot (M5, W1) |
| Khoảng dự phòng | `buffer` | Safety margin around a time window |
| Thỏa thuận | `agreement` | Contract from the zone template, confirmed by OTP (M6) |
| Sổ cái | `ledger` | Append-only, hash-chained transaction log (M6) |
| Thanh toán, VietQR | `payment` (mock) | Simulated QR payment (M7) |
| Về sớm | `early_return` | Owner returns early → W3 gives renter a TH3 replacement (BR-07) |
| Đỗ quá giờ | `overstay` | W4, fee per zone rules (BR-08) |
| Tranh chấp | `dispute` | W5, handled by BQL of the slot's zone (BR-18), plates masked (BR-09) |
| Hoán đổi | `swap` | W6, same zone only, BQL approval (BR-10) |
| LPR | `lpr` | Licence-plate recognition events; dedupe by event id (BR-13) |
| Duyệt (HITL) | `approval` | Human approval by BQL for over-threshold or sensitive actions (BR-12) |
| Mã giả | `pseudonym` | Placeholder for names/plates before LLM calls (BR-14) |
| Nội quy | `rules` / `policy` | Building/zone rules; rule engine in `policy/domain` |

IDs used in docs: **BR-xx** business rules (`docs/01-product/prd.md`), **US-xx** user stories,
**AC-xx** acceptance criteria, **M1–M14** modules, **W0–W7** agent workflows, **N1–N8** background jobs.
