# ADR-0011: Đơn giản hóa schema cho bản demo MVP (23 bảng), thêm nhật ký quyết định AI

- **Status**: Accepted
- **Date**: 2026-11-18
- **Liên quan**: [ADR-0004](ADR-0004-fastapi-langgraph-arq-on-ec2-docker-compose.md) · [ADR-0005](ADR-0005-rds-postgres-asyncpg-rls-alembic-sql.md) · [ADR-0006](ADR-0006-self-issued-jwt-auth.md) · [ADR-0008](ADR-0008-opentelemetry-lgtm-on-dedicated-ec2.md) · [ADR-0010](ADR-0010-backend-modules-agent-workflows-jobs.md) · [Bảng hoãn lại](../03-design/08-deferred-tables.md) · [D-32](../03-design/07-db-decision-log.md#d-32) · [PRD](../01-product/02-prd.md) (FR-09, FR-14)

## Context

- Bản demo có 4 tuần. Schema 27 bảng (D-31) còn các bảng chỉ phục vụ vận hành lâu dài: refresh token, sổ cái băm chuỗi, outbox, audit log...
- Đội giữ `slot_pool` và cắt 8 bảng để ra demo sớm hơn. Đề bài ([00-xac-dinh-bai-toan](../01-product/00-xac-dinh-bai-toan.md)) là cách hiểu của chính đội, nên spec được sửa theo schema thay vì để lệch.
- Ban tổ chức yêu cầu nhật ký kiểm toán cho AI (guide chương 7 §7.6, chương 11 §11.7): ai quyết định, model nào, băm đầu vào / đầu ra, có người duyệt hay không.
- Đội cũng đã có một bản thiết kế DBML thay thế (18 bảng). Ba bảng của bản đó được nhận về, viết lại theo quy ước của repo.

## Decision

**Bỏ 8 bảng**

| Bảng bỏ | Thay bằng |
|---------|-----------|
| `refresh_token` | Chỉ access JWT, **hạn 8 giờ** cho demo. Không thu hồi, không phát hiện dùng lại refresh. Chỉ dùng cho demo; người dùng thật cần quay lại ADR-0006 |
| `otp_challenge` | OTP xác nhận thỏa thuận vẫn giữ nguyên cơ chế (lưu hash, có hạn, giới hạn số lần thử) nhưng lưu trong **Redis**. DB giữ `agreement.*_confirmed_at` và một dòng `consent_record` |
| `staff_zone` | Cột `app_user.staff_zone_id` (mỗi BQL / bảo vệ một khu). Claim JWT `zone_ids` là danh sách một phần tử |
| `ledger_entry`, `ledger_head` | Không có chuỗi hash. FR-09 viết lại: bằng chứng của hai bên xác nhận là một dòng `consent_record` chỉ ghi thêm |
| `outbox` | Usecase ghi `notification` trong cùng transaction; đẩy realtime sau khi commit. Port `platform.publish()` giữ chỗ để thêm outbox sau mà không sửa usecase. Job nền kích hoạt workflow Agent là Ưu tiên 3 và sẽ mang outbox trở lại |
| `idempotency_keys` | Mỗi bảng đích ghi có cột `idempotency_key` UNIQUE (`booking`, `payment`, `share_window`, `parking_request`, `notification`, `recovery_case`, `ai_decision_log`), đáp ứng guide chương 7 "Idempotent" |
| `audit_log` | Lịch sử cấu hình là Ưu tiên 3; `zone_policy` đã có version. Nhật ký quyết định AI nằm ở `ai_decision_log` (bên dưới) |

**Thêm 4 bảng**
- `agent_thread`: thread LangGraph của một người dùng (trạng thái, thẻ xác nhận đã ẩn danh `pending_card`). Không lưu nội dung tin nhắn gốc (BR-14, D-12).
- `recovery_case`: ca chủ xe về sớm (W3, Ưu tiên 2), gồm phương án từ rule engine, ca mở duy nhất theo booking.
- `consent_record`: bằng chứng đồng ý, chỉ ghi thêm (trigger `reject_mutation()`), thay `app_user.consent_*`. Vai trò app chỉ có INSERT và SELECT.
- `ai_decision_log`: nhật ký quyết định AI, chỉ ghi thêm. Mỗi dòng là một bước quyết định hoặc gợi ý. Chỉ lưu **hash** (`user_hash` HMAC, `input_hash`, `output_hash` SHA-256), `model_version`, `risk_level`, `outcome`, `human_approved`, `trace_id`. Không lưu prompt hay đầu ra thô. Khóa idempotent là `thread_id:checkpoint_id:node` (quy ước ADR-0010).

Kết quả: 23 bảng.

## Consequences

**Tích cực**
- Ít hạ tầng hơn cho demo: không relay outbox, không job thu hồi token, không chuỗi hash cần kiểm.
- Vẫn đạt yêu cầu của ban tổ chức: idempotent theo từng bảng đích, kiểm toán AI bằng dữ liệu truy vấn được.
- Bằng chứng xác nhận vẫn không sửa được ở tầng DB.

**Tiêu cực**
- Token bị lộ dùng được đến 8 giờ và không thu hồi được. Chấp nhận cho demo, không dùng cho người thật.
- Không còn chuỗi hash nên không phát hiện được việc xóa hoặc sắp xếp lại bằng chứng bởi người có quyền superuser. Chỉ còn quyền INSERT/SELECT và trigger.
- Thông báo realtime đẩy sau commit có thể mất nếu process chết giữa chừng; người dùng vẫn thấy ở danh sách `notification`.
- Không có lịch sử thay đổi cấu hình ngoài version của `zone_policy`.

**Cái gì quay lại khi nào:** xem [08-deferred-tables.md](../03-design/08-deferred-tables.md) và quyết định [D-32](../03-design/07-db-decision-log.md#d-32). Tóm tắt: outbox cùng job nền kích hoạt workflow Agent (Ưu tiên 3); refresh token trước khi có người dùng thật; chuỗi hash sổ cái và `audit_log` khi có yêu cầu pháp lý hoặc vận hành.

## Observability Impact

- `ai_decision_log` bổ sung cho trace OTel của [ADR-0008](ADR-0008-opentelemetry-lgtm-on-dedicated-ec2.md), không thay thế. Cột `trace_id` cho phép nhảy từ một dòng sang Tempo.
- Không còn `outbox_lag_seconds`, `auth_refresh_reuse_detected_total`, `auth_token_refresh_total` trong demo.
- `traceparent` không đi qua outbox nữa: usecase gọi trực tiếp, nên chuỗi nằm trong cùng một trace; khi outbox quay lại thì truyền `traceparent` như ADR-0010.
- Bảo mật: `ai_decision_log` chỉ có hash và id, không có PII; RLS cho BQL đọc theo khu, người dùng không đọc.

## Alternatives considered

- **Giữ 27 bảng:** an toàn hơn về dài hạn nhưng chậm demo, nhiều thứ không ai dùng trong 4 tuần.
- **Giữ outbox, bỏ các bảng khác:** vẫn phải dựng relay; chưa có job nền nào kích hoạt workflow.
- **Chỉ dùng OTel cho kiểm toán AI:** trace có thể bị lấy mẫu và khó truy vấn từ màn hình BQL, nên thêm bảng tóm tắt.
