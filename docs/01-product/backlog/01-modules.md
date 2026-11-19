# Backlog — Module (API / DB / BE)

> **File này trả lời:** mỗi module cần API nào theo mức ưu tiên, dữ liệu ở bảng nào, code ở đâu.
> Liên quan: [README](README.md) (mức ưu tiên, lịch, danh sách Ưu tiên 3) · [Workflow Agent](02-agent-workflows.md) · [Workflow nền](03-background-workflows.md)

Endpoint bỏ tiền tố `/api/v1`; BE tính từ `server/src/app/`; DDL ở [`schema.sql`](../../03-design/sql/schema.sql).
Cột Ưu tiên 3 chỉ ghi endpoint; tính năng Ưu tiên 3 khác ở [README §5](README.md#5-ưu-tiên-3--chỉ-làm-nếu-còn-thời-gian).

## 1. Nền móng

| Module | Ưu tiên 1 | Ưu tiên 2 | Ưu tiên 3 | DB · BE |
|--------|-----------|-----------|-----------|---------|
| **M1** Tài khoản & tư cách | • `POST /auth/login`, `GET /me`<br>• Seed 5 vai trò, cấp L1–L4 + hạn, RLS | • `POST /registrations` (kèm đồng ý)<br>• `POST /auth/logout` | • `GET /me/eligibilities` | • `app_user`, `asset`, `eligibility`, `consent_record`<br>• `identity/`, `eligibility/` |
| **M2** Khu, tòa, ô, xe | • `GET /me/vehicles`<br>• Seed 3 khu → tòa → pool → ô | • `POST/PATCH/DELETE /me/vehicles` | • `GET /zones`, `GET /zones/{id}/slots` | • `zone`, `building`, `slot_pool`, `slot`, `vehicle`<br>• `facility/` |
| **M3** Nội quy & rule engine | • Không có API: rule engine tất định gọi trong W1 / W2<br>• Nội quy bằng seed | • `GET /zones/{id}/rules`<br>• Hỏi đáp W7 qua chat | • `PATCH /zones/{id}/rules` | • `zone_policy`, `knowledge_chunk`<br>• `policy/`, `knowledge/` |
| **M14** AI Agent Chat | • `POST /chat/stream` (SSE)<br>• W0, checkpointer HITL, `ai_decision_log` | • `GET /agent/threads/{id}`<br>• Trích dẫn RAG, **eval ≥45 case** | • `POST /agent/threads/{id}/messages` | • `agent_thread`, `ai_decision_log`<br>• `agent/`, `server/prompts/`, `eval/` |

## 2. Luồng chính

| Module | Ưu tiên 1 | Ưu tiên 2 | Ưu tiên 3 | DB · BE |
|--------|-----------|-----------|-----------|---------|
| **M4** Chia sẻ chỗ | • `POST /share-windows`, `DELETE /share-windows/{id}`<br>• Dự phòng, chặn TH3, ghép theo phạm vi mở | • `GET /me/share-windows` | • `PATCH /share-windows/{id}` | • `share_window`, `slot_holding`<br>• `sharing/` |
| **M5** Đặt chỗ | • Yêu cầu qua `POST /chat/stream` (W1)<br>• Ghép / TH3 / bãi công cộng / chặn kèm lý do | • `GET /me/bookings/current`, `GET /me/parking-requests`<br>• Gợi ý khu khác (FR-27) | • `POST /parking-requests/{id}/cancel`, `GET /parking-requests` | • `parking_request`, `booking`<br>• `booking/` |
| **M6** Thỏa thuận & bằng chứng | • `GET /agreements/{id}`, `POST /agreements/{id}/confirm`<br>• OTP Redis, bằng chứng chỉ ghi thêm | • `POST /agreements/{id}/otp/resend`<br>• BQL xem bằng chứng | • `GET /agreements` | • `agreement`, `consent_record`<br>• `ledger/`, `approval/` |
| **M7** Thanh toán | • Không có API: tính phí theo cấp trong W2 | • `GET /me/payments`, `GET /payments/{id}`, `POST /payments/{id}/mock-confirmation`<br>• Khoản TH3, hoàn tiền, phí quá giờ (W4) | • `POST /payments/{id}/refund` | • `payment`<br>• `payment/` |

## 3. Vận hành và quản trị

| Module | Ưu tiên 1 | Ưu tiên 2 | Ưu tiên 3 | DB · BE |
|--------|-----------|-----------|-----------|---------|
| **M8** LPR & ra vào | • `POST /dev/lpr-events/import` (hoặc CLI) → N1 | • `GET /zones/{id}/lpr-events` | • `POST /integrations/lpr/events` | • `lpr_event`, giờ vào / ra ở `booking`<br>• `access/` |
| **M9** Ngoại lệ | • `POST /bookings/{id}/early-return`, `POST /recovery-cases/{id}/accept` (W3) | • `GET /recovery-cases/{id}`<br>• Quá giờ tự động: N2, W4 | • `POST /recovery-cases/{id}/decision` | • `recovery_case`<br>• `agent/`, `booking/`, `access/` |
| **M10** Tranh chấp | • `POST /disputes`, `GET /disputes/{id}`<br>• Gom bằng chứng, biển số ẩn | • `GET /zones/{id}/disputes`, `POST /disputes/{id}/decision` (HITL) | • `GET /disputes/{id}/evidence` | • `dispute_case`, `dispute_evidence`<br>• `dispute/`, `agent/` |
| **M11** Hoán đổi | • — | • — | • `POST /swaps`, `GET /zones/{id}/swaps`, `POST /swaps/{id}/decision` | • Chưa có bảng ([deferred](../../03-design/08-deferred-tables.md))<br>• `swap/` (khung) |
| **M12** Dashboard BQL | • `GET /zones/{id}/approvals`, `POST /approvals/{id}/decision` → resume graph | • `GET /zones/{id}/kpis`, `GET /approvals/{id}` | • — | • `approval_request`, view `kpi_daily_v`<br>• `approval/`, `reporting/` |
| **M13** Thông báo | • `GET /me/notifications` (polling, ghi cùng transaction) | • `POST /me/notifications/{id}/read` | • — | • `notification`<br>• `notification/` |

## 4. Màn hình theo mức

| Mức | Cư dân / người thuê | BQL khu |
|-----|---------------------|---------|
| Ưu tiên 1 | • Đăng nhập, chat, chia sẻ chỗ, kết quả ghép, thỏa thuận + OTP<br>• "Tôi về sớm", báo tranh chấp, thông báo | • Hàng chờ duyệt, chi tiết tranh chấp |
| Ưu tiên 2 | • Thanh toán VietQR mock, đăng ký, xe, lượt đỗ hiện tại, hỏi đáp nội quy | • Bằng chứng xác nhận, KPI, quyết định tranh chấp |

Wireframe: [ux/wireframes](../ux/wireframes/README.md).
