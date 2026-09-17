import argparse
import asyncio

from app.ai.openrouter_client import RealOpenRouterClient, Usage
from app.core.config import get_settings
from app.db.session import SessionFactory, engine
from app.models.entities import AgentEvent, EmbeddingIndex, ProductEmbedding
from app.services.embeddings import embed_products, next_batch
from sqlalchemy import delete, text


async def run(reindex: bool, limit: int | None) -> None:
    settings = get_settings()
    if not settings.openrouter_api_key.get_secret_value():
        raise SystemExit(
            "Set OPENROUTER_API_KEY before generating embeddings. This command uses credits."
        )
    if not 1 <= settings.embedding_dimensions <= 2000:
        raise SystemExit(
            "This HNSW index supports dimensions 1–2000; use a new index strategy for larger models."
        )
    if reindex:
        async with SessionFactory() as db, db.begin():
            await db.execute(text("SELECT pg_advisory_xact_lock(70715001)"))
            await db.execute(delete(ProductEmbedding))
            await db.execute(delete(EmbeddingIndex))
            await db.execute(text("DROP INDEX IF EXISTS ix_embedding_hnsw"))
            await db.execute(
                text(
                    f"CREATE INDEX ix_embedding_hnsw ON product_embeddings USING hnsw ((embedding::vector({settings.embedding_dimensions})) vector_cosine_ops)"
                )
            )
    cursor, processed = "", 0
    ai = RealOpenRouterClient(settings)
    try:
        while limit is None or processed < limit:
            async with SessionFactory() as db, db.begin():
                await db.execute(text("SELECT pg_advisory_xact_lock(70715001)"))
                batch = await next_batch(
                    db,
                    cursor,
                    min(settings.embedding_batch_size, limit - processed)
                    if limit
                    else settings.embedding_batch_size,
                )
                if not batch:
                    break

                async def usage_sink(usage: Usage) -> None:
                    db.add(AgentEvent(**usage.__dict__))

                ai.usage_sink = usage_sink
                counts = await embed_products(db, ai, settings, batch)
                cursor, processed = batch[-1].id, processed + len(batch)
                print(f"Processed {processed}: {counts}")
    finally:
        await ai.aclose()
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Batch embeddings through OpenRouter; unchanged products are skipped."
    )
    parser.add_argument(
        "--reindex",
        action="store_true",
        help="Explicitly discard the previous vector index and rebuild it for the configured model",
    )
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    asyncio.run(run(args.reindex, args.limit))
