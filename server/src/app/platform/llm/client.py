"""Router LLM theo loại task: model rẻ cho việc đơn giản, model mạnh cho việc khó.

Chuyển từ `src/services/llm.py` của template. `get_llm(task_type)` là điểm duy nhất
chọn model:

- "classify": model rẻ (phân loại ý định W0, guardrail mềm)
- "generate": model mạnh (câu trả lời, đề xuất, tóm tắt)
- "judge":    model KHÁC generate, dùng cho eval

Đổi model chỉ cần sửa `.env`. Bước tiếp theo theo ADR-0007: thay `ChatOpenAI`
bằng `ChatBedrockConverse` và bọc trong `LLMPort` có ẩn danh (ADR-0010).
"""

from typing import Literal

from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from app.platform.config.settings import get_settings

TaskType = Literal["classify", "generate", "judge"]

_TASK_TO_SETTING = {
    "classify": "model_classify",
    "generate": "model_generate",
    "judge": "model_judge",
}


def get_llm(task_type: TaskType = "generate") -> ChatOpenAI:
    """Trả về LLM phù hợp với loại task.

    Raises:
        ValueError: nếu model judge trùng model generate.
    """
    settings = get_settings()

    if task_type == "judge" and settings.model_judge == settings.model_generate:
        raise ValueError(
            "MODEL_JUDGE phải khác MODEL_GENERATE: judge trùng generator gây "
            "self-preference bias. Sửa MODEL_JUDGE trong .env."
        )

    model_name = getattr(settings, _TASK_TO_SETTING[task_type])
    # classify và judge cần ổn định, không sáng tạo.
    temperature = 0.0 if task_type in ("classify", "judge") else settings.llm_temperature

    return ChatOpenAI(
        model=model_name,
        api_key=SecretStr(settings.openai_api_key),
        temperature=temperature,
    )
