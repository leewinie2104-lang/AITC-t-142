"""Cấu hình ứng dụng, đọc từ biến môi trường và file `.env`.

Chuyển từ `src/config.py` của template. File `.env` nằm ở gốc repo (hook ghi log AI
của BTC cũng đọc file này), nên khi chạy trong `server/` vẫn tìm được qua `../.env`.
"""

from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name: str = "ParkSmart AI"
    app_env: Literal["development", "production", "test"] = "development"
    app_port: int = Field(default=8000, ge=1, le=65535)
    app_host: str = "0.0.0.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # LLM: mỗi loại task một model. Judge phải khác model generate để tránh
    # self-preference bias khi chấm eval. Dev dùng Groq (ADR-0013); demo dự kiến Bedrock (ADR-0007).
    # Any OpenAI-compatible provider. Old OPENAI_* names still accepted.
    llm_api_key: str = Field(default="", validation_alias=AliasChoices("LLM_API_KEY", "OPENAI_API_KEY"))
    # Empty = api.openai.com. Groq: https://api.groq.com/openai/v1
    llm_base_url: str | None = Field(default=None, validation_alias=AliasChoices("LLM_BASE_URL", "OPENAI_BASE_URL"))
    model_classify: str = "gpt-4o-mini"
    model_generate: str = "gpt-4o"
    model_judge: str = "gpt-4o-mini"
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)

    # Database (ADR-0005)
    database_url: str = "postgresql://parksmart:parksmart@localhost:5432/parksmart"

    # Redis: hàng đợi arq, pub/sub (ADR-0004)
    redis_url: str = "redis://localhost:6379/0"


@lru_cache
def get_settings() -> Settings:
    return Settings()
