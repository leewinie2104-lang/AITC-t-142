# PROJECT_CONTEXT.md (C5)

> Inspire team 001 (Memio) — Quick Rehydrate + Current Invariants.
> Đây là file agent đọc ĐẦU TIÊN khi resume session. Giữ < 60 giây để đọc.

## 0. Quick Rehydrate (≤ 60s)

- **Project**: ParkSmart AI — chia sẻ và đặt chỗ đỗ xe cho chuỗi khu đô thị, có AI Agent hỗ trợ.
- **Stack**: Python 3.11 / FastAPI / LangGraph / Postgres / Redis (arq); client React + Vite.
- **Dev**: `make run` (backend, chạy trong `server/`); client chưa khởi tạo.
- **Test**: `make test`. **Eval**: `python eval/run_eval.py`.
- **Env**: copy `.env.example` → `.env`, thêm `OPENAI_API_KEY` (optional — mock-first).

## 0.1 Current Invariants (để không drift)

- **Source of truth kỹ thuật**: code trong `server/src/app/`. File `.md` chỉ tóm tắt — khi mâu thuẫn,
  **CODE WINS**. Inspire team 011 source-of-truth rule.
- **Cấu trúc**: module Clean Architecture + `agent/` điều phối W0–W7 + job nền N1–N8 (ADR-0010, `docs/05-development/01-server-structure.md`).
- **Prompts**: `server/prompts/*.md` (external, `{{placeholder}}`).
- **Safety**: `server/src/app/agent/infrastructure/guardrails.py`; rule engine quyết định, LLM chỉ gợi ý (BR-14).

## 0.2 Known Ambiguities / Mismatches (inspire team 011)

Liệt kê chỗ doc-vs-code lệch để agent không tin doc stale:
- [team điền khi phát hiện mismatch, vd: "PRD nói dùng Gemini nhưng code đang OpenAI"]

## 1. Quyết định kỹ thuật (link ADR)

Xem `docs/10-adr/` (ADR-0001 → ADR-0010). Mỗi quyết định lớn ghi theo format:
`[ADR-XXX] Context / Options / Decision / Consequences` (inspire team 010).

## 2. Cập nhật file này

Khi đổi stack/invariant → UPDATE FILE NÀY TRƯỚC, rồi mới sửa code. File này là contract
giữa các session agent.
