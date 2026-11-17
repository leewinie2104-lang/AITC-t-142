"""Nạp prompt từ file `.md` trong `server/prompts/`.

Chuyển từ `src/agents/prompts.py` của template. Prompt nằm ngoài code để review
và xem diff dễ hơn; placeholder dạng `{{tên}}`.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

# server/src/app/platform/prompts/loader.py -> parents[4] = server/
PROMPTS_DIR = Path(__file__).resolve().parents[4] / "prompts"

# Quy tắc chung chèn vào mọi prompt.
SHARED_RULES = """- Trả lời tiếng Việt có dấu.
- Ngắn gọn, đúng trọng tâm. Không lặp ý.
- Khi không chắc thì nói "tôi không chắc", không bịa.
- Không hứa hẹn thay cho quyết định của rule engine (tư cách, quyền thuê, phí)."""


@lru_cache(maxsize=32)
def load_prompt(name: str) -> str:
    """Đọc file prompt và cache. Raise FileNotFoundError nếu không có."""
    path = PROMPTS_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Prompt file không tồn tại: {path}")
    return path.read_text(encoding="utf-8")


def render(template: str, **values: str) -> str:
    """Thay `{{key}}` bằng giá trị tương ứng."""
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", value)
    return template


def build_system_prompt() -> str:
    """Render `system_prompt.md` với shared rules, citation rules và safeguards."""
    shared = SHARED_RULES
    try:
        shared += "\n\n" + load_prompt("citation_rules.md")
    except FileNotFoundError:
        pass
    return render(
        load_prompt("system_prompt.md"),
        shared_rules=shared,
        safeguards=load_prompt("safeguards.md"),
    )
