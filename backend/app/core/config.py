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
    aliyun_model_api_key: str = ""
    aliyun_openai_base_url: str = "https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1"
    aliyun_anthropic_base_url: str = "https://token-plan.cn-beijing.maas.aliyuncs.com/apps/anthropic"
    aliyun_multimodal_base_url: str = "https://token-plan.cn-beijing.maas.aliyuncs.com/api/v1"
    openrouter_model_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    cors_origins: list[str] = ["http://localhost:5173"]
    auth_secret_key: str = "change-this-secret-in-production"
    auth_token_hours: int = 12
    default_admin_username: str = "admin"
    default_admin_password: str = "admin123"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
