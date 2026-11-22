# ADR-0011: Schema demo MVP 25 bảng, thêm nhật ký quyết định AI

- **Status**: Accepted
- **Date**: 2026-11-18 · cập nhật 2026-11-19 (D-33) · viết lại 2026-11-22 (plan 021)
- **Liên quan**: [ADR-0005](ADR-0005-rds-postgres-asyncpg-rls-alembic-sql.md) · [ADR-0006](ADR-0006-self-issued-jwt-auth.md) · [ADR-0010](ADR-0010-backend-modules-agent-workflows-jobs.md) · [Bảng hoãn](../03-design/08-deferred-tables.md) · [D-32, D-33](../03-design/07-db-decision-log.md#d-32)

## Context

- Demo có 4 tuần; schema 27 bảng (D-31) còn bảng chỉ phục vụ vận hành lâu dài (refresh token, sổ cái hash, outbox, audit log).
- Ban tổ chức yêu cầu nhật ký kiểm toán AI: ai quyết định, model nào, hash đầu vào / đầu ra, có người duyệt không.

## Decision

**Bỏ khỏi demo:**
- `refresh_token`: chỉ access JWT 8 giờ (ADR-0006).
- `otp_challenge`: OTP lưu trong Redis.
- `staff_zone`: thay bằng `app_user.staff_zone_id`.
- `ledger_entry`, `ledger_head`: không dùng chuỗi hash, bằng chứng là `consent_record` chỉ ghi thêm.
- `outbox`: ghi `notification` cùng transaction rồi đẩy sau commit qua `platform.publish()`.
- `idempotency_keys`: thay bằng cột UNIQUE `idempotency_key` trên từng bảng đích.
- `audit_log`: thay bằng việc `zone_policy` có phiên bản.

**Thêm:**
- `agent_thread`: thread LangGraph, `pending_card` đã ẩn danh, không lưu tin nhắn gốc.
- `recovery_case`: ca chủ về sớm, mỗi booking tối đa một ca mở.
- `consent_record`: trigger chặn sửa / xóa.
- `ai_decision_log`: mỗi bước AI một dòng, chỉ lưu hash `user_hash`, `input_hash`, `output_hash` cùng `model_version`,
  `risk_level`, `outcome`, `human_approved`, `trace_id`.
- Theo D-33: phí quá giờ là `payment` loại `overstay_fee`; tranh chấp có `dispute_case` và `dispute_evidence`. Tổng: **25 bảng**.

## Consequences

- **Tích cực:** ít hạ tầng (không relay outbox, không job thu hồi token); vẫn idempotent theo bảng đích; kiểm toán AI truy vấn được.
- **Tiêu cực:** token lộ dùng được tới 8 giờ; superuser sửa được bằng chứng mà không bị phát hiện; thông báo realtime có thể mất nếu
  process chết sau commit (vẫn còn trong danh sách `notification`).
- **Quay lại khi:** outbox khi job nền kích hoạt Agent ở quy mô lớn; refresh token trước người dùng thật; chuỗi hash, `audit_log` khi có yêu cầu pháp lý.

## Observability Impact

- `ai_decision_log` bổ sung, không thay trace OTel; cột `trace_id` để nhảy sang trace. Chỉ có hash và id, không PII; RLS cho BQL đọc theo khu.
