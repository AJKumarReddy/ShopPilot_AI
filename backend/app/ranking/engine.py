import math
from pathlib import Path
from typing import Any

import yaml

from app.models.entities import Inventory, Product
from app.schemas.commerce import Constraints
from app.services.catalog import effective_price, product_view

COMPONENTS = {"semantic", "attributes", "price", "rating", "confidence", "shipping"}


def load_weights(path: Path | None = None) -> dict[str, float]:
    path = path or Path(__file__).resolve().parents[3] / "configs/recommendation.yaml"
    if not path.exists():
        path = Path(__file__).resolve().parents[4] / "configs/recommendation.yaml"
    weights = {
        key: float(value) for key, value in yaml.safe_load(path.read_text())["weights"].items()
    }
    if (
        set(weights) != COMPONENTS
        or any(not math.isfinite(v) or v < 0 for v in weights.values())
        or not math.isclose(sum(weights.values()), 1, abs_tol=0.0001)
    ):
        raise ValueError("Ranking weights must match the six components and sum to one.")
    return weights


def rank(
    candidates: list[tuple[Product, Inventory, float]],
    constraints: Constraints,
    weights: dict[str, float],
    preferences: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    results = []
    preferences = preferences or {}
    for product, inventory, relevance in candidates:
        haystack = product.search_text.lower()
        wanted = constraints.preferred_features or constraints.required_features
        matched = [feature for feature in wanted if feature.lower() in haystack]
        attr_score = len(matched) / len(wanted) if wanted else 0.5
        if not constraints.brands and product.brand in preferences.get("favorite_brands", []):
            attr_score = min(1, attr_score + 0.1)
        price = effective_price(product, inventory)
        price_score = (
            max(0, 1 - float(price / constraints.max_price) * 0.5) if constraints.max_price else 0.5
        )
        components = {
            "semantic": min(1, max(0, relevance)),
            "attributes": attr_score,
            "price": price_score,
            "rating": float(product.average_rating) / 5,
            "confidence": min(1, math.log1p(product.rating_count) / math.log1p(10000)),
            "shipping": max(0, 1 - (inventory.shipping_days - 1) / 7),
        }
        score = sum(weights[k] * components[k] for k in weights)
        reasons = [f"Rated {product.average_rating}/5 from {product.rating_count:,} reviews."]
        if constraints.max_price:
            reasons.insert(0, f"Within your ${constraints.max_price} budget.")
        if matched:
            reasons.append("Source lists " + ", ".join(matched) + ".")
        reasons.append(
            f"In stock, estimated shipping in {inventory.shipping_days} days."
            if inventory.active and inventory.stock_quantity > inventory.reserved_quantity
            else "Currently unavailable."
        )
        results.append(
            {
                **product_view(product, inventory),
                "score": round(score, 6),
                "score_components": components,
                "reason": " ".join(reasons[:3]),
                "reason_options": reasons,
            }
        )
    if constraints.sort_preference == "price_asc":
        results.sort(key=lambda x: (float(x["price"]), -x["score"], x["id"]))
    elif constraints.sort_preference == "rating":
        results.sort(key=lambda x: (-float(x["average_rating"]), -x["score"], x["id"]))
    else:
        results.sort(key=lambda x: (-x["score"], x["id"]))
    return results[:5]
