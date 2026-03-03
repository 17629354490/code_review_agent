"""应用配置，支持环境变量与 .env。"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API
    app_name: str = "code-review-agent"
    debug: bool = False
    api_prefix: str = "/api/v1"

    # LLM
    llm_provider: str = "openai"  # openai | azure | ollama
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str | None = None  # for Ollama / custom endpoint
    llm_api_key: str | None = None
    llm_max_tokens: int = 4096
    llm_timeout_seconds: int = 60

    # Storage
    data_dir: Path = Path("data")
    reports_dir: Path = Path("data/reports")
    rules_config_path: Path = Path("config/rules.yaml")

    # Task queue (MVP: in-memory)
    queue_max_size: int = 100
    worker_poll_interval_seconds: float = 1.0

    # Security
    api_key_header: str = "X-API-Key"
    api_keys: str = ""  # comma-separated, empty = no auth for dev
    webhook_github_secret: str = ""
    webhook_gitlab_secret: str = ""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @property
    def allowed_api_keys(self) -> list[str]:
        if not self.api_keys:
            return []
        return [k.strip() for k in self.api_keys.split(",") if k.strip()]


settings = Settings()
