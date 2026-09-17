import json
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.constraints import extract_constraints
from app.ai.fake_client import FakeOpenRouterClient
from app.ai.openrouter_client import (
    AIError,
    AIResponseError,
    EmbeddingMismatch,
    RealOpenRouterClient,
)
from app.core.config import Settings
from app.models.entities import EmbeddingIndex, Product
from app.ranking.engine import load_weights
from app.schemas.commerce import Constraints, SearchRequest
from app.search.hybrid import HybridSearch
from app.services.embeddings import embed_products


async def no_sleep(_: float) -> None:
    pass


@pytest.mark.parametrize("status", [429, 500, 502])
async def test_openrouter_retry_fallback_and_routing(status: int) -> None:
    seen = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        payload = json.loads(request.content)
        assert str(request.url).startswith("https://openrouter.ai/api/v1/")
        assert request.headers["x-title"] == "ShopPilot AI"
        if payload["model"] == "primary":
            return httpx.Response(status, headers={"retry-after": "0"})
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 2},
            },
        )

    ai = RealOpenRouterClient(
        Settings(
            openrouter_api_key="test-only",
            openrouter_chat_model="primary",
            openrouter_fallback_models="secondary",
            openrouter_retries=1,
        ),
        transport=httpx.MockTransport(handler),
        sleep=no_sleep,
    )
    result = await ai.chat([{"role": "user", "content": "hello"}])
    assert result.content == "ok" and result.usage and result.usage.input_tokens == 5
    assert len(seen) == 3
    await ai.aclose()


async def test_openrouter_timeout_and_no_credential_leak() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("secret-provider-body", request=request)

    ai = RealOpenRouterClient(
        Settings(openrouter_api_key="secret-test", openrouter_retries=0),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(AIError) as error:
        await ai.chat([])
    assert "secret" not in str(error.value)
    await ai.aclose()


async def test_embedding_endpoint_model_order_and_dimensions() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://openrouter.ai/api/v1/embeddings"
        assert json.loads(request.content)["model"] == "configured-embedding"
        return httpx.Response(
            200,
            json={"data": [{"index": 1, "embedding": [0, 1]}, {"index": 0, "embedding": [1, 0]}]},
        )

    ai = RealOpenRouterClient(
        Settings(
            openrouter_api_key="test",
            openrouter_embedding_model="configured-embedding",
            embedding_dimensions=2,
        ),
        transport=httpx.MockTransport(handler),
    )
    assert await ai.embed_batch(["one", "two"]) == [[1, 0], [0, 1]]
    await ai.aclose()


async def test_malformed_constraint_output() -> None:
    with pytest.raises(AIResponseError):
        await extract_constraints(FakeOpenRouterClient(responses=['{"max_price": -3}']), "shoes")
    result = await extract_constraints(FakeOpenRouterClient(), "waterproof hiking boots under $180")
    assert result.max_price == 180 and "waterproof" in result.required_features


async def test_hard_filters_top_five_and_rank_components(db: AsyncSession) -> None:
    search = HybridSearch(db, FakeOpenRouterClient(), Settings())
    result = await search.search(
        SearchRequest(
            query="headphones",
            constraints=Constraints(max_price=150, required_features=["wireless"]),
        )
    )
    assert len(result["products"]) == 5
    assert all(Decimal(p["price"]) <= 150 for p in result["products"])
    assert all(0 <= p["score"] <= 1 for p in result["products"])
    fewer = await search.search(
        SearchRequest(query="headphones", constraints=Constraints(max_price=90))
    )
    assert len(fewer["products"]) == 1
    assert not (
        await search.search(
            SearchRequest(
                query="headphones", constraints=Constraints(required_features=["waterproof"])
            )
        )
    )["products"]


def test_invalid_weights(tmp_path: Path) -> None:
    path = tmp_path / "weights.yaml"
    path.write_text("weights:\n  semantic: 3\n")
    with pytest.raises(ValueError):
        load_weights(path)


async def test_embedding_skip_and_reindex_guard(db: AsyncSession) -> None:
    ai = FakeOpenRouterClient(dimensions=3)
    settings = Settings(embedding_dimensions=3)
    products = list((await db.scalars(select(Product).limit(2))).all())
    assert (await embed_products(db, ai, settings, products))["embedded"] == 2
    assert (await embed_products(db, ai, settings, products))["skipped"] == 2
    assert ai.calls == ["embed_batch"]
    index = await db.get(EmbeddingIndex, 1)
    assert index
    index.dimensions = 4
    with pytest.raises(EmbeddingMismatch):
        await embed_products(db, ai, settings, products)


def test_reject_direct_provider_base_url() -> None:
    with pytest.raises(ValueError):
        Settings(openrouter_base_url="https://example.test/api/v1")
