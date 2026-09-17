import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.openrouter_client import EmbeddingMismatch, OpenRouterClient
from app.core.config import Settings
from app.models.entities import EmbeddingIndex, Product, ProductEmbedding

EMBEDDING_VERSION = "product-v1"


def embedding_text(product: Product) -> str:
    return f"Title: {product.title}\nBrand: {product.brand}\nCategory: {product.major_category}\nSubcategory: {product.subcategory}\nDescription: {product.description[:4000]}\nFeatures: {'; '.join(product.features)[:3000]}\nAttributes: {json.dumps(product.attributes, sort_keys=True)}"


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


async def verify_index(db: AsyncSession, settings: Settings) -> EmbeddingIndex | None:
    index = await db.get(EmbeddingIndex, 1)
    if index and (
        index.model != settings.openrouter_embedding_model
        or index.dimensions != settings.embedding_dimensions
        or index.version != EMBEDDING_VERSION
    ):
        raise EmbeddingMismatch()
    return index


async def embed_products(
    db: AsyncSession, ai: OpenRouterClient, settings: Settings, products: list[Product]
) -> dict[str, int]:
    index = await verify_index(db, settings)
    if index is None:
        index = EmbeddingIndex(
            id=1,
            model=settings.openrouter_embedding_model,
            dimensions=settings.embedding_dimensions,
            version=EMBEDDING_VERSION,
        )
        db.add(index)
        await db.flush()
    pending: list[tuple[Product, str, str, ProductEmbedding | None]] = []
    for product in products:
        text = embedding_text(product)
        digest = content_hash(text)
        prior = await db.get(ProductEmbedding, product.id)
        if (
            prior
            and prior.content_hash == digest
            and prior.embedding_model == settings.openrouter_embedding_model
            and prior.embedding_version == EMBEDDING_VERSION
        ):
            continue
        pending.append((product, text, digest, prior))
    for start in range(0, len(pending), settings.embedding_batch_size):
        batch = pending[start : start + settings.embedding_batch_size]
        vectors = await ai.embed_batch([row[1] for row in batch])
        if len(vectors) != len(batch) or any(
            len(vector) != settings.embedding_dimensions for vector in vectors
        ):
            raise EmbeddingMismatch()
        for (product, _, digest, prior), vector in zip(batch, vectors, strict=True):
            values: dict[str, Any] = {
                "embedding": vector,
                "embedding_model": settings.openrouter_embedding_model,
                "embedding_version": EMBEDDING_VERSION,
                "content_hash": digest,
            }
            if prior:
                for key, value in values.items():
                    setattr(prior, key, value)
            else:
                db.add(ProductEmbedding(product_id=product.id, **values))
        await db.flush()
    return {"embedded": len(pending), "skipped": len(products) - len(pending)}


async def next_batch(db: AsyncSession, cursor: str, size: int) -> list[Product]:
    return list(
        (
            await db.scalars(
                select(Product).where(Product.id > cursor).order_by(Product.id).limit(size)
            )
        ).all()
    )
