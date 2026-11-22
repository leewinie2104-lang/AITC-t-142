# RAG kho tri thức (W7 hỏi đáp nội quy)

> Dữ liệu và prototype: [server/knowledge_base/](../../server/knowledge_base/README.md) ·
> Bảng đích: [`knowledge_chunk`](../03-design/dictionary/08-agent-knowledge.md) ·
> Workflow: [W7 trong backlog](../01-product/05-backlog.md#2-tính-năng) · Code sẽ ở `server/src/app/knowledge/`

## 1. Trạng thái

Có **prototype trong notebook** (`rag_prototype.ipynb`), chạy bộ nhớ, chưa nối vào app. Module
`knowledge/` mới có khung thư mục (`.gitkeep`). Mục 5 liệt kê việc cần làm để đưa vào app.

## 2. Kho tài liệu (15 file, 7 nhóm)

| Thư mục `sources/` | `domain` | `sub_domain` | File |
|---|---|---|---|
| Pháp lý & Quy định nhà nước | `legal_policy` | `state_law` | TT 24 BGTVT, giá dịch vụ trông giữ, QCVN gara ô tô, PCCC bãi xe, Luật TTATGT đường bộ |
| Hợp đồng | `legal_policy` | `contract_template` | 2 mẫu hợp đồng giữ xe |
| Bảng giá & Chính sách thương mại | `commercial_cs` | `pricing_policy` | Bảng giá đỗ ô tô HN / TP.HCM (.xlsx) |
| Chính sách thanh toán & Dịch vụ | `commercial_cs` | `billing_refund` | Quy chế quản lý, thanh toán |
| Nội quy BQL & Chủ đầu tư | `operations_sop` | `building_rules` | 3 nội quy bãi xe, thẻ từ |
| Nghiệp vụ xử lý sự cố (SOP & FAQ) | `operations_sop` | `incident_sop` | Cẩm nang sự cố & kịch bản CSKH (.pdf) |
| Tiêu chuẩn kỹ thuật & Hạ tầng | `technical_infra` | `technical_spec` | QCVN 07-11:2025, tài liệu kỹ thuật |

Kết quả: **564 chunk** — `legal_policy` 388, `operations_sop` 64, `technical_infra` 59,
`commercial_cs` 53. Riêng Luật TTATGT chiếm ~326 nghìn ký tự, phần lớn chunk pháp lý.

## 3. Pipeline trong notebook

| Bước | Việc | Đầu ra |
|---|---|---|
| 1 Quét | Duyệt `sources/`, gán `domain` theo tên thư mục | `processed/manifest.csv` |
| 2 Bóc tách | `.docx` python-docx (giữ bảng dạng Markdown); `.pdf`/`.doc` PyMuPDF, dự phòng docx rồi lọc HTML; `.xlsx` pandas, mỗi dòng thành `cột: giá trị` | `processed/parsed_documents.jsonl` |
| 3 Chia chunk | Văn bản pháp lý / nội quy / thanh toán: tách theo `Điều`, `Chương`, `PHẦN`; còn lại tách theo heading. Tối đa 1 800 ký tự, chồng 250; thêm tiền tố `[Nguồn: … \| Nhóm: …]` | `processed/chunks_v1.jsonl` |
| 4 Gắn metadata | `city` = HN / HCM / ALL theo từ khóa trong chunk (Vành đai, Thủ Đức…) | trong `metadata` |
| 5 Truy xuất | Lai: `0.55 × BM25 (chuẩn hóa) + 0.45 × cosine TF-IDF (1–2 gram)` + **0.15** nếu khớp `domain` dự kiến; lọc `city ∈ {city, ALL}` | top-k chunk |
| 6 Trả lời | Ghép top-3 vào prompt "chỉ dùng tài liệu, luôn trích nguồn, không có thì nói chưa có dữ liệu"; gọi Gemini, temperature 0.2 | câu trả lời + nguồn |

Kiểm thử thủ công 4 câu (giá tháng ô tô Vành đai I HN, mất thẻ từ, trách nhiệm bồi thường,
quy chuẩn kỹ thuật): top-1 đều đúng nhóm tài liệu. Chưa có eval case tự động.

## 4. Lệch so với kiến trúc đã chốt

| Prototype | Kiến trúc | Xử lý khi đưa vào app |
|---|---|---|
| Gemini qua `google-genai` | Claude qua Bedrock, mọi lần gọi qua `platform/llm` ([ADR-0007](../07-adr/ADR-0007-claude-via-amazon-bedrock.md)) | Thay bằng `get_llm()`; prompt chuyển vào `server/prompts/` (skill `new-prompt`) |
| Index BM25 / TF-IDF trong RAM | `knowledge_chunk.embedding vector(1024)` trên pgvector ([ADR-0005](../07-adr/ADR-0005-rds-postgres-asyncpg-rls-alembic-sql.md)) | Ingest `chunks_v1.jsonl` → bảng; có thể giữ BM25 làm điểm phụ (cần quyết định, ADR nếu đổi) |
| Lọc theo `city` | Lọc theo `zone_id` / `building_id`, RLS theo khu | Tài liệu chung (luật, QCVN) để `zone_id` NULL; nội quy riêng gắn khu demo |
| `domain`, `sub_domain`, `chunk_id` | Bảng chỉ có `doc_title`, `source_uri`, `doc_version`, `ordinal`, `content` | Thêm cột `domain` qua migration, hoặc bỏ soft boost |
| Trả lời tự do | W7 phải kiểm tra không hứa thay rule engine: không cam kết giá, quyền thuê (BR-14) | Bước `[TĐ]` sau LLM; giá lấy từ `zone_policy`, không lấy từ bảng giá tham khảo |

Bảng giá HN / TP.HCM là **giá thị trường tham khảo**, không phải giá của khu demo; câu trả
lời về phí của ParkSmart phải lấy từ rule engine.

## 5. Việc tiếp theo (W7, tuần 3)

- [ ] `knowledge/domain`: entity `KnowledgeChunk`, port `ChunkRepository`, `EmbeddingPort`.
- [ ] `knowledge/usecase`: `ingest_chunks` (đọc `processed/chunks_v1.jsonl`), `search_chunks(query, zone_id, building_id, k)`.
- [ ] `knowledge/infrastructure/postgres`: SQL asyncpg tham số `$1…`, lọc `is_active`.
- [ ] `agent/workflows/w7_*`: phân loại câu hỏi → truy xuất → trả lời kèm trích dẫn → kiểm tra BR-14.
- [ ] Eval: chuyển 4 câu thử ở mục 3 thành case trong `eval/datasets/` (skill `eval-case`), thêm case "không có dữ liệu".
