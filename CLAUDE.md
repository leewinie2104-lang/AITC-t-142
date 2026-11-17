# CLAUDE.md — Project context cho Claude Code

## Quick Rehydrate (≤ 60s)

- **Đây là**: ParkSmart AI — chia sẻ và đặt chỗ đỗ xe cho chuỗi khu đô thị, có AI Agent hỗ trợ.
  Repo sinh từ AI20K Agent Template của BTC; code demo của template đã được dọn (plan 007).
- **Stack**: Python 3.11, FastAPI, LangGraph 1.x, Pydantic v2; Postgres + Redis (arq). Xem
  [docs/02-architecture/tech-stack.md](docs/02-architecture/tech-stack.md) và [docs/10-adr/](docs/10-adr/).
- **Code server**: `server/src/app/`. Cấu trúc: [docs/05-development/server-structure.md](docs/05-development/server-structure.md).
- **Chạy server**: `make run` → http://localhost:8000/docs (health: `/api/v1/health`)
- **Chạy test**: `make test` · **Lint**: `make lint` · **Eval**: `make eval`
- **Mock-first**: test và eval chạy được không cần API key.

## Current Invariants (để không drift)

- **Source of truth**: code trong `server/src/app/`. Khi tài liệu và code mâu thuẫn, CODE WINS.
- **Kiến trúc (ADR-0010)**:
  - Mỗi module (`identity/`, `sharing/`, `booking/`…) có `domain/ usecase/ delivery/ infrastructure/`.
  - Module không import module khác; cần dữ liệu thì khai báo port trong `domain/ports.py`.
  - Chỉ `agent/` được gọi usecase của nhiều module (workflow W0–W7).
  - Job nền N1–N8 nằm ở `<module>/delivery/jobs/`, không gọi LLM.
- **Rule engine quyết định, LLM chỉ gợi ý** (BR-14). Mọi lần gọi LLM qua `platform/llm`.
- **Prompts**: `server/prompts/*.md`, nạp bằng `app.platform.prompts.loader`. Không nhúng prompt dài trong code.
- **Guardrail**: `app/agent/infrastructure/guardrails.py` (chặn prompt injection, lộ key, sai schema).
- **Eval** ở gốc repo (`eval/`), vì BTC chấm `eval/results/report.md`.
- **Logging hooks**: `.claude/.cursor/.codex/.gemini/.agents/.github/hooks` tự ghi prompt vào
  `.ai-log/`. KHÔNG tắt, KHÔNG bypass `--no-verify`.
- **Folder mới** luôn có `.gitkeep`.

## Commands hay dùng

```bash
make install       # pip install -r server/requirements.txt
make run           # uvicorn app.main_api:app (trong server/)
make test          # pytest (server/tests)
make lint          # ruff check
make eval          # eval/run_eval.py → eval/results/report.md
docker compose up  # api + postgres + redis
```

## Thư mục gốc

```
server/         code backend (src/app, tests, prompts, migrations, Dockerfile)
client/         React + Vite SPA (ADR-0002) — chưa khởi tạo
infra/          Terraform (ADR-0009) — chưa khởi tạo
eval/           eval harness + report (deliverable #10)
docs/           tài liệu sản phẩm, kiến trúc, ADR; docs/guide là guidebook của BTC
presentation/   pitch deck, video demo
scripts/        hook ghi log AI của BTC + check_docs.py
```
