# Backlog ParkSmart AI — 3 nhóm × 3 mức ưu tiên

> Liên quan: [PRD](../prd.md) · [Scope](../scope.md) · [User Stories](../user-stories.md)
> Chi tiết: [Module (FE/BE)](modules.md) · [Workflow AI Agent](agent-workflows.md) · [Workflow nền](background-workflows.md)

Backlog chia làm 3 nhóm. Mỗi nhóm được xếp theo 3 mức ưu tiên.

| Mức | Ý nghĩa | Phạm vi |
|-----|---------|---------|
| **1. Rất cần thiết** | Thiếu thì demo không chạy được luồng chính: *yêu cầu → xác định tư cách → định tuyến → ghép → thỏa thuận → sổ cái*, trên ít nhất 2 khu. Đồng thời phải giữ được các nguyên tắc an toàn (rule engine quyết định, ẩn danh trước khi gửi LLM, BQL duyệt giao dịch vượt ngưỡng). | Demo tối thiểu |
| **2. Nên có** | Hoàn thiện các giá trị đã cam kết trong PRD: ngoại lệ đầy đủ, tranh chấp, hoán đổi, dự báo, hỏi đáp nội quy, gợi ý chỗ liên khu, dashboard theo khu. | Demo đầy đủ |
| **3. Có thể trong tương lai** | Tích hợp thật, các mục đang TBD hoặc cần xác nhận pháp lý, tính năng cho cả chuỗi. | Sau demo |

## Tóm tắt theo nhóm

| Nhóm | Rất cần thiết | Nên có | Có thể trong tương lai |
|------|---------------|--------|------------------------|
| **Module** ([chi tiết](modules.md)) | M1 tư cách L1–L4; M2 mô hình khu–tòa–ô; M3 rule engine + phạm vi mở; M14 chat; M5 đặt chỗ; M4 lịch chia sẻ; M6 thỏa thuận + sổ cái; M7 VietQR mock; M9 về sớm qua app; M8 nạp log mô phỏng; M12 hàng chờ duyệt; M13 thông báo trong app | M10 tranh chấp; M11 hoán đổi 2 bên; voucher; sơ đồ bãi realtime; dự báo và đề xuất khung giờ; chủ chỗ thu hẹp phạm vi; gợi ý khu khác; KPI theo khu; BQL quản lý tư cách | Thanh toán thật; LPR thật; đồng bộ dữ liệu cư dân thật; mở TH1 ra cả khu; hoán đổi theo chuỗi; dashboard toàn chuỗi; push / Zalo |
| **Workflow AI Agent** ([chi tiết](agent-workflows.md)) | W0 Supervisor; W1 xin chỗ (có bước tính tư cách); W2 chia sẻ (có HITL vượt ngưỡng); W3 về sớm, kích hoạt từ app | W4 quá giờ; W5 tranh chấp; W6 hoán đổi 2 bên; W7 hỏi đáp nội quy (RAG theo khu); gợi ý khu khác trong W1 / W3; đề xuất khung giờ trong W2 | Hoán đổi theo chuỗi; bù phí khi chủ về sớm; Agent hỗ trợ BQL |
| **Workflow nền** ([chi tiết](background-workflows.md)) | N1 cơ bản (CSV mô phỏng, chuẩn hóa, bỏ trùng, gắn khu) | N1 đầy đủ; N2 quá giờ; N3 đối soát; N4 dự báo; N5 tranh chấp lặp; N6 quét tư cách hết hạn | N7 KPI toàn chuỗi; N8 cân bằng cung–cầu liên khu; LPR thật |

## Thứ tự làm đề xuất

1. **Rất cần thiết:**
   - Nền móng: M1, M2, M3, M14 + W0.
   - Luồng chính: M5 + W1 → M4 + W2 → M6 → M7.
   - Rồi M9 + W3 (từ app), M12 hàng chờ duyệt, M13, N1 cơ bản.
2. **Nên có:** N1 đầy đủ → W4 + N2 → W5 + M10 → W6 + N5 + M11. Song song: N4 → đề xuất khung giờ W2; N6; W7; N3 + dashboard.
3. **Tương lai:** theo nhu cầu sau demo.

## Truy vết yêu cầu chức năng

| FR | Module | Workflow | Mức |
|----|--------|----------|-----|
| FR-01, FR-02, FR-03 | M5, M3 | W1 | Rất cần thiết |
| FR-04 | M3 | W1 | Rất cần thiết |
| FR-05 | M4 | W2, N4 | Nên có |
| FR-06, FR-07 | M4 | W2 | Rất cần thiết |
| FR-08, FR-09 | M6 | W2 | Rất cần thiết |
| FR-09a | M12 | W2 (HITL) | Rất cần thiết |
| FR-10 | M9 | W3 | Rất cần thiết (từ app) · Nên có (từ LPR, gợi ý khu lân cận) |
| FR-11, FR-12 | M9, M7 | W4, N2 | Nên có |
| FR-13 → FR-16 | M10 | W5 | Nên có |
| FR-16a | M8 | N1 | Rất cần thiết (chống trùng) · Nên có (so khớp mờ, OCR thấp) |
| FR-17, FR-18 | M11 | W6, N5 | Nên có (2 bên) · Tương lai (theo chuỗi) |
| FR-19 | M8 | N1 | Rất cần thiết (CSV mô phỏng) · Nên có (webhook / MQTT) |
| FR-20 | M4 | N4 | Nên có |
| FR-21 | M7 | W2, W4 | Rất cần thiết (phí chia sẻ, VietQR mock) · Nên có (phí quá giờ) |
| FR-22 | M7 | — | Nên có |
| FR-23, FR-24 | M1, M3 | W1 | Rất cần thiết |
| FR-25 | M1 | W1, N6 | Rất cần thiết (chặn khi xử lý yêu cầu) · Nên có (quét, thông báo) |
| FR-26 | M3, M4 | W2 | Rất cần thiết (cấu hình pool) · Nên có (chủ chỗ thu hẹp) |
| FR-27 | M5 | W1, W3 | Nên có |

## Vì sao đặt ở đây

Backlog này trả lời câu hỏi *làm gì, làm cái nào trước*. Đó là quyết định sản phẩm, nên đặt cạnh PRD và User Stories trong `docs/01-product/`. Khi thiết kế kỹ thuật chi tiết:
- Graph LangGraph, prompt và eval của từng workflow Agent → `docs/12-ai/`.
- Job, queue và lịch chạy của worker → `docs/02-architecture/`.
- API → `docs/04-api/`.

Các tài liệu kỹ thuật đó tham chiếu lại mã M / W / N ở đây.

> Ba ảnh `docs/images/ParkSmartAI-{modules,agent-workflows,background-workflows}.png` là bản trước khi chuyển sang mô hình chuỗi N khu. Khi lệch nhau, tài liệu trong thư mục này là bản đúng.
