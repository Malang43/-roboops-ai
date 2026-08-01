from functools import lru_cache

from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class Settings(BaseSettings):
    app_name: str = "RoboOps AI API"
    app_version: str = "0.3.0"
    database_url: str

    ollama_base_url: str = (
        "http://127.0.0.1:11434"
    )
    ollama_model: str = "qwen2:latest"
    ollama_timeout_seconds: float = 180.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
