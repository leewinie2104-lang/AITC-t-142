# 08 — Bảng hoãn lại (v2 → v3 → v4 → v5 MVP)

> **v7, 2026-11-22.** MVP = **26 bảng** (thêm `bql_registry_import`, plan 024). **v5, 2026-11-19:** 25 bảng ([D-33](07-db-decision-log.md#d-33), [D-32](07-db-decision-log.md#d-32), [ADR-0011](../07-adr/ADR-0011-mvp-simplifications.md)).
> **34 bảng hoãn:** 26 bảng v2 bỏ ở v3 ([D-31](07-db-decision-log.md#0-quyết-định-phạm-vi-mvp-d-31), nhóm a–c) + 8 bảng bỏ ở v4 (nhóm d). v4 liệt kê 38 bảng; 4 bảng tranh chấp của v2 (`dispute_category`, `dispute_ticket`, `dispute_party`, `dispute_evidence`) không còn hoãn: v5 thay bằng 2 bảng `dispute_case` + `dispute_evidence` (thiết kế DBML thay thế, đã nhận).
> `workflow_run` và `consent` có bảng kế nhiệm thiết kế khác ở v4 (`agent_thread`, `consent_record`).
> DDL, test, từ điển, ERD v2: `git show 333b85b:docs/database/02-schema.sql` (và các file cùng commit).
> Các tính năng dùng những bảng này thuộc **Ưu tiên 3 — chỉ làm nếu còn thời gian** ([backlog §6](../01-product/05-backlog.md#6-mức-3--nếu-còn-thời-gian)).

**Loại migration.** *Chỉ bảng mới*: một revision Alembic (+ RLS, quyền, trigger chép từ v2). *Bảng mới + backfill*: tạo bảng, chép dữ liệu
từ cột đã gộp, xóa cột sau. **Thứ tự:** theo nhóm; nhóm (c) trước khi có dữ liệu thật; trong (b), `plate_access_log` trước.

## (a) Chất lượng dữ liệu và cấu hình (bảng v2 số 28–39)

Bảng nhỏ chỉ để chuẩn hóa; ở v3 là cột, enum hoặc JSON. Đưa lại khi cột gộp gây phiền thật (gõ sai mã, cấu hình cần phiên bản hoặc truy vấn).

| Bảng bỏ | Giải quyết gì | Phục vụ | Thay bằng | Migration |
|---------|---------------|---------|-----------|-----------|
| `consent` | Lịch sử đồng ý / rút đồng ý theo loại | A-03, PDPL | **v4:** `consent_record` (chỉ ghi thêm, `accepted`/`rejected`/`withdrawn`) | Phần lớn đã có; chỉ khôi phục nếu cần danh mục riêng theo loại |
| `knowledge_doc` | Một dòng mỗi tài liệu nguồn | W7 RAG | `knowledge_chunk.doc_title`, `source_uri`, `doc_version`, `is_active` | Bảng mới + backfill theo `(source_uri, doc_version)`, thêm FK, bỏ cột |
| `workflow_run` | Bản ghi mỗi lần chạy workflow | ADR-0010 HITL | **v4:** `agent_thread` + `ai_decision_log` | Chỉ cần nếu muốn số liệu theo lần chạy |
| `kpi_daily` | KPI ngày đã materialise, gồm cả tranh chấp, hoán đổi | Scope §6, N3 | view `app.kpi_daily_v` | Bảng mới + backfill bằng truy vấn của view; job N điền tiếp |
| `price_rule` | Giá theo loại ô × cấp × đơn vị, có phiên bản | BR-19, FR-21 | `zone_policy.prices` jsonb | Bảng mới + backfill bằng cách tách `prices` |
| `agreement_template` | Mẫu thỏa thuận có phiên bản theo khu | FR-08, AC-07 | `zone_policy.agreement_template_md` | Bảng mới + backfill; thêm `agreement.template_id` |
| `subzone` | Phân khu thành dòng có tên | PRD §2 | `building.subzone_code` | Bảng mới + backfill, rồi FK |
| `basement` | Tầng hầm thành dòng (tên, sức chứa) | vị trí ô, UX | `slot.level_code` (`B2`, `G`) | Bảng mới + backfill, rồi FK |
| `size_class` | Danh mục kích thước xe có hạng | BR-11, FR-07 | enum có thứ tự `app.size_class` | Bảng mới + backfill từ enum |
| `chain` | Đơn vị vận hành thành dòng | PRD §2 | bỏ; `zone.code` UNIQUE toàn hệ thống | Chỉ cần khi có nhiều đơn vị vận hành |
| `lpr_source` | Danh mục camera / adapter, ngưỡng OCR theo nguồn | FR-19, BR-13 | `lpr_event.source_code`; ngưỡng ở `zone_policy` | Bảng mới + backfill theo `(zone_id, source_code)` |
| `gate` | Cổng của khu thành dòng | màn hình LPR, job N | `lpr_event.gate_code` | Bảng mới + backfill, rồi FK |

## (b) Tính năng Ưu tiên 3 (bảng v2 số 40–53)

Mỗi nhóm phục vụ một tính năng Ưu tiên 3; đưa lại cùng module. Tất cả là *chỉ bảng mới*, trừ ghi chú.

| Bảng bỏ | Giải quyết gì | Phục vụ | Ghi chú |
|---------|---------------|---------|---------|
| `plate_access_log` | Log mỗi lần xem biển số gốc (ai, vì sao, khi nào). **Phải có trước** nếu màn hình nào hiện biển số gốc | AC-12, BR-09, D-06 | Cùng hàm `reveal_lpr_plate` / `reveal_vehicle_plate` |
| `password_reset_token` | Token quên mật khẩu, dùng một lần, có hạn | ADR-0006 | — |
| `holiday` | Lịch ngày lễ theo khu | FR-20, N3/N4 | Seed từ lịch chính thức |
| `parking_session` | Lượt đỗ thực tế từ LPR vào / ra, nhiều lượt vào / ra mỗi booking | W4 (v5: `booking.checked_*_at` đủ cho MVP) | Cần `lpr_event` (đã có) |
| `overstay_case` | Hồ sơ quá giờ: nhắc lặp, nhiều lượt vào / ra, báo cáo quá giờ | FR-11/12, D-03 | **v5:** không cần bảng cho hai lần nhắc + phí lúc ra (cột `zone_policy.overstay_*`, `payment.kind = 'overstay_fee'` đã có, [D-33](07-db-decision-log.md#d-33)). Thêm lại khi cần nhắc lặp hoặc báo cáo |
| `voucher` | Voucher khách shophouse, chỉ TH3 | BR-06, FR-22, AC-16 | Thêm lại `payment.voucher_id`, `discount_vnd`, `gross_vnd`, trigger `payment_validate_voucher` |
| `swap_need`, `swap_proposal`, `swap_leg` | Nhu cầu đổi, đề xuất và quyết định BQL, phần mỗi bên (`accepted_at`) | FR-17/18, BR-10, D-10 | Thêm lại `slot_holding.swap_proposal_id`, trigger `swap_proposal_validate`, cờ `swap_requires_party_consent` |
| `reconciliation_report` | Báo cáo đối soát cuối ngày | N3 | — |

## (c) Trước khi có dữ liệu thật (bảng v2 số 54–57)

MVP chạy được với dữ liệu demo; **không được** giữ dữ liệu người thật cho đến khi có `privacy_request` và `retention_rule` (cùng các hàm
dùng chúng). Căn cứ: PDPL 91/2025/QH15, NĐ 356/2025/NĐ-CP (D-22).

| Bảng bỏ | Giải quyết gì | Phục vụ | Ghi chú |
|---------|---------------|---------|---------|
| `retention_rule` | Hạn lưu theo loại dữ liệu, job xóa đọc | D-05, D-06, D-12 | Seed hạn từ nhật ký quyết định; thêm lại `purge_expired`, `purge_agent_checkpoints` và nhánh `purgeable` của `reject_mutation()` |
| `privacy_request` | Yêu cầu của chủ thể dữ liệu với `due_at` | D-14, D-15, NĐ 356 Đ.5 | Cùng `erase_user`; cột biển số, số điện thoại đã cho phép NULL |
| `occupancy_hourly` | Lịch sử chiếm chỗ theo giờ, không dữ liệu cá nhân | FR-20, D-05 | Lịch sử bắt đầu khi có bảng |
| `vacancy_forecast` | Dự báo ô trống theo khu và giờ | FR-05, FR-20, N4 | — |

## (d) Bỏ ở v4 (8 bảng, D-32)

DDL v3 nằm trong lịch sử git của `docs/03-design/sql/schema.sql` (trước thay đổi v4).

| Bảng bỏ | Giải quyết gì | Thay bằng ở v4 | Đưa lại thế nào |
|---------|---------------|----------------|-----------------|
| `staff_zone` | Nhân viên làm cho nhiều khu; claim `zone_ids` dạng danh sách | `app_user.staff_zone_id` (một khu) | Bảng mới + backfill từ cột; đổi claim và RLS sang bảng nối. Cần khi một người phục vụ hai khu |
| `refresh_token` | Refresh token xoay vòng, phát hiện dùng lại | Chỉ access JWT **8 giờ**, không thu hồi | Chỉ bảng mới; làm trước người dùng thật, cùng access token 15 phút |
| `otp_challenge` | OTP lưu trong DB, có hạn và giới hạn lần thử | Khóa Redis; DB giữ `agreement.*_confirmed_at` + `consent_record` | Chỉ cần nếu OTP phải sống qua sự cố Redis hoặc cần kiểm toán |
| `ledger_entry`, `ledger_head` | Sổ cái chuỗi hash theo khu, kiểm được (`ledger_verify`) | FR-09 = `consent_record` (chỉ ghi thêm, không chuỗi) | Bảng + hàm `ledger_*` + backfill bằng cách phát lại `consent_record` theo `id`. Khi có yêu cầu pháp lý |
| `outbox` | Outbox giao dịch, relay ít nhất một lần, mang `traceparent` | `notification` cùng transaction, đẩy sau commit qua `platform.publish()` | Bảng + job relay (`FOR UPDATE SKIP LOCKED`) sau `platform.publish()`. Khi job nền kích hoạt workflow Agent |
| `idempotency_keys` | Bảng khóa chung cho bước không có dòng đích | Cột UNIQUE `idempotency_key` trên từng bảng đích | Chỉ bảng mới, giữ các cột |
| `audit_log` | Lịch sử thay đổi cấu hình, tư cách, duyệt bằng trigger | Không; `zone_policy` có phiên bản | Bảng + `audit_row()` + trigger; không backfill. Ưu tiên 3 |

Thiết kế DBML nên dùng lại và các hàm, enum đã bỏ: [11-deferred-designs-functions](11-deferred-designs-functions.md).

## Đã đưa vào v5 (không còn hoãn)

| Bảng v2 | Thay bằng ở v5 | Ghi chú |
|---------|----------------|---------|
| `dispute_category`, `dispute_ticket`, `dispute_party`, `dispute_evidence` | `dispute_case` + `dispute_evidence` (FR-13…16, BR-14, BR-18) | Theo thiết kế `dispute_cases` + `dispute_evidence` của bản DBML thay thế, rút gọn theo kiểu v4; danh mục thành enum `dispute_category`, bên liên quan thành `reporter_user_id` / `respondent_user_id`. Còn hoãn: bảng danh mục, tranh chấp lặp → hoán đổi (N5, M11), log xem biển số gốc |

## Cách khôi phục một bảng

1. Chép bảng, index, policy RLS, quyền, trigger, comment từ DDL v2 (`git show 333b85b:docs/database/02-schema.sql`); bảng nhóm (d) lấy từ
   bản v3 của `sql/schema.sql` trong lịch sử git.
2. Thêm cột cần trên các bảng còn lại (cột "Ghi chú" / "Đưa lại"), thành revision Alembic SQL thuần (ADR-0005, skill `new-migration`).
3. Với *bảng mới + backfill*: chép dữ liệu từ cột đã gộp, đối chiếu số dòng, xóa cột ở revision sau.
4. Thêm test v2 của bảng vào `sql/seed-and-tests.sql` và cập nhật từ điển, sơ đồ.
