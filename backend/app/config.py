"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Database
    database_url: str = "sqlite+aiosqlite:///./solo100.db"

    # Celery
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/0"

    # Feishu (optional)
    feishu_webhook_url: str = ""

    # SSH keys
    ssh_key_project_default: str = "SSH_KEY_PROJECT_DEFAULT"

    # Claude Code / AI
    anthropic_api_key_env: str = "ANTHROPIC_API_KEY"

    # App
    app_env: str = "development"
    log_level: str = "INFO"


settings = Settings()
