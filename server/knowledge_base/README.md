# knowledge_base — kho tài liệu cho W7 (RAG nội quy)

Dữ liệu nguồn và prototype RAG, **chưa phải code chạy trong app**. Code thật đặt ở module
`src/app/knowledge/` (ADR-0010), lưu vào bảng `knowledge_chunk` (pgvector). Thiết kế và
khoảng cách với kiến trúc: [docs/08-ai/02-rag-knowledge-base.md](../../docs/08-ai/02-rag-knowledge-base.md).

## Cấu trúc

```
sources/     15 tài liệu gốc (.doc/.docx/.pdf/.xlsx/.md), 7 thư mục theo nhóm nghiệp vụ
processed/   file sinh ra từ notebook, không sửa tay
  manifest.csv            bước 1: danh sách file, domain, dung lượng
  parsed_documents.jsonl  bước 2: văn bản bóc tách (raw_markdown, char_count)
  chunks_v1.jsonl         bước 3: 564 chunk + metadata, đầu vào cho ingest
notebooks/   rag_prototype.ipynb: bóc tách → chia chunk → BM25 + TF-IDF → trả lời bằng LLM
```

Tên thư mục trong `sources/` là khóa ánh xạ `domain` / `sub_domain` trong notebook; đổi tên
thì phải sửa `DOMAIN_MAPPING` và `sub_domain_map`.

## Định dạng chunk (`processed/chunks_v1.jsonl`)

```json
{"chunk_id": "LEGAL_POLICY_1a2b3c4d",
 "text": "[Nguồn: <file> | Nhóm: <thư mục>]\n<nội dung>",
 "metadata": {"domain": "legal_policy", "sub_domain": "state_law", "folder_name": "...",
              "source_file": "...", "city": "HN|HCM|ALL", "chunk_index": 1,
              "total_chunks": 12, "status": "active"}}
```

## Chạy lại notebook

```bash
cd server/knowledge_base/notebooks
pip install pandas openpyxl python-docx pymupdf rank-bm25 scikit-learn google-genai jupyter
export GEMINI_API_KEY=...        # chỉ cần cho ô gọi LLM (bước 4)
jupyter notebook rag_prototype.ipynb
```

- Thư viện notebook **không** có trong `server/requirements.txt`, cài riêng trong venv.
- `file_path` trong `processed/` vẫn ghi `data\...` (đường dẫn cũ, sinh trên Windows); chạy lại
  notebook sẽ ghi đường dẫn mới. `chunk_id` sinh ngẫu nhiên nên mỗi lần chạy sẽ khác.
- Gốc repo `.gitignore` bỏ qua thư mục tên `data/` và `build/`, nên dùng `sources/` và `processed/`.

## Thêm tài liệu

1. Đặt file vào đúng thư mục nhóm trong `sources/` (thư mục mới thì thêm vào hai map nói trên).
2. Chạy lại notebook, kiểm tra số chunk theo `domain` ở ô cuối bước 3.
3. Không đưa tài liệu có dữ liệu cá nhân thật (tên, SĐT, biển số) vào `sources/`.
