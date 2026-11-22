# 04-development — Hướng dẫn phát triển

> **Thư mục này trả lời:** code nằm ở đâu, thêm tính năng mới vào chỗ nào, chạy và kiểm tra ra sao.

## Tổng quan

Repo là monorepo `client/` + `server/` ([ADR-0001](../07-adr/ADR-0001-monorepo-client-server.md)). Server tổ chức theo module nghiệp vụ, tầng `agent/` điều phối W0–W7, job N1–N9 là delivery adapter ([ADR-0010](../07-adr/ADR-0010-backend-modules-agent-workflows-jobs.md)).

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
| `new-background-job` | Thêm job N1–N9 |
| `new-migration` | Đổi bảng, cột, index, RLS |
| `new-prompt` | Thêm hoặc sửa prompt LLM |
| `pre-pr` | Kiểm tra cuối trước khi mở PR |

## Quy tắc chính

- Không import chéo giữa module; chỉ `agent/` gọi use case của nhiều module.
- Rule engine quyết định, LLM chỉ gợi ý (BR-14); ẩn danh tên và biển số trước khi gọi LLM. Không gửi tọa độ GPS cho LLM, chỉ gửi ETA (BR-27).
- Tiền, phí, OTP, giữ chỗ và tạm ngừng nhận lượt do code và job quyết định, không do LLM (BR-22, BR-24).
- SQL chỉ dùng tham số `$1, $2…`; schema chỉ đổi qua migration.
- Chi tiết: `.claude/rules/backend.md` + `backend-*.md` (Claude Code, tự nạp theo đường dẫn) hoặc `server/AGENTS.md` (Codex).

## Auth (SCRUM-86, ADR-0006)

- `POST /api/v1/auth/login` (phone + password) trả JWT ES256 8 giờ; `GET /api/v1/me` trả hồ sơ + tư cách của người gọi.
- Router cần biết người gọi: nhận `current_user` từ `app.platform.auth.dependency.make_current_user(tokens)` (dựng ở
  `main_api.py`), rồi truyền vào `unit_of_work` để RLS có ngữ cảnh:

  ```python
  async def endpoint(user: CurrentUser = Depends(current_user)):
      async with unit_of_work(user_id=user.user_id, role=user.role, zone_ids=user.zone_ids) as conn: ...
  ```

- Thiếu / sai / hết hạn token -> 401 `WWW-Authenticate: Bearer`. Khóa: `JWT_PRIVATE_KEY` / `JWT_PUBLIC_KEY` (PEM);
  dev / test không đặt thì dùng khóa tạm theo tiến trình, production bắt buộc có.
- Việc tiếp theo: các router booking / agreement còn đọc `X-User-Id` / `X-Role` từ header (client tự khai) và sẽ được
  chuyển sang `current_user` trong PR riêng.

## Kiểm thử (gộp từ thư mục `06-testing` cũ)

| Tầng | Thư mục | Ghi chú |
|---|---|---|
| Unit | `server/tests/unit/<module>/` | Port giả, không DB / LLM / mạng; bảng quy tắc L1–L4 × phạm vi × TH1/TH2/TH3 viết bằng `@pytest.mark.parametrize` |
| Agent | `server/tests/unit/agent/` | Patch `get_llm`, không gọi model thật |
| Tích hợp | `server/tests/integration/` | Postgres thật (local `docker compose up -d postgres`), `@pytest.mark.integration` |
| Eval | `eval/datasets/*.jsonl` | **≥45 case trước Demo Day** (phân bổ ở [backlog W](../01-product/05-backlog.md#2-tính-năng)); BTC chấm `eval/results/report.md`; CI `python3 eval/run_eval.py --strict` |

Mỗi AC trong [04-user-stories](../01-product/04-user-stories.md) nên có ít nhất một test hoặc eval case. API: OpenAPI sinh từ code tại `/docs` (ADR-0003).

## MCP và test API (plan 025)

`.mcp.json` ở gốc repo khai báo MCP dùng chung cho Claude Code; lần đầu mở, gõ `/mcp` để duyệt từng server.

| Server | Việc | Cần trên máy bạn |
|---|---|---|
| `codebase-memory-mcp` | Đồ thị code: tìm symbol, ai gọi ai, kiến trúc | Cài binary `codebase-memory-mcp`; lần đầu: nhờ Claude `index_repository` |
| `postgres` | SQL **chỉ đọc** (`postgres-mcp --access-mode=restricted`) lên DB dev dùng chung, role `parksmart_app` (có RLS) | `uv`, Tailscale bật, `DATABASE_URL` đúng trong `.env` |
| `redis` | Xem key / queue arq trên Redis dev (DB index trong `REDIS_URL` của bạn) | `uv`, Tailscale bật, `REDIS_URL` đúng trong `.env` |
| `atlassian` | Jira / Confluence | Đăng nhập Atlassian (OAuth) |

- `postgres` / `redis` chạy qua `scripts/mcp_server.py`: đọc URL từ `.env` của bạn, truyền qua biến môi trường, không
  ghi secret vào git. Cài `uv`: `pip install --user uv` hoặc xem docs.astral.sh/uv. Ngoài giờ bật máy CI thì hai server này lỗi kết nối.
- Redis MCP có lệnh ghi (set / delete): chỉ dùng để xem, không xóa key của queue `bg` / agent.
- **Test API thủ công**: dùng OpenAPI sinh từ code, không dùng Postman (gói team mất phí). `make run` → mở
  `http://localhost:8000/docs`, gọi `POST /api/v1/auth/login` với tài khoản seed (SĐT ở
  [demo_seed](../../server/src/demo_seed/README.md), mật khẩu `SEED_DEMO_PASSWORD` trong Bitwarden), rồi ở endpoint cần
  đăng nhập (`/me`, `/me/vehicles`) điền ô `authorization` = `Bearer <access_token>` (chưa có nút Authorize vì API chưa
  khai báo security scheme). Endpoint khác nhận `x-user-id` / `x-zone-id` / `x-role` ngay trong form. Spec thô: `/openapi.json` (import được vào Bruno / Insomnia nếu cần).

## Sẽ thêm vào đây

`02-client-structure.md` khi khởi tạo `client/`. Môi trường dev (DB / Redis dùng chung, Tailscale, `.env`): [infra/dev-db](../../infra/dev-db/README.md) và `.env.example`.
