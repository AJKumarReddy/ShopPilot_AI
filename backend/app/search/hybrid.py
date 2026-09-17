import re
import time
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import ColumnElement, cast, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.openrouter_client import AIError, OpenRouterClient
from app.core.config import Settings
from app.models.entities import Inventory, Product, ProductEmbedding
from app.observability.telemetry import SEARCH_LATENCY, SEARCH_RESULTS
from app.ranking.engine import load_weights, rank
from app.schemas.commerce import SearchRequest
from app.services.embeddings import verify_index


def literal_pattern(value: str) -> str:
    return "%" + value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


class HybridSearch:
    def __init__(self, db: AsyncSession, ai: OpenRouterClient, settings: Settings) -> None:
        self.db, self.ai, self.settings = db, ai, settings

    async def search(
        self, args: SearchRequest, preferences: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        started = time.perf_counter()
        c = args.constraints
        postgres = self.db.get_bind().dialect.name == "postgresql"
        predicates: list[ColumnElement[bool]] = [Inventory.active.is_(True)]
        discounted = func.round(Product.price * (1 - Inventory.discount_percentage / 100), 2)
        if c.available_only:
            predicates.append(Inventory.stock_quantity > Inventory.reserved_quantity)
        if c.min_price is not None:
            predicates.append(discounted >= c.min_price)
        if c.max_price is not None:
            predicates.append(discounted <= c.max_price)
        if c.min_rating is not None:
            predicates.append(Product.average_rating >= c.min_rating)
        if c.brands:
            predicates.append(func.lower(Product.brand).in_([b.lower() for b in c.brands]))
        if c.category:
            if postgres:
                predicates.append(
                    func.to_tsvector(literal("english"), Product.search_text).op("@@")(
                        func.plainto_tsquery(literal("english"), c.category)
                    )
                )
            else:
                predicates.append(
                    Product.search_text.ilike(literal_pattern(c.category), escape="\\")
                )
        if c.subcategory:
            predicates.append(
                Product.subcategory.ilike(literal_pattern(c.subcategory), escape="\\")
            )
        for feature in c.required_features:
            predicates.append(Product.search_text.ilike(literal_pattern(feature), escape="\\"))
        for key, value in (("size", c.size), ("color", c.color)):
            if value:
                predicates.append(func.lower(Product.attributes[key].as_string()) == value.lower())
        if c.max_shipping_days:
            predicates.append(Inventory.shipping_days <= c.max_shipping_days)
        words = re.findall(r"[a-z0-9]+", args.query.lower())
        stopwords = {
            "i",
            "im",
            "m",
            "looking",
            "for",
            "a",
            "an",
            "the",
            "with",
            "good",
            "need",
            "under",
            "below",
            "only",
            "show",
            "products",
            "me",
            "rated",
            "above",
            "and",
            "want",
        }
        words = [w for w in words if w not in stopwords and not w.isdigit()][:20]
        base = select(Product, Inventory).join(Inventory).where(*predicates)
        if postgres and words:
            vector = func.to_tsvector(literal("english"), Product.search_text)
            query = func.websearch_to_tsquery(literal("english"), " OR ".join(words))
            lexical = (
                await self.db.execute(
                    base.add_columns(func.ts_rank_cd(vector, query).label("lexical"))
                    .where(vector.op("@@")(query))
                    .order_by(func.ts_rank_cd(vector, query).desc(), Product.id)
                    .limit(100)
                )
            ).all()
        else:
            query_base = (
                base.where(
                    or_(
                        *[
                            Product.search_text.ilike(literal_pattern(word), escape="\\")
                            for word in words
                        ]
                    )
                )
                if words
                else base
            )
            lexical = (
                await self.db.execute(
                    query_base.add_columns(literal(1.0))
                    .order_by(Product.average_rating.desc(), Product.id)
                    .limit(100)
                )
            ).all()
        pool: dict[str, tuple[Product, Inventory, float]] = {}
        for position, (product, inventory, _) in enumerate(lexical):
            pool[product.id] = (product, inventory, 1 / (1 + position / 20))
        mode, warning = "lexical", None
        if postgres and self.settings.ai_mode == "openrouter" and args.query:
            try:
                index = await verify_index(self.db, self.settings)
                if index:
                    embedding = await self.ai.embed_text(args.query)
                    distance = cast(
                        ProductEmbedding.embedding, Vector(self.settings.embedding_dimensions)
                    ).cosine_distance(embedding)
                    semantic = (
                        await self.db.execute(
                            base.join(ProductEmbedding, ProductEmbedding.product_id == Product.id)
                            .where(
                                ProductEmbedding.embedding_model
                                == self.settings.openrouter_embedding_model
                            )
                            .add_columns(distance.label("distance"))
                            .order_by(distance)
                            .limit(100)
                        )
                    ).all()
                    for product, inventory, distance_value in semantic:
                        similarity = max(0, min(1, 1 - float(distance_value)))
                        prior = pool.get(product.id)
                        fused = 0.65 * similarity + 0.35 * (prior[2] if prior else 0)
                        pool[product.id] = (product, inventory, fused)
                    mode = "hybrid"
                else:
                    warning = "Semantic index has not been built; using catalog text and filters."
            except AIError:
                warning = "Semantic search is unavailable; using catalog text and filters."
        products = rank(list(pool.values()), c, load_weights(), preferences)[: args.limit]
        SEARCH_LATENCY.observe(time.perf_counter() - started)
        SEARCH_RESULTS.observe(len(products))
        return {
            "products": products,
            "constraints": c.model_dump(mode="json"),
            "retrieval_mode": mode,
            "warning": warning,
        }
