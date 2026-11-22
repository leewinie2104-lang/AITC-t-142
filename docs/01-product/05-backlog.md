# 05 — Backlog 4 tuần

> **File này trả lời:** use case pilot làm trước cái gì; mỗi tính năng làm ở tuần nào, mức nào, ticket nào.
> **Bảng đầy đủ, lọc được** (mức, tuần, người làm, tìm kiếm): [backlog.html](backlog.html).
> Liên quan: [Pilot một tòa](07-pilot-mot-toa.md) · [PRD](02-prd.md) · [Traceability](06-traceability.md) · [ADR-0015](../07-adr/ADR-0015-renter-gps-eta-otp-and-two-layer-approval.md) · [ADR-0010](../07-adr/ADR-0010-backend-modules-agent-workflows-jobs.md)

## 0. Ưu tiên use case pilot

Làm các tính năng của [use case pilot một tòa](07-pilot-mot-toa.md) **trước** các tính năng khác cùng mức. Ticket mới chưa gán người.
Bỏ hẳn thanh toán QR / VietQR: khoản phí chỉ được ghi nhận (M7). Đã hủy SCRUM-114, 115, 135 (QR); SCRUM-116, 117, 129 đã viết lại theo luồng về sớm mới.

| Tính năng use case | Mức | Tuần | Ticket mới | Ticket nền đã có |
| --- | --- | --- | --- | --- |
| Schema cho pilot (hàng chờ, OTP chủ, ETA người thuê, kết quả duyệt 2 lớp, tạm ngừng nhận lượt) | 1 | 2 | SCRUM-183 | SCRUM-81 |
| Chỗ trống khi chủ đã nhập OTP cho thuê **và** xe chủ đã ra (BR-20) | 1 | 2 | SCRUM-184 | SCRUM-97, SCRUM-109 |
| Hàng chờ người thuê, đủ điều kiện khi ETA ≤ 30 phút (BR-21) | 1 | 2 | SCRUM-185 | SCRUM-96 |
| Ghép từ hàng chờ khi có chỗ vừa trống | 1 | 2 | SCRUM-186 | SCRUM-112, SCRUM-95 |
| Agent đề xuất ghép, rule engine chốt (FR-30) · chỉ số lịch sử hai bên | 1 | 2 | SCRUM-187 · SCRUM-188 | — |
| Giữ chỗ theo ETA + OTP nhận chỗ 3 phút; quá hạn trả người kế tiếp (BR-22, FR-35) | 1 | 2 | SCRUM-189 | SCRUM-104 |
| OTP chủ xác nhận cho thuê + OTP người thuê nhận chỗ (BR-25) · thỏa thuận | 1 | 2 | — | SCRUM-99, SCRUM-100 |
| FE hàng chờ + trạng thái chỗ của chủ | 1 | 2 | SCRUM-190 | SCRUM-98 |
| Kịch bản demo một tòa (seed + log cổng) | 1 | 2 | SCRUM-191 | SCRUM-85, SCRUM-110 |
| GPS mỗi 15 phút + ETA người thuê (FR-31, BR-27) | 1 | 2 | SCRUM-201 | — |
| Sổ khoản phí (không QR) + hủy lượt, khoản hoàn theo nội quy (BR-23) | 2 | 3 | SCRUM-192 | — |
| Nhắc quá giờ · phí khi xe ra · báo bảo vệ (FR-32) | 2 | 3 | SCRUM-193 | SCRUM-124, SCRUM-130 |
| Chủ về sớm: ETA (mock), người thuê chọn dời / ở lại, ô dự phòng, tạm ngừng nhận lượt (BR-07, BR-24) | 2 | 3 | SCRUM-116 (API) · SCRUM-129 (W3) · SCRUM-117 (FE) · SCRUM-194 (ETA) · SCRUM-196 (ô dự phòng) | — |
| Duyệt 2 lớp: rule + AI rủi ro, BQL chỉ ca xấu (FR-33, BR-26) | 1 | 2 | SCRUM-198 | SCRUM-106, SCRUM-107 |
| Ưu tiên TH3 cho người liên quan khu + báo BQL / bảo vệ (FR-36, BR-28) | 2 | 3 | SCRUM-202 | — |
| Báo số chỗ còn lại + gợi ý bãi khác (FR-37, BR-29) | 2 | 3 | SCRUM-203 | — |
| Đăng ký tự đối chiếu dữ liệu BQL (FR-38, BR-26) | 1 | 2 | SCRUM-204 | — |
| Tranh chấp: dòng thời gian có nguồn (FR-34) | 2 | 3 | SCRUM-199 | SCRUM-136, SCRUM-127 |
| Eval cho các bước AI của pilot | 2 | 3–4 | SCRUM-200 | SCRUM-145 |

## 1. Cách đọc

- Mỗi dòng trong bảng đầy đủ là **một tính năng**; ô có nội dung là **một task** cho người làm cột đó (DB, BE, Worker nền, Worker Agent, FE); "—" là không cần.
- **Mức:** **1** siêu cần thiết (xong hết tuần 2) · **2** cố gắng trước demo (tuần 3) · **3** nếu còn thời gian (§6).
- Mã **N1–N9** (worker nền, §4), **W0–W7** (worker Agent, §5). Endpoint bỏ tiền tố `/api/v1`. LLM chỉ gợi ý, rule engine quyết định (BR-14); `[HITL]` chờ BQL của khu có ô duyệt.

**Tóm tắt theo tuần**

- **Tuần 1:** nền tảng: migration 25 bảng + RLS, docker compose, khung SPA, đăng nhập, khu / tòa / ô, nội quy và rule quyền thuê, khóa mã hóa biển số, chat W0.
- **Tuần 2 (mức 1):** luồng chính pilot: chỗ trống khi chủ đã nhập OTP và xe ra (BR-20), hàng chờ ETA ≤ 30 phút (BR-21), ghép, giữ chỗ theo ETA + OTP nhận chỗ (BR-22), duyệt 2 lớp, GPS / ETA người thuê, sổ khoản, kịch bản demo, N1 và N9. Cuối tuần 2 luồng chính chạy end-to-end.
- **Tuần 3 (mức 2):** ngoại lệ và trải nghiệm: hủy và hoàn, quá giờ, chủ về sớm, ưu tiên TH3, báo số chỗ còn lại, đăng ký đối chiếu BQL, tranh chấp, W3, W4, W5, W7, N2. Cuối tuần 3 đóng băng tính năng.
- **Tuần 4:** chỉ sửa lỗi, test tích hợp Postgres thật, eval (≥ 45 case), demo.

## 2. Tính năng

Bảng đầy đủ M1–M14 (mỗi tính năng × DB / BE / Worker nền / Worker Agent / FE, mức, tuần, ticket) nằm ở [backlog.html](backlog.html), mục 2.

## 3. Việc chung

Migration, hạ tầng, khóa mã hóa biển số, tham số pilot, eval, lưu ảnh tranh chấp: xem [backlog.html](backlog.html), mục 3.

## 4. Worker nền (N1–N9)

Job chạy ngầm queue `bg` (arq), **không gọi LLM**; phát sự kiện qua port `publish()`. Trong 4 tuần làm N1, N9 (mức 1) và N2 (mức 2); N3–N8 mức 3. Chi tiết và cách đăng ký: [backlog.html](backlog.html), mục 4.

## 5. Worker Agent (W0–W7)

Workflow LangGraph trong `server/src/app/agent/`. Nhãn bước: `[TĐ]` tất định, `[LLM]` chỉ gợi ý, `[HITL]` dừng chờ BQL, `[RAG]` truy xuất có trích dẫn. Mức 1: W0–W2; mức 2: W3, W4, W5, W7; W6 mức 3. Chi tiết: [backlog.html](backlog.html), mục 5.

## 6. Mức 3 — nếu còn thời gian

Đã có thiết kế; bảng hoãn ở [08-deferred-tables](../03-design/08-deferred-tables.md). Ví dụ: quên mật khẩu, sơ đồ bãi realtime, hoán đổi chỗ (W6, N5), đối soát (N3), KPI chuỗi (N7, N8). Danh sách đủ: [backlog.html](backlog.html), mục 6.
