# Backlog — Workflow AI Agent

> **File này trả lời:** workflow Agent nào làm theo mức ưu tiên, kích hoạt bằng gì, gồm những bước nào.
> Liên quan: [README](README.md) · [Module](01-modules.md) · [Workflow nền](03-background-workflows.md) · [PRD §5](../02-prd.md#5-quy-tắc-nghiệp-vụ)

**Loại bước:** `[TĐ]` tất định · `[LLM]` dùng LLM · `[HITL]` BQL duyệt · `[RAG]` truy xuất nội quy.

**Nguyên tắc**
- LLM chỉ gợi ý; tư cách, quyền thuê, phí do rule engine quyết định (BR-14). Tên, biển số thay bằng mã giả trước khi gửi LLM.
- Mỗi bước `[LLM]` / `[HITL]` ghi một dòng `ai_decision_log` (hash, model, `trace_id`; [ADR-0011](../../07-adr/ADR-0011-mvp-simplifications.md)).
- `[HITL]` dừng graph bằng checkpointer (`agent_thread`), chạy tiếp khi BQL của khu có ô duyệt qua `POST /approvals/{id}/decision` (BR-18).

## 1. Phạm vi theo mức

| Workflow | Kích hoạt | Ưu tiên 1 | Ưu tiên 2 | Ưu tiên 3 |
|----------|-----------|-----------|-----------|-----------|
| **W0** Supervisor | `POST /chat/stream` | • Toàn bộ; chuyển sang W1, W2 | • Chuyển sang W3, W5, W7 | • — |
| **W1** Xin chỗ | W0 | • Toàn bộ, trừ FR-27 | • `[LLM]` gợi ý khu khác (FR-27) | • — |
| **W2** Chia sẻ chỗ | `POST /share-windows` | • Đến lưu bằng chứng, gồm HITL | • VietQR mock | • — |
| **W3** Chủ về sớm | `POST /bookings/{id}/early-return` | • Toàn bộ, từ app | • Kích hoạt từ chat | • Từ LPR |
| **W4** Phí quá giờ | Xe ra (N1) | • — | • Toàn bộ | • — |
| **W5** Tranh chấp | `POST /disputes` | • Đến gom bằng chứng | • `[LLM]` gợi ý + HITL | • Làm mờ ảnh tự động |
| **W6** Hoán đổi | `POST /swaps` | • — | • — | • Toàn bộ |
| **W7** Hỏi đáp nội quy | W0 | • — | • Toàn bộ | • — |

## 2. Chuỗi bước

**W0 — Supervisor** *(M14)*: `[TĐ] Guardrail (off-topic, prompt injection) → [TĐ] Mã giả → [LLM] Phân loại ý định → [TĐ] Chuyển workflow → [TĐ] Đổi mã giả về thật → [LLM] Stream SSE`

**W1 — Xin chỗ** *(M5 · M3 · M1 · M2)*: `[TĐ] Hồ sơ, xe → [TĐ] Cấp L1–L4 + hạn → [TĐ] Rule engine: cấp × phạm vi mở → vi phạm thì chặn → [TĐ] Ghép theo giờ, kích thước, dự phòng, giữ chỗ → W2 → [TĐ] Không được / hết ô → TH3 cùng khu → bãi công cộng → (P2) [LLM] gợi ý khu khác`

**W2 — Chia sẻ chỗ** *(M4 · M6 · M7)*: `[TĐ] Đăng khung giờ, chặn TH3, kèm dự phòng → [TĐ] Ghép → [TĐ] Sinh thỏa thuận theo mẫu khu → [TĐ] Hai bên xác nhận OTP → [HITL] Vượt ngưỡng → BQL duyệt → [TĐ] Lưu consent_record, thông báo → (P2) VietQR mock`

**W3 — Chủ về sớm** *(M9 · M4 · M5, BR-07)*: `[TĐ] "Tôi về sớm" → [TĐ] Lượt đỗ đang diễn ra → [TĐ] recovery_case, tìm ô TH3 cùng khu kèm giá (D-09) → [TĐ] Người thuê chấp nhận → đổi booking, thông báo → [HITL] Không có ô / từ chối → BQL`

**W4 — Phí quá giờ** *(M9 · M7, BR-08)*: `[TĐ] Xe ra → [TĐ] Nội quy khu: miễn 10 phút, 12 500 đ / bước 15 phút → [TĐ] Tạo overstay_fee (về chủ chỗ; TH3 về khu) → [TĐ] Thông báo`. Không có `[LLM]`; miễn phí chỉ qua W5.

**W5 — Tranh chấp** *(M10 · M6 · M8, BR-18)*: `[TĐ] Báo kèm ảnh + loại → [TĐ] Hồ sơ theo khu của ô, mã giả biển số → [TĐ] Gom bằng chứng (ảnh, thỏa thuận, log cổng, phí quá giờ) → (P2) [LLM] Đọc ảnh đã che, tóm tắt "Gợi ý" → [HITL] BQL quyết định → [TĐ] Thông báo`. Bằng chứng chỉ ghi thêm; demo dùng ảnh che sẵn.

**W7 — Hỏi đáp nội quy** *(M3 · M14)*: `[LLM] Phân loại → [RAG] Nội quy lọc theo khu / tòa → [LLM] Trả lời kèm trích dẫn → [TĐ] Không cam kết giá, quyền thuê`

## 3. Eval cần có (Demo Day)

| Nhóm case | Tối thiểu | Workflow |
|-----------|-----------|----------|
| Định tuyến đúng cấp, chặn sai tư cách | 12 | W1 |
| Chia sẻ, thỏa thuận, HITL vượt ngưỡng | 10 | W2 |
| Chủ về sớm | 5 | W3 |
| Hỏi đáp nội quy có trích dẫn | 8 | W7 |
| An toàn: guardrail, prompt injection, PII, off-topic | 10 | W0 |
| **Tổng** | **≥45** | |

Cách viết case: skill `eval-case`, dữ liệu ở `eval/datasets/`.
