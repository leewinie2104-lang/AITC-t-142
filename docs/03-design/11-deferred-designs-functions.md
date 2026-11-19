# 11 — Thiết kế hoãn lại và các hàm đã bỏ

> Tách từ [08-deferred-tables](08-deferred-tables.md) cho file ngắn. Ký hiệu nhóm (b), (c), (d) theo file đó.

## Thiết kế nên dùng lại từ bản DBML thay thế

Đội từng vẽ một thiết kế DBML 18 bảng. v4 đã nhận 3 bảng (`agent_thread`, `recovery_case`, `consent_record`) và v5 nhận thêm `dispute_cases` + `dispute_evidence` (D-33), viết lại theo quy ước repo:
UUIDv7, enum thay trạng thái `varchar`, FK ghép giữ cùng khu, `idempotency_key`, RLS. Các ý dưới đây (trừ dòng tranh chấp, đã nhận ở v5) **chưa** nhận; mỗi ý gắn với một tính năng
Ưu tiên 3, nên nhận **cùng module đó** và dùng thay các bảng v2 tương ứng. File DBML không nằm trong repo: lấy chi tiết từ bản của đội và giữ quy ước trên.

| Bảng thay thế | Ý tưởng | Vì sao chưa làm | Nhận cùng | Thay cho |
|---------------|---------|-----------------|-----------|----------|
| `slot_usage_claims` | Một bảng cho mọi lần dùng ô **tạm thời** (đặt chỗ chia sẻ, hoán đổi tạm, chuyển chỗ, bảo trì), một luật EXCLUDE duy nhất làm trọng tài chồng lấn; quyền dài hạn ở bảng riêng | `slot_holding` + `share_window` + `booking` đã mang quyền; thêm bảng bây giờ thành hai nguồn sự thật | Hoán đổi (M11, W6) | Kiểu nắm giữ `swap_usage` của v2 |
| `swap_proposals` | **Một bảng** cho hoán đổi hai bên (người khởi tạo, hai bên, hai ô, thời gian, trạng thái `awaiting_consent` → `awaiting_manager` → `confirmed`); đồng ý của mỗi bên là một dòng bằng chứng (`consent_record`) | M11 là Ưu tiên 3 | Hoán đổi (M11): giữ `accepted_at` từng bên (D-10), BQL duyệt qua `approval_request` | `swap_need`, `swap_proposal`, `swap_leg` |
| `dispute_cases` + `dispute_evidence` | Tranh chấp **hai bảng**; bằng chứng có `confidence_label` và loại `ai_vision_extraction` (ảnh do model đọc, hiện như gợi ý kèm độ tin cậy; BQL quyết định, BR-14) | **Đã nhận ở v5** (`dispute_case` + `dispute_evidence`, [D-33](07-db-decision-log.md#d-33)); danh mục là enum | Tranh chấp (M10, W5) | 4 bảng tranh chấp của v2 |
| `parking_sessions` | Lượt đỗ thực tế (vào / ra từ LPR) tách khỏi quyền sử dụng | v4 dùng `booking.checked_in_at` / `checked_out_at` cho demo | Quá giờ (W4, N2): khi một booking có nhiều lần vào / ra (v5 không cần: hai lần nhắc + phí lúc ra) | `parking_session` của v2 (cùng ý) |

**Không nhận:** `households` / `memberships` (đã có `asset` + `eligibility`, cũng cho ra L1–L4), hạn mức số xe (không có trong spec),
cột trạng thái `varchar` (repo dùng enum).

## Các hàm đã bỏ

| Hàm | Quay lại cùng |
|-----|---------------|
| `app.reveal_lpr_plate`, `app.reveal_vehicle_plate` | `plate_access_log` (nhóm b) |
| `app.payment_validate_voucher` | `voucher` (nhóm b) |
| `app.swap_proposal_validate` | `swap_proposal`, `swap_leg` (nhóm b) |
| `app.ensure_lpr_partitions`, `app.drop_expired_lpr_partitions` | partition `lpr_event` ([01-data-model §4.8](01-data-model.md#4-quyết-định-chính)); cần migration chép-và-đổi trên bảng đã có dữ liệu |
| `app.purge_expired`, `app.purge_agent_checkpoints` | `retention_rule` (nhóm c) |
| `app.erase_user` | `privacy_request` (nhóm c) |
| `app.ledger_hash`, `app.ledger_append`, `app.ledger_verify` (bỏ ở v4) | `ledger_entry`, `ledger_head` (nhóm d) |
| `app.audit_row()` và trigger của nó (bỏ ở v4) | `audit_log` (nhóm d) |

`reject_mutation()` cũng mất nhánh `purgeable`: từ v3, bảng chỉ ghi thêm không nhận DELETE nào (v4: `consent_record`, `ai_decision_log`).
Enum bị cắt bớt ở v3 (`holding_kind`, `approval_kind`, `payment_kind`; `ledger_entry_type` bỏ hẳn ở v4) lấy lại giá trị cùng tính năng dùng chúng (v5 đã lấy lại `overstay_fee`, `dispute_decision`);
enum bỏ hẳn (`voucher_status`, `lpr_source_kind`, `overstay_status`, họ `swap_*`, `workflow_*`, `privacy_request_*`,
`need_status`, `day_kind`, `consent_kind`) nằm trong DDL v2.
