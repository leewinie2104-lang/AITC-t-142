# ADR-0011: Đơn giản hóa schema cho bản demo MVP (23 bảng), thêm nhật ký quyết định AI

- **Status**: Accepted · **Cập nhật 2026-11-19**: phí quá giờ (không có bảng ca quá giờ) và tranh chấp (2 bảng) quay lại MVP theo [D-33](../03-design/07-db-decision-log.md#d-33); schema còn 25 bảng
- **Date**: 2026-11-18
- **Liên quan**: [ADR-0004](ADR-0004-fastapi-langgraph-arq-on-ec2-docker-compose.md) · [0005](ADR-0005-rds-postgres-asyncpg-rls-alembic-sql.md) · [0006](ADR-0006-self-issued-jwt-auth.md) · [0010](ADR-0010-backend-modules-agent-workflows-jobs.md) · [Bảng hoãn](../03-design/08-deferred-tables.md) · [D-32](../03-design/07-db-decision-log.md#d-32)

## Context

- Demo có 4 tuần; schema 27 bảng (D-31) còn bảng chỉ phục vụ vận hành lâu dài (refresh token, sổ cái chuỗi hash, outbox, audit log…).
- Đội giữ `slot_pool`, cắt 8 bảng để ra demo sớm; đề bài là cách hiểu của đội nên spec sửa theo schema thay vì để lệch.
- Ban tổ chức yêu cầu nhật ký kiểm toán AI (guide ch.7 §7.6, ch.11 §11.7): ai quyết định, model nào, hash đầu vào / đầu ra, có người duyệt không.
- Bản DBML thay thế của đội (18 bảng) có 3 bảng được nhận về, viết lại theo quy ước repo.

## Decision

**Bỏ 8 bảng:** `refresh_token` → chỉ access JWT **8 giờ**, không thu hồi (người dùng thật cần quay lại ADR-0006) · `otp_challenge` → OTP giữ nguyên cơ chế nhưng lưu **Redis**; DB giữ `agreement.*_confirmed_at` + một `consent_record` · `staff_zone` → `app_user.staff_zone_id` (claim `zone_ids` một phần tử) · `ledger_entry`, `ledger_head` → không chuỗi hash; FR-09 = `consent_record` chỉ ghi thêm · `outbox` → ghi `notification` cùng transaction, đẩy realtime sau commit qua port `platform.publish()` (outbox quay lại khi job nền kích hoạt workflow, Ưu tiên 3) · `idempotency_keys` → cột UNIQUE `idempotency_key` trên từng bảng đích · `audit_log` → không; `zone_policy` có phiên bản.

**Thêm 4 bảng:** `agent_thread` (thread LangGraph, `pending_card` đã ẩn danh, không lưu tin nhắn gốc) · `recovery_case` (W3 chủ về sớm, một hồ sơ mở mỗi booking) · `consent_record` (bằng chứng đồng ý chỉ ghi thêm, trigger `reject_mutation()`, app chỉ INSERT / SELECT) · `ai_decision_log` (mỗi bước AI một dòng; chỉ **hash** `user_hash`, `input_hash`, `output_hash` + `model_version`, `risk_level`, `outcome`, `human_approved`, `trace_id`; khóa idempotent `thread_id:checkpoint_id:node`). Kết quả: 23 bảng.

## Consequences

**Tích cực:** ít hạ tầng (không relay outbox, không job thu hồi token, không chuỗi hash); vẫn đạt idempotent theo bảng đích và kiểm toán AI truy vấn được; bằng chứng xác nhận vẫn không sửa được ở tầng DB.

**Tiêu cực:** token lộ dùng được tới 8 giờ; superuser xóa / sắp lại bằng chứng không bị phát hiện; realtime có thể mất nếu process chết sau commit (vẫn thấy trong danh sách `notification`); không có lịch sử cấu hình ngoài phiên bản `zone_policy`. **Quay lại khi nào:** outbox cùng job nền kích hoạt Agent; refresh token trước người dùng thật; chuỗi hash, `audit_log` khi có yêu cầu pháp lý ([08](../03-design/08-deferred-tables.md)).

**Đã cân nhắc:** giữ 27 bảng (chậm demo); giữ outbox (vẫn phải dựng relay); chỉ dùng OTel để kiểm toán AI (trace bị lấy mẫu, khó truy vấn).

## Observability Impact

- `ai_decision_log` bổ sung, không thay trace OTel ([ADR-0008](ADR-0008-opentelemetry-lgtm-on-dedicated-ec2.md)); cột `trace_id` để nhảy sang Tempo.
- Demo không có `outbox_lag_seconds`, `auth_refresh_reuse_detected_total`, `auth_token_refresh_total`.
- `traceparent` không qua outbox: usecase gọi trực tiếp nên chuỗi nằm trong một trace.
- `ai_decision_log` chỉ có hash và id, không PII; RLS cho BQL đọc theo khu, người dùng không đọc.
