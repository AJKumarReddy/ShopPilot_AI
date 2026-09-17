from collections.abc import AsyncIterator

from app.ai.fake_client import FakeOpenRouterClient
from app.ai.openrouter_client import OpenRouterClient, RealOpenRouterClient
from app.core.config import get_settings


async def get_ai() -> AsyncIterator[OpenRouterClient]:
    settings = get_settings()
    client: OpenRouterClient = (
        FakeOpenRouterClient(dimensions=settings.embedding_dimensions)
        if settings.ai_mode == "demo"
        else RealOpenRouterClient(settings)
    )
    try:
        yield client
    finally:
        await client.aclose()
