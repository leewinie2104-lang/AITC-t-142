# 05-development — Hướng dẫn phát triển

> **Thư mục này trả lời:** code nằm ở đâu, thêm tính năng mới vào chỗ nào, chạy và kiểm tra ra sao.

## Tổng quan

Repo là monorepo `client/` + `server/` ([ADR-0001](../10-adr/ADR-0001-monorepo-client-server.md)). Server tổ chức theo module nghiệp vụ, tầng `agent/` điều phối W0–W7, job N1–N8 là delivery adapter ([ADR-0010](../10-adr/ADR-0010-backend-modules-agent-workflows-jobs.md)).

## File

| File | Trả lời câu hỏi |
|---|---|
| [01-server-structure.md](01-server-structure.md) | Cây thư mục `server/`, bên trong một module, quy tắc phụ thuộc, thêm mới ở đâu |

## Lệnh thường dùng (từ gốc repo)

| Lệnh | Việc |
|---|---|
| `make install` | Cài dependency |
| `make run` | Chạy API local |
| `make test` | Chạy pytest trong `server/` |
| `make lint` · `make format` · `make typecheck` | Ruff và mypy |
| `make check` | Lint + test, phải xanh trước khi mở PR |
| `make eval` | Chạy eval, ghi `eval/results/report.md` |

API local: `http://localhost:8000/docs`.

## Skill hỗ trợ (Claude Code / Codex)

| Skill | Dùng khi |
|---|---|
| `new-usecase` | Thêm một thao tác nghiệp vụ hoặc endpoint REST |
| `new-agent-workflow` | Làm hoặc mở rộng workflow W0–W7 |
| `new-background-job` | Thêm job N1–N8 |
| `new-migration` | Đổi bảng, cột, index, RLS |
| `new-prompt` | Thêm hoặc sửa prompt LLM |
| `pre-pr` | Kiểm tra cuối trước khi mở PR |

## Quy tắc chính

- Không import chéo giữa module; chỉ `agent/` gọi use case của nhiều module.
- Rule engine quyết định, LLM chỉ gợi ý (BR-14); ẩn danh tên và biển số trước khi gọi LLM.
- SQL chỉ dùng tham số `$1, $2…`; schema chỉ đổi qua migration.
- Chi tiết: `.claude/rules/backend.md` (Claude Code) hoặc `server/AGENTS.md` (Codex).

## Sẽ thêm vào đây

`02-client-structure.md` khi khởi tạo `client/`; hướng dẫn chạy docker compose local.
