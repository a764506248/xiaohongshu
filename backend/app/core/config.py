from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "AI 自媒体运营系统"
    app_env: str = "development"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/xiaohongshu"
    checkpoint_database_url: str | None = "postgresql://postgres:postgres@localhost:5432/xiaohongshu"
    llm_provider: str = "sensenova"
    llm_base_url: str = "https://token.sensenova.cn/v1"
    llm_model: str = "deepseek-v4-flash"
    llm_api_key: str = ""
    llm_timeout_seconds: float = 120
    cors_origins: list[str] = ["http://localhost:5173"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
