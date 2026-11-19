# Từ điển dữ liệu — Agent, kiểm toán AI, tri thức, view (M14, W7)

> Thuộc [từ điển dữ liệu](../03-data-dictionary.md). Ràng buộc, index, giá trị enum: [sql/schema.sql](../sql/schema.sql).

## Agent và kiểm toán AI (M14)

### agent_thread

Một dòng mỗi thread LangGraph (M14): ai nói chuyện với Agent, workflow nào (W0–W7), đang chờ ở đâu. State của graph nằm trong checkpointer (schema `agent`). Không lưu tin nhắn gốc (BR-14, D-12); `pending_card` chỉ là thẻ xác nhận đã ẩn danh. Thay vai trò của `workflow_run` đã bỏ.  
RLS: **có** (policy: `owner`, `system_all`, `zone_manager_read`)

| Cột | Kiểu | Null | Mặc định | Ý nghĩa |
|---|---|---|---|---|
| `thread_id` | text | no |  | Khóa chính; bằng thread id của LangGraph (1–200 ký tự). |
| `user_id` | uuid | no |  | Người sở hữu hội thoại. → `app_user`. |
| `zone_id` | uuid | yes |  | Khu của ô sau khi thread được định tuyến; NULL trước đó. → `zone`. Giúp BQL khu thấy thread `awaiting_manager`. |
| `workflow` | app.workflow_code | no |  | Workflow chạy trong thread: W0 … W7 (enum `workflow_code`). |
| `status` | app.thread_status | no | 'active'::thread_status | `active` · `awaiting_user` · `awaiting_manager` · `completed` · `failed`. |
| `pending_card` | jsonb | yes |  | Thẻ xác nhận đã ẩn danh hiển thị cho người dùng hoặc BQL (JSON object; NULL khi không có gì chờ). Không tên, số điện thoại, biển số (D-12). |
| `created_at` | timestamp with time zone | no | now() | Thời điểm tạo (UTC). |
| `updated_at` | timestamp with time zone | no | now() | Lần cập nhật cuối (trigger `set_updated_at`). |

### ai_decision_log

Nhật ký chỉ ghi thêm, một dòng mỗi bước quyết định hoặc gợi ý của AI, cho màn hình kiểm toán của BQL và yêu cầu kiểm toán của ban tổ chức. Chỉ hash và id: không prompt, đầu ra hay user id gốc (BR-14). Bổ sung, không thay trace OTel (ADR-0008). MVP không có job xóa.  
RLS: **có** (policy: `system_all`, `zone_manager_read`)

| Cột | Kiểu | Null | Mặc định | Ý nghĩa |
|---|---|---|---|---|
| `id` | bigint | no | identity | Khóa chính (identity). |
| `thread_id` | text | yes |  | Thread LangGraph của bước; NULL nếu bước nằm ngoài thread. → `agent_thread`. |
| `zone_id` | uuid | yes |  | Khu mà quyết định liên quan. → `zone`. Dùng cho policy đọc của BQL. |
| `user_hash` | bytea | no |  | HMAC-SHA256 (32 byte) của user id; không lưu id gốc. |
| `workflow` | app.workflow_code | no |  | Workflow của bước (W0 … W7). |
| `step` | text | no |  | Tên node trong graph. |
| `model_version` | text | yes |  | Định danh model; NULL với bước tất định (rule engine). |
| `input_hash` | bytea | no |  | SHA-256 đầu vào của bước (32 byte). |
| `output_hash` | bytea | no |  | SHA-256 đầu ra của bước (32 byte). |
| `risk_level` | app.ai_risk_level | no |  | `low` · `medium` · `high`. |
| `outcome` | app.ai_outcome | no |  | `suggested` · `auto_applied` · `blocked_by_rule` · `sent_to_human` · `failed` · `degraded`. |
| `human_approved` | boolean | yes |  | NULL = không cần duyệt; true / false = quyết định của người. |
| `approval_request_id` | uuid | yes |  | Lượt duyệt đã chặn bước này. → `approval_request`. |
| `trace_id` | text | yes |  | Trace id OTel, để mở trong Tempo. |
| `latency_ms` | integer | yes |  | Thời gian chạy của bước, mili giây (≥ 0). |
| `idempotency_key` | text | no |  | `thread_id:checkpoint_id:node` (ADR-0010): node chạy lại sau `interrupt()` hoặc retry chỉ ghi quyết định một lần. |
| `created_at` | timestamp with time zone | no | now() | Thời điểm tạo (UTC). |

## Kho tri thức (W7)

### knowledge_chunk

Đoạn tài liệu nội quy cho RAG, theo khu / tòa, kèm metadata tài liệu + `embedding vector(1024)` (pgvector). Quét chính xác; ở quy mô này không cần index ANN.  
RLS: **có** (policy: `manage_zone`, `read_authenticated`)

| Cột | Kiểu | Null | Mặc định | Ý nghĩa |
|---|---|---|---|---|
| `id` | uuid | no | uuid_v7() | Khóa chính (UUIDv7, trừ khi kiểu là bigint). |
| `zone_id` | uuid | yes |  | Khu sở hữu; dùng cho RLS. Khớp với cha qua FK ghép. |
| `building_id` | uuid | yes |  | Phạm vi tòa, tùy chọn; NULL = cả khu. |
| `doc_title` | text | no |  | Tiêu đề tài liệu nguồn của đoạn này. |
| `source_uri` | text | no |  | Vị trí tài liệu nguồn (URI hoặc đường dẫn); cùng `doc_version` và `ordinal` xác định đoạn. |
| `doc_version` | integer | no | 1 | Phiên bản tài liệu nguồn, tăng dần; bản cũ giữ lại và tắt bằng `is_active`. |
| `is_active` | boolean | no | true | False khi phiên bản tài liệu bị thay hoặc ngừng dùng; truy xuất chỉ đọc đoạn đang active. |
| `ordinal` | integer | no |  | Như tên cột. |
| `content` | text | no |  | Nội dung đoạn được truy xuất cho câu trả lời W7. |
| `created_at` | timestamp with time zone | no | now() | Thời điểm tạo (UTC). |

## View

### kpi_daily_v

Kết quả yêu cầu, phí quá giờ và tranh chấp theo ngày và khu cho dashboard KPI (thay bảng `kpi_daily` của v2). Gom `parking_request`, `payment` (`overstay_fee` đã trả) và `dispute_case`, nhóm theo `zone_id` và ngày địa phương; một dòng cho mỗi (khu, ngày) có ít nhất một yêu cầu, phí hoặc tranh chấp.  
Tùy chọn: `security_barrier = true`

| Column | Type | Meaning |
|---|---|---|
| `zone_id` | uuid | Khu của các yêu cầu. |
| `day` | date | Ngày làm việc địa phương: `(created_at AT TIME ZONE zone.timezone)::date`. |
| `requests_total` | bigint | Mọi yêu cầu đỗ xe trong ngày. |
| `matched` | bigint | Yêu cầu có kết quả `matched`. |
| `redirected_th3` | bigint | Yêu cầu có kết quả `redirected_th3`. |
| `redirected_public` | bigint | Yêu cầu có kết quả `redirected_public`. |
| `blocked` | bigint | Yêu cầu có kết quả `blocked`. |
| `no_match` | bigint | Yêu cầu có kết quả `no_match`. |
| `overstay_fees` | bigint | v5: tổng phí quá giờ đã thu trong ngày (VND, payment `paid_simulated`; khoản được miễn là `cancelled` nên không tính). |
| `disputes_opened` | bigint | v5: số hồ sơ tranh chấp mở trong ngày. |
| `dispute_prep_minutes_avg` | numeric | v5: số phút trung bình từ tạo đến `ready_at` (thời gian lập hồ sơ); NULL nếu không có hồ sơ nào đủ trong ngày. |

Sáu số đầu của yêu cầu là 0 khi ngày chỉ có phí hoặc tranh chấp. Bộ lọc dòng trong view: `app.ctx_role() = 'chain_operator' OR (app.ctx_role() IN ('zone_manager','system') AND zone_id = ANY (app.ctx_zone_ids()))`. Vận hành chuỗi thấy mọi khu, BQL (hoặc vai trò system) chỉ thấy khu trong ngữ cảnh, cư dân hoặc bảo vệ không thấy dòng nào. View chạy với quyền owner có chủ đích: chỉ lộ số liệu tổng hợp (PRD §9), không bao giờ lộ dòng `parking_request`. `parksmart_readonly` được cấp `zone` và `kpi_daily_v`.
