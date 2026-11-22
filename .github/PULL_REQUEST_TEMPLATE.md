<!--
Tiêu đề PR theo Conventional Commits, scope là module hoặc khu vực:
  feat(booking): add hold-slot use case · fix(agent): ... · chore(infra): ...
PR nhắm vào `dev` (`main` chỉ dùng cho release).
-->

## Ticket

<!-- Mã Jira, ví dụ SCRUM-25. Ghi thêm backlog / BR / AC liên quan nếu có (M5, W2, BR-14, AC-03...). -->

## Thay đổi gì

<!-- Mô tả ngắn: làm gì và vì sao. Nhóm theo khu vực nếu PR đụng nhiều chỗ. Nếu sửa Technical Book, ghi rõ chương nào và vì sao. -->

### ⚠️ Thay đổi cách dùng

<!-- Lệnh, API, biến môi trường, schema DB... mà người khác phải làm khác đi sau khi merge. Không có thì ghi "Không". -->

## Cách kiểm tra

<!-- Lệnh / bước để reviewer tự kiểm. Ví dụ:
    make check
    make up PROFILE=app && make start
    curl http://localhost:8000/api/v1/health
-->

## Loại thay đổi

- [ ] `feat` — tính năng mới
- [ ] `fix` — sửa lỗi
- [ ] `docs` — **nội dung Technical Book** (`docs/guide/**`) → cần review của @AI20K-Build-Phase/book-maintainers
- [ ] `chore` / `refactor` / `test`

## Checklist

**Chung**
- [ ] `make check` xanh (ruff + mypy + pytest — CI chạy đúng lệnh này)
- [ ] **Không có API key / token / credential** trong diff (kể cả `.env.example`)
- [ ] Có plan trong `.claude/plans/` (với việc lớn) và đã cập nhật **Status**

**Backend** — bỏ qua nếu không đụng `server/`
- [ ] Đúng layer theo ADR-0010, không import chéo module (`check_arch` chạy trong `make check`)
- [ ] Đổi schema → có migration Alembic (SQL thuần, RLS theo khu); SQL chỉ dùng tham số `$1, $2…`
- [ ] Không có PII (tên, biển số…) trong log, span attribute, metric label
- [ ] Có test cho use case / business rule mới (BR-xx / AC-xx)

**Agent / LLM** — bỏ qua nếu không đụng agent, prompt, guardrail
- [ ] Rule engine quyết định, LLM chỉ gợi ý (BR-14)
- [ ] Prompt nằm trong `server/prompts/*.md`, không viết inline
- [ ] Đã chạy `make eval`, không có regression

**Hạ tầng** — bỏ qua nếu không đụng Docker / CI
- [ ] Đụng `server/Dockerfile` / `docker-compose.yml`: đã chạy `make build` + `make up` + `make start` ở local
- [ ] Đụng `.github/workflows/`: job dùng `runs-on: self-hosted` (runner GitHub bị chặn do hạn mức của org)

**Tài liệu**
- [ ] Quyết định kiến trúc mới / đổi thư viện → có ADR trong `docs/07-adr/`
- [ ] Đổi API / lệnh chạy → đã cập nhật README hoặc docs liên quan
- [ ] Nếu đụng `docs/guide/**`: đã kiểm tra nội dung hiển thị đúng và link không chết

## Chưa làm / để sau

<!-- Việc còn thiếu, giới hạn đã biết, ticket tiếp theo. Không có thì xoá mục này. -->

<!--
Nhắc: nội dung docs/guide/ merge vào main sẽ được đồng bộ lên
https://phoenix.note.transformerlabs.ai/technical-book
-->
