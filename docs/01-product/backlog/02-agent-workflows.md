# Backlog — Workflow AI Agent

> **File này trả lời:** workflow Agent nào làm trong 4 tuần, gồm những bước nào.
> Liên quan: [README](README.md) · [Module](01-modules.md) · [Workflow nền](03-background-workflows.md) · [PRD §5](../02-prd.md#5-quy-tắc-nghiệp-vụ)

![ParkSmart AI — Workflow AI Agent trong 4 tuần](../../images/ParkSmartAI-agent-workflows.png)

**Loại bước:** `[TĐ]` tất định (rule engine / tool) · `[LLM]` dùng LLM · `[HITL]` BQL duyệt · `[RAG]` truy xuất nội quy.

**Nguyên tắc**
- LLM chỉ gợi ý; tư cách, quyền thuê, phí do rule engine quyết định (BR-14).
- Tên và biển số thay bằng mã giả trước khi gửi LLM, đổi lại sau khi có câu trả lời.
- Mỗi bước `[LLM]` hoặc `[HITL]` ghi một dòng `ai_decision_log` (chỉ hash, model, `trace_id`; [ADR-0011](../../07-adr/ADR-0011-mvp-simplifications.md)).
- Bước `[HITL]` dừng graph bằng checkpointer, lưu thread ở `agent_thread`, chạy tiếp khi **BQL của khu có ô** duyệt (BR-18).

## 1. Phạm vi theo mức

| Workflow | Ưu tiên 1 (tuần 1–2) | Ưu tiên 2 (tuần 3–4) |
|----------|----------------------|----------------------|
| **W0** Supervisor | Toàn bộ chuỗi bước; chuyển sang W1, W2 | Chuyển sang W3, W7; eval ≥45 case + trace |
| **W1** Xin chỗ / định tuyến | Cấp L1–L4, rule engine, ghép, giữ chỗ, chuyển TH3 / bãi công cộng | `[LLM]` gợi ý ô khu khác (FR-27) |
| **W2** Chia sẻ chỗ | Chuỗi bước đến lưu bằng chứng xác nhận, gồm HITL vượt ngưỡng | Bước thanh toán VietQR mock |
| **W3** Chủ về sớm | — | Kích hoạt từ app, TH3 cùng khu, HITL khi không có phương án |
| **W7** Hỏi đáp nội quy | — | Toàn bộ chuỗi bước |

W4 quá giờ, W5 tranh chấp, W6 hoán đổi, Agent hỗ trợ BQL: **không làm** ([README §5](README.md#5-không-làm-trong-4-tuần-ưu-tiên-3)).

## 2. Chuỗi bước

### W0 — Supervisor *(M14)*
Cửa vào mọi tin nhắn chat.

`[TĐ] Nhận tin nhắn → [TĐ] Guardrail (off-topic, prompt injection) → [TĐ] Thay tên, biển số bằng mã giả → [LLM] Phân loại ý định → [TĐ] Chuyển sang W1 / W2 / W3 / W7 → [TĐ] Đổi mã giả về giá trị thật → [LLM] Stream câu trả lời (SSE)`

### W1 — Xin chỗ / định tuyến *(M5 · M3 · M1 · M2)*
Người cần chỗ gửi yêu cầu; xác định được thuê loại chỗ nào rồi ghép hoặc chuyển hướng.

`[TĐ] Lấy hồ sơ và xe → [TĐ] Tính cấp L1–L4 tại tòa / khu của ô (kiểm tra hạn; khu khác chỉ dùng cấp + hạn) → [TĐ] Rule engine: cấp × phạm vi mở → [TĐ] Vi phạm rõ ràng → chặn, ghi KPI → [TĐ] Đủ quyền → ghép theo giờ, kích thước, dự phòng → giữ chỗ tạm → sang W2 (thỏa thuận) → [TĐ] Không đủ quyền hoặc hết ô → TH3 cùng khu theo giá cấp → [TĐ] Hết TH3 → bãi công cộng; Ưu tiên 2: [LLM] gợi ý ô khu khác, người dùng tự chọn`

### W2 — Chia sẻ chỗ *(M4 · M6 · M7)*
Chủ chỗ đăng khung giờ trống; ghép, lập thỏa thuận, chờ xác nhận, lưu bằng chứng, thanh toán.

`[TĐ] Chủ chỗ chọn khung giờ → [TĐ] Kiểm tra nội quy, không cho chia sẻ TH3 → [TĐ] Đăng lịch kèm dự phòng → [TĐ] Ghép người cần chỗ theo phạm vi mở → [TĐ] Sinh thỏa thuận theo mẫu khu có ô → [TĐ] Hai bên xác nhận OTP có hạn → [HITL] Vượt ngưỡng của khu → BQL khu duyệt → [TĐ] Lưu bằng chứng xác nhận (consent_record), thông báo → [TĐ] Ưu tiên 2: VietQR mock`

### W3 — Chủ về sớm *(M9 · M4 · M5)* — Ưu tiên 2
Bảo đảm quyền quay về của chủ chỗ (BR-07).

`[TĐ] Chủ chỗ bấm "Tôi về sớm" → [TĐ] Xác định lượt đỗ đang diễn ra → [TĐ] Mở recovery_case, rule engine tìm ô TH3 trống cùng khu kèm giá (D-09) → [TĐ] Người thuê chấp nhận → lưu đồng ý, đổi booking, thông báo → [HITL] Không có ô hoặc người thuê từ chối → BQL khu xử lý`

### W7 — Hỏi đáp nội quy *(M3 · M14)* — Ưu tiên 2
Trả lời câu hỏi nội quy của khu / tòa người hỏi, có trích dẫn.

`[LLM] Phân loại câu hỏi → [RAG] Truy xuất đoạn nội quy, lọc theo khu / tòa → [LLM] Trả lời kèm trích dẫn → [TĐ] Kiểm tra câu trả lời không hứa thay rule engine (không cam kết giá, quyền thuê)`

## 3. Eval cần có (Demo Day)

| Nhóm case | Số tối thiểu | Workflow |
|-----------|--------------|----------|
| Định tuyến đúng cấp, chặn sai tư cách | 12 | W1 |
| Chia sẻ, thỏa thuận, HITL vượt ngưỡng | 10 | W2 |
| Chủ về sớm | 5 | W3 |
| Hỏi đáp nội quy có trích dẫn | 8 | W7 |
| An toàn: guardrail, prompt injection, PII, off-topic | 10 | W0 |
| **Tổng** | **≥45** | |

Cách viết case: skill `eval-case`, dữ liệu ở `eval/datasets/`.
