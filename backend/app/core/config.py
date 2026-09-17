from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = (
        "postgresql+asyncpg://shoppilot:local-development-only@localhost:55432/shoppilot"
    )
    ai_mode: Literal["demo", "openrouter"] = "demo"
    dataset_mode: Literal["demo", "full"] = "demo"
    auth_mode: Literal["demo", "token"] = "demo"
    demo_auth_token: SecretStr = SecretStr("local-demo-token-change-for-shared-environments")
    openrouter_api_key: SecretStr = SecretStr("")
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_chat_model: str = "openai/gpt-5.6-luna"
    openrouter_reasoning_model: str = "openai/gpt-5.6-terra"
    openrouter_embedding_model: str = "openai/text-embedding-3-small"
    openrouter_fallback_models: str = ""
    openrouter_site_url: str = "http://localhost:3000"
    openrouter_app_name: str = "ShopPilot AI"
    openrouter_timeout: float = 30
    openrouter_retries: int = 2
    voice_parallel_reasoning: bool = True
    voice_ack_timeout_ms: int = 1200
    embedding_dimensions: int = 1536
    embedding_batch_size: int = 32
    cors_origins: str = "http://localhost:3000"
    checkout_ttl_seconds: int = 600
    tax_rate: str = "0.0825"
    rate_limit_per_minute: int = 90
    payment_mode: Literal["approved", "declined", "processing_error"] = "approved"

    @field_validator("openrouter_base_url")
    @classmethod
    def router_only(cls, value: str) -> str:
        if value.rstrip("/") != "https://openrouter.ai/api/v1":
            raise ValueError("All AI traffic must use https://openrouter.ai/api/v1")
        return value.rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()
