import os
from pathlib import Path

import pytest
from sqlalchemy.engine import make_url

from app.core.config import Settings


@pytest.fixture
def env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for name in tuple(os.environ):
        if name.lower() in Settings.model_fields:
            monkeypatch.delenv(name)
    path = tmp_path / ".env"
    monkeypatch.setitem(Settings.model_config, "env_file", path)
    return path


def test_working_directory_dotenv_does_not_replace_root_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected_name = Settings().openrouter_app_name
    (tmp_path / ".env").write_text(
        f"OPENROUTER_APP_NAME={expected_name} (wrong directory)\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    assert Settings().openrouter_app_name == expected_name


def test_dotenv_settings_apply_from_another_directory(
    env_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file.write_text(
        "AI_MODE=openrouter\n"
        "OPENROUTER_CHAT_MODEL=example/chat:free\n"
        "OPENROUTER_REASONING_MODEL=example/reasoning:free\n"
        "OPENROUTER_EMBEDDING_MODEL=example/embedding\n"
        "OPENROUTER_SITE_URL=https://shop.example.test\n"
        "OPENROUTER_APP_NAME=My store\n"
        "OPENROUTER_TIMEOUT=45\n"
        "OPENROUTER_RETRIES=4\n"
        "EMBEDDING_DIMENSIONS=512\n"
        "EMBEDDING_BATCH_SIZE=8\n"
        "TAX_RATE=0.05\n"
        "CHECKOUT_TTL_SECONDS=900\n"
        "RATE_LIMIT_PER_MINUTE=20\n"
        "PAYMENT_MODE=declined\n"
        "CORS_ORIGINS=https://shop.example.test\n",
        encoding="utf-8",
    )
    other_directory = env_file.parent / "backend"
    other_directory.mkdir()
    monkeypatch.chdir(other_directory)

    settings = Settings()
    assert settings.ai_mode == "openrouter"
    assert settings.openrouter_chat_model == "example/chat:free"
    assert settings.openrouter_reasoning_model == "example/reasoning:free"
    assert settings.openrouter_embedding_model == "example/embedding"
    assert settings.openrouter_site_url == settings.cors_origins == "https://shop.example.test"
    assert settings.openrouter_app_name == "My store"
    assert settings.openrouter_timeout == 45
    assert settings.openrouter_retries == 4
    assert settings.embedding_dimensions == 512
    assert settings.embedding_batch_size == 8
    assert settings.tax_rate == "0.05"
    assert settings.checkout_ttl_seconds == 900
    assert settings.rate_limit_per_minute == 20
    assert settings.payment_mode == "declined"


def test_environment_overrides_dotenv_and_database_address(
    env_file: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_file.write_text(
        "POSTGRES_HOST=localhost\nPOSTGRES_PORT=55432\n"
        "POSTGRES_USER=shop@test\nPOSTGRES_PASSWORD='p@ss:/word'\n"
        "POSTGRES_DB=custom_shop\nOPENROUTER_CHAT_MODEL=example/chat:free\n",
        encoding="utf-8",
    )
    local = make_url(Settings().database_url)
    assert (local.host, local.port) == ("localhost", 55432)
    monkeypatch.setenv("POSTGRES_HOST", "db")
    monkeypatch.setenv("POSTGRES_PORT", "5432")
    monkeypatch.setenv("OPENROUTER_CHAT_MODEL", "example/override:free")

    settings = Settings()
    docker = make_url(settings.database_url)
    assert (docker.host, docker.port) == ("db", 5432)
    assert docker.username == local.username == "shop@test"
    assert docker.password == local.password == "p@ss:/word"
    assert docker.database == local.database == "custom_shop"
    assert settings.openrouter_chat_model == "example/override:free"


def test_explicit_database_url_overrides_components(env_file: Path) -> None:
    url = "postgresql+asyncpg://custom:password@remote.example.test:6543/store"
    env_file.write_text(
        f"DATABASE_URL={url}\nPOSTGRES_HOST=db\nPOSTGRES_PORT=5432\n", encoding="utf-8"
    )
    assert Settings().database_url == url
