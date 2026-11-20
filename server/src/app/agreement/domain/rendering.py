"""Văn bản mẫu và bằng chứng băm thuần (M6, FR-08, BR-12)."""

import hashlib
import re
from collections.abc import Mapping
from datetime import datetime
from typing import Any


def render_agreement_template(template_md: str, context: Mapping[str, Any]) -> str:
    """Render nội dung thỏa thuận từ Markdown template và context dictionary.

    Thay thế các placeholder định dạng {{ key }} hoặc {{key}}.
    Nếu key không tồn tại trong context, giữ nguyên placeholder để tránh mất dấu vết.
    """

    def _replacer(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        if key in context:
            val = context[key]
            if isinstance(val, datetime):
                return val.strftime("%H:%M %d/%m/%Y")
            return str(val)
        return match.group(0)

    return re.sub(r"\{\{\s*([\w.]+)\s*\}\}", _replacer, template_md)


def compute_body_hash(body_rendered: str) -> bytes:
    """Tính toán mã băm SHA-256 (32 bytes raw binary)."""
    return hashlib.sha256(body_rendered.encode("utf-8")).digest()


def check_requires_approval(price_vnd: int, threshold_vnd: int = 1_000_000) -> bool:
    """BR-12 / AC-15: Giao dịch vượt ngưỡng cần Ban Quản Lý phê duyệt (HITL)."""
    return price_vnd >= threshold_vnd
