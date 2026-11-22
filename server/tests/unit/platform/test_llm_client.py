"""Router LLM: model rẻ cho task rẻ, model mạnh cho task mạnh."""

import pytest

from app.platform.config.settings import get_settings
from app.platform.llm.client import get_llm


@pytest.fixture(autouse=True)
def _fresh_settings(monkeypatch):
    """Mỗi test đọc lại Settings từ env — không dính cache của test khác."""
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("MODEL_CLASSIFY", "gpt-4o-mini")
    monkeypatch.setenv("MODEL_GENERATE", "gpt-4o")
    monkeypatch.setenv("MODEL_JUDGE", "gpt-4o-mini")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_classify_uses_cheap_model():
    assert get_llm("classify").model_name == "gpt-4o-mini"


def test_generate_uses_strong_model():
    assert get_llm("generate").model_name == "gpt-4o"


def test_judge_uses_configured_model():
    assert get_llm("judge").model_name == "gpt-4o-mini"


def test_judge_same_model_as_generator_raises():
    get_settings.cache_clear()
    import os

    os.environ["MODEL_JUDGE"] = "gpt-4o"  # trùng MODEL_GENERATE
    get_settings.cache_clear()
    with pytest.raises(ValueError, match="self-preference"):
        get_llm("judge")
    os.environ.pop("MODEL_JUDGE")


def test_classify_and_judge_run_at_low_temperature():
    settings = get_settings()
    settings.llm_temperature = 0.9  # generate có thể nóng
    assert get_llm("classify").temperature == 0.0
    assert get_llm("judge").temperature == 0.0
    assert get_llm("generate").temperature == 0.9


def test_base_url_points_to_openai_compatible_provider(monkeypatch):
    """Dev dùng Groq qua API tương thích OpenAI: chỉ đổi base_url, không đổi code gọi."""
    monkeypatch.setenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
    get_settings.cache_clear()
    assert get_llm("generate").openai_api_base == "https://api.groq.com/openai/v1"


def test_old_openai_env_names_still_work(monkeypatch):
    """.env cũ dùng OPENAI_API_KEY / OPENAI_BASE_URL vẫn chạy sau khi đổi sang LLM_*."""
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-old")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.test/v1")
    get_settings.cache_clear()
    assert get_settings().llm_base_url == "https://example.test/v1"
    assert get_llm("generate").openai_api_base == "https://example.test/v1"
