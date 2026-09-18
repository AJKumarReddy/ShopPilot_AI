from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )
    database_url: str = ""
    postgres_host: str = "localhost"
    postgres_port: int = 55432
    postgres_user: str = "shoppilot"
    postgres_password: SecretStr = SecretStr("local-development-only")
    postgres_db: str = "shoppilot"
    ai_mode: Literal["demo", "openrouter"] = "demo"
    dataset_mode: Literal["demo", "full"] = "demo"
    auth_mode: Literal["demo", "token"] = "demo"
    demo_auth_token: SecretStr = SecretStr("local-demo-token-change-for-shared-environments")
    openrouter_api_key: SecretStr = SecretStr("")
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_chat_model: str = "openrouter/free"
    openrouter_reasoning_model: str = "openrouter/free"
    openrouter_embedding_model: str = "openai/text-embedding-3-small"
    openrouter_fallback_models: str = ""
    openrouter_site_url: str = "http://localhost:3000"
    openrouter_app_name: str = "ShopPilot AI"
    openrouter_timeout: float = 30
    openrouter_retries: int = 2
    embedding_dimensions: int = 1536
    embedding_batch_size: int = 32
    cors_origins: str = "http://localhost:3000"
    checkout_ttl_seconds: int = 600
    tax_rate: str = "0.0825"
    rate_limit_per_minute: int = 90
    payment_mode: Literal["approved", "declined", "processing_error"] = "approved"

    @model_validator(mode="after")
    def resolve_database_url(self) -> Self:
        if not self.database_url:
            self.database_url = URL.create(
                "postgresql+asyncpg",
                username=self.postgres_user,
                password=self.postgres_password.get_secret_value(),
                host=self.postgres_host,
                port=self.postgres_port,
                database=self.postgres_db,
            ).render_as_string(hide_password=False)
        return self

    @field_validator("openrouter_base_url")
    @classmethod
    def router_only(cls, value: str) -> str:
        if value.rstrip("/") != "https://openrouter.ai/api/v1":
            raise ValueError("All AI traffic must use https://openrouter.ai/api/v1")
        return value.rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()
