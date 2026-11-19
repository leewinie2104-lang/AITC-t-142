# Backlog ParkSmart AI — 3 nhóm × 3 mức ưu tiên (4 người, 4 tuần)

> **File này trả lời:** làm gì, làm cái nào trước, và mỗi mức ưu tiên nghĩa là gì.
> Liên quan: [PRD](../02-prd.md) · [Scope](../03-scope.md) · [User Stories](../04-user-stories.md) · [Traceability](../06-traceability.md)
> Chi tiết: [Module](01-modules.md) · [Workflow AI Agent](02-agent-workflows.md) · [Workflow nền](03-background-workflows.md)

## 1. Ba mức ưu tiên

Dự án có **4 người trong 4 tuần** (~16 người-tuần), gồm cả hạ tầng AWS và eval ≥45 case cho Demo Day. Vì vậy chỉ một luồng chính được làm trọn; phần còn lại xếp theo giá trị khi demo.

| Mức | Khi nào phải xong | Ý nghĩa |
|-----|-------------------|---------|
| **Ưu tiên 1** | **Bắt buộc**, hết tuần 2 | Luồng chính *yêu cầu → tư cách → định tuyến → ghép → thỏa thuận → bằng chứng xác nhận* chạy được trên ít nhất 2 khu, giữ các nguyên tắc an toàn: rule engine quyết định, ẩn danh trước khi gửi LLM, BQL duyệt giao dịch vượt ngưỡng. |
| **Ưu tiên 2** | **Trước demo**, hết tuần 4 | Những phần làm demo thuyết phục: chủ về sớm (W3), hỏi đáp nội quy bằng RAG (W7), gợi ý khu khác, log LPR mô phỏng, KPI cơ bản, eval và trace. |
| **Ưu tiên 3** | **Chưa cần ở demo** | Quá giờ, tranh chấp, hoán đổi, các job nền định kỳ, tích hợp thật, mục đang TBD hoặc chờ xác nhận pháp lý, tính năng toàn chuỗi. |

## 2. Tóm tắt theo nhóm

Chỉ ghi mã. Tính năng cụ thể ở từng mức: mục 1 của file chi tiết.

| Nhóm | Ưu tiên 1 | Ưu tiên 2 | Ưu tiên 3 |
|------|-----------|-----------|-----------|
| **Module** ([chi tiết](01-modules.md)) | M1–M7, M12, M13, M14 | M8, M9 bắt đầu ở mức này; bổ sung cho M1–M6, M12–M14 | M10, M11 (toàn bộ); bổ sung cho các module còn lại |
| **Workflow AI Agent** ([chi tiết](02-agent-workflows.md)) | W0, W1, W2 | W3, W7; bổ sung cho W0–W2 | W4, W5, W6, Agent hỗ trợ BQL; bổ sung cho W0–W3, W7 |
| **Workflow nền** ([chi tiết](03-background-workflows.md)) | — | N1 cơ bản | N1 đầy đủ, N2–N8 |

## 3. Lịch 4 tuần đề xuất

Theo 4 vai trò trong [Tech stack](../../02-architecture/02-tech-stack.md#gợi-ý-chia-việc-4-người): Server core · AI Agent · Client · Hạ tầng và vận hành.

| Tuần | Ưu tiên | Việc chính |
|------|---------|-----------|
| **1** | 1 | Schema, RLS, seed 3 khu (M1, M2, M3); rule engine + cấp L1–L4; khung W0 (guardrail, mã giả, phân loại ý định); đăng nhập, khung SPA; hạ tầng, CI/CD |
| **2** | 1 | W1 + M5 định tuyến; W2 + M4 / M6 / M7 (thỏa thuận, OTP, bằng chứng xác nhận, VietQR mock); HITL M12; thông báo M13; màn hình luồng chính |
| **3** | 2 | W3 chủ về sớm (M9); W7 RAG nội quy; gợi ý khu khác (FR-27); N1 nạp log mô phỏng (M8); đăng ký, xe, KPI cơ bản; realtime WebSocket |
| **4** | 2 | Eval ≥45 case + trace; sửa lỗi; chạy thử kịch bản demo trên 2–3 khu; tài liệu và slide |

Ưu tiên 3: chỉ làm khi ưu tiên 1 và 2 đã xong và còn thời gian.

## 4. Truy vết FR → module / workflow

| FR | Module | Workflow | Ưu tiên |
|----|--------|----------|---------|
| FR-01, FR-02, FR-03 | M5, M3 | W1 | 1 |
| FR-04 | M3 | W1 | 1 |
| FR-05 | M4 | W2, N4 | 3 |
| FR-06, FR-07 | M4 | W2 | 1 |
| FR-08, FR-09 | M6 | W2 | 1 |
| FR-09a | M12 | W2 (HITL) | 1 |
| FR-10 | M9 | W3 | 2 (từ app) · 3 (từ LPR, gợi ý khu lân cận) |
| FR-11, FR-12 | M9, M7 | W4, N2 | 3 |
| FR-13 → FR-16 | M10 | W5 | 3 |
| FR-16a | M8 | N1 | 2 (chống trùng) · 3 (so khớp mờ, OCR thấp) |
| FR-17, FR-18 | M11 | W6, N5 | 3 |
| FR-19 | M8 | N1 | 2 (CSV mô phỏng) · 3 (webhook / MQTT) |
| FR-20 | M4 | N4 | 3 |
| FR-21 | M7 | W2, W4 | 1 (phí chia sẻ, VietQR mock) · 3 (phí quá giờ) |
| FR-22 | M7 | — | 3 |
| FR-23, FR-24 | M1, M3 | W1 | 1 |
| FR-25 | M1 | W1, N6 | 1 (chặn khi xử lý yêu cầu) · 3 (quét, thông báo) |
| FR-26 | M3, M4 | W2 | 1 (cấu hình pool) · 2 (chủ chỗ thu hẹp) |
| FR-27 | M5 | W1, W3 | 2 |

## 5. Vì sao đặt ở đây

Backlog trả lời *làm gì, làm cái nào trước*: đây là quyết định sản phẩm nên đặt cạnh PRD và User Stories. Thiết kế kỹ thuật tham chiếu lại mã M / W / N ở đây: graph, prompt, eval của workflow Agent → `docs/12-ai/`; job, queue, lịch worker → `docs/02-architecture/`; API → `docs/04-api/`.

> Ảnh `docs/images/ParkSmartAI-{modules,agent-workflows,background-workflows}.png` vẽ lại 2026-11-18, **chưa** cập nhật theo phân bổ ưu tiên 4 tuần. Nếu lệch, văn bản đúng hơn ảnh ([docs/README](../../README.md)).
