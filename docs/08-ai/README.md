# 08-ai — AI trong dự án

> **Thư mục này trả lời:** hai việc liên quan AI: (1) công cụ AI hỗ trợ đội viết code được cấu hình thế nào; (2) Agent ParkSmart được thiết kế ra sao ở mức graph, prompt và eval.

## Tổng quan

| Phần | Trạng thái |
|---|---|
| Cấu hình Claude Code và Codex cho đội | Có: [01-agent-setup.md](01-agent-setup.md) (tiếng Anh) |
| RAG kho tri thức W7 | Prototype notebook: [02-rag-knowledge-base.md](02-rag-knowledge-base.md); dữ liệu ở `server/knowledge_base/` |
| Thiết kế Agent ParkSmart (W0–W7) | Chưa có; yêu cầu nghiệp vụ ở [05 Backlog, cột Worker Agent](../01-product/05-backlog.md#2-tính-năng) |

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
| LLM | Dev: Groq ([ADR-0013](../07-adr/ADR-0013-dev-env-on-ci-runner-and-groq.md)); demo dự kiến Claude qua Bedrock ([ADR-0007](../07-adr/ADR-0007-claude-via-amazon-bedrock.md)); unit test và CI dùng mock |

Nguyên tắc: rule engine quyết định, LLM chỉ gợi ý (BR-14); BQL chỉ xem ca xấu (BR-26), không duyệt từng lượt.

### Agent role, pilot one building (final, 2026-11-22)

- **Goal:** get the waiting renter into a space as fast as possible without breaking any rule. The agent only
  proposes and assesses risk; it never confirms money, fees, hold timers or closures (BR-14, BR-22, BR-24).
- **Tools:** look up the waiting queue; look up share windows; read gate events; compute ETA (`TravelTimeProvider` port,
  mock in dev/CI/demo); check rules; assess risk; propose assignment; send renter OTP; notify; alert guard;
  hand the case to BQL.
- **Send the ETA only, never coordinates.** GPS is used for priority and assignment timing, never for
  space confirmation or billing (BR-27).
- **History** (past overstays, early returns, disputes) is read only when several spaces open at once, or to escalate a
  case to BQL. It is never used to make a waiting renter wait longer.
- **AI only tightens, never loosens:** AI cannot pass a case that the rule engine has rejected (BR-26).
  Normal cases are auto-approved; suspicious cases go to BQL with reasons and evidence; a BQL case
  unanswered after 10 minutes is treated as rejected.
- **Disputes:** the agent builds a sourced timeline; BQL decides.
- **Pilot metrics** (see [ADR-0015](../07-adr/ADR-0015-renter-gps-eta-otp-and-two-layer-approval.md) and [06 Operations](../06-operations/README.md)):
  wait time until a space is offered; first-try match rate; no-OTP / no-show rate; ETA gap (ETA at assignment vs camera entry);
  rate of "no space left" notices before arrival; self-handled rate (auto-approve + auto-reject, target >= 95%);
  BQL-escalated cases BQL agrees were bad; no-show rate on TH3 holds; BQL time on bad cases; dispute dossier build time.

## Nên có

| File gợi ý | Nội dung |
|---|---|
| `03-agent-graphs.md` | State, node, cạnh của W0–W3, W7; chỗ `interrupt()` cho HITL |
| `04-prompts.md` | Danh sách prompt, đầu vào, schema đầu ra, cách kiểm tra |
| `05-eval.md` | Phân bổ case, rubric judge, ngưỡng, cách đọc report |

Skill hỗ trợ: `new-agent-workflow`, `new-prompt`, `eval-case`. Tài liệu mới về AI tooling viết tiếng Anh; thiết kế Agent viết tiếng Việt như phần còn lại của `docs/`.
