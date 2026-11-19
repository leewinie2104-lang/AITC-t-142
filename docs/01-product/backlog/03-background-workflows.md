# Backlog — Workflow nền

> **File này trả lời:** job nền nào làm theo mức ưu tiên, chạy thế nào, tạo ra gì.
> Liên quan: [README](README.md) · [Module](01-modules.md) · [Workflow Agent](02-agent-workflows.md)

**Nguyên tắc:** worker arq + Redis (queue `bg`, đăng ký ở `main_worker.py`), không gọi LLM. Job chỉ phát hiện và chuẩn
bị dữ liệu; đổi quyền hoặc tiền đi qua workflow Agent. Chạy riêng từng khu; không có outbox, gọi `platform.publish()`
([ADR-0011](../../07-adr/ADR-0011-mvp-simplifications.md)).

## 1. Phạm vi theo mức

| Job | Ưu tiên 1 | Ưu tiên 2 | Ưu tiên 3 |
|-----|-----------|-----------|-----------|
| **N1** Log LPR *(M8)* | • Nạp CSV mô phỏng, chống trùng, ghi giờ vào / ra | • `GET /zones/{id}/lpr-events` | • Webhook / MQTT, so khớp mờ, OCR thấp |
| **N2** Nhắc quá giờ *(M9)* | • — | • 2 lần nhắc | • Nhắc thêm, thông báo chủ chỗ |
| **N3–N8** | • — | • — | • Đối soát, dự báo giờ trống, tranh chấp lặp, quét tư cách, KPI chuỗi, cân bằng liên khu |

Tư cách hết hạn chặn ngay trong W1 (không cần N6); KPI theo khu đọc view `kpi_daily_v` (không cần job).

## 2. N1 — Log LPR *(`access/`)*

- **Kích hoạt:** `POST /api/v1/dev/lpr-events/import` hoặc CLI → enqueue theo khu.
- **Đầu vào:** CSV `source_code`, `source_event_id`, `gate_code`, hướng, thời điểm, biển số, độ tin cậy OCR.
- **Các bước:** chuẩn hóa, gắn khu → mã hóa biển số (`plate_ciphertext`, `plate_hash`, `plate_masked`) → bỏ trùng theo `(zone_id, source_code, source_event_id)` → khớp booking → ghi `checked_in_at / checked_out_at`.
- **Dữ liệu mô phỏng:** ngày thường, cuối tuần, Tết cho 3 khu; có dòng trùng, dòng OCR thấp, ca xe ra quá giờ.

## 3. N2 — Nhắc quá giờ *(`access/`)*

- **Kích hoạt:** cron ~5 phút mỗi khu. Ứng viên: booking `confirmed`, có giờ vào, chưa có giờ ra.
- **Nhắc:** trước giờ kết thúc 20 phút, và đúng lúc hết giờ (nêu 10 phút cho phép, 12 500 đ / 15 phút).
- **Idempotent:** khóa `overstay_pre:<booking_id>`, `overstay_due:<booking_id>`; chạy lại không gửi trùng. Không tính phí (W4 làm khi xe ra).

## 4. Kiểm thử

| Test | Kỳ vọng |
|------|---------|
| Nạp cùng file hai lần | Số dòng `lpr_event` không đổi (BR-13) |
| Sự kiện khu A | BQL khu B không thấy (RLS) |
| Sự kiện vào khớp booking | `checked_in_at` ghi một lần |
| Chạy N2 hai lần | Mỗi loại nhắc chỉ một `notification` |
