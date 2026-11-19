# 08-ai — AI trong dự án

> **Thư mục này trả lời:** hai việc liên quan AI: (1) công cụ AI hỗ trợ đội viết code được cấu hình thế nào; (2) Agent ParkSmart được thiết kế ra sao ở mức graph, prompt và eval.

## Tổng quan

| Phần | Trạng thái |
|---|---|
| Cấu hình Claude Code và Codex cho đội | Có: [01-agent-setup.md](01-agent-setup.md) (tiếng Anh) |
| RAG kho tri thức W7 | Prototype notebook: [02-rag-knowledge-base.md](02-rag-knowledge-base.md); dữ liệu ở `server/knowledge_base/` |
| Thiết kế Agent ParkSmart (W0–W7) | Chưa có; yêu cầu nghiệp vụ ở [backlog/02-agent-workflows](../01-product/backlog/02-agent-workflows.md) |

## File

| File | Trả lời câu hỏi |
|---|---|
| [01-agent-setup.md](01-agent-setup.md) | Claude Code (`.claude/`, `CLAUDE.md`) và Codex (`.codex/`, `AGENTS.md`, `.agents/skills/`) được cấu hình song song thế nào; hook ghi log; cài đặt theo hệ điều hành |
| [02-rag-knowledge-base.md](02-rag-knowledge-base.md) | Kho 15 tài liệu, pipeline bóc tách → chunk → truy xuất lai BM25 + TF-IDF, lệch so với ADR và việc cần làm cho W7 |

## Agent ParkSmart: đang ở đâu

| Thành phần | Vị trí |
|---|---|
| Graph W0–W7 | `server/src/app/agent/` |
| Prompt | `server/prompts/*.md` (dạng `{{placeholder}}`), nạp qua `app.platform.prompts.loader` |
| RAG nội quy (W7) | Code: `server/src/app/knowledge/` (chưa có); dữ liệu, notebook: `server/knowledge_base/` |
| Guardrail, ẩn danh | `server/src/app/agent/infrastructure/` |
| Eval | `eval/` ở gốc repo, ≥45 case trước Demo Day |
| LLM | Claude qua Bedrock ([ADR-0007](../07-adr/ADR-0007-claude-via-amazon-bedrock.md)); local chạy mock |

Nguyên tắc: rule engine quyết định, LLM chỉ gợi ý (BR-14); BQL của khu có ô duyệt các bước HITL (BR-18).

## Nên có

| File gợi ý | Nội dung |
|---|---|
| `03-agent-graphs.md` | State, node, cạnh của W0–W3, W7; chỗ `interrupt()` cho HITL |
| `04-prompts.md` | Danh sách prompt, đầu vào, schema đầu ra, cách kiểm tra |
| `05-eval.md` | Phân bổ case, rubric judge, ngưỡng, cách đọc report |

Skill hỗ trợ: `new-agent-workflow`, `new-prompt`, `eval-case`. Tài liệu mới về AI tooling viết tiếng Anh; thiết kế Agent viết tiếng Việt như phần còn lại của `docs/`.
