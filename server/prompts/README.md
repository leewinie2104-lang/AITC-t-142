# Prompts — external file pattern (C2)

Thư mục này chứa prompt dưới dạng `.md` file tách khỏi code (inspire team 004 —
`prompts/*.md` với `{{placeholder}}`). Lợi ích:

- Đổi prompt KHÔNG cần sửa code / deploy lại.
- Copywriter / mentor review được prompt mà không cần đọc Python.
- Diff history rõ ràng trên git.

## Cấu trúc

- `system_prompt.md` — system prompt đầy đủ, XML tags (`<role>` / `<context>` /
  `<instructions>` / `<rules>` / `<safeguards>` / `<output_format>` /
  `<verification>`). Inspire team 002, 004, 007.
- `safeguards.md` — quy tắc an toàn tách bạch khỏi personality (inspire team 005).
- `citation_rules.md` — contract citation với frontend (inspire team 006).

## Placeholder

Dùng `{{tên_biến}}` — `server/src/app/platform/prompts/loader.py` sẽ substitute. Ví dụ:
`{{shared_rules}}`, `{{safeguards}}`.

## Loader

```python
from app.platform.prompts.loader import build_system_prompt, load_prompt, render

system = build_system_prompt()                       # system_prompt.md đã thay placeholder
intent = render(load_prompt("intent.md"), zone="B")  # prompt khác, tự thay placeholder
```

Loader cache (`@lru_cache`) để không đọc disk nhiều lần (inspire team 003).
