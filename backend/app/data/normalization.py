import hashlib
import json
import random
import re
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import NAMESPACE_URL, uuid5


def normalize(
    raw: dict[str, Any], category: str, minimum_rating_count: int = 10
) -> dict[str, Any] | None:
    try:
        title = str(raw.get("title") or "").strip()
        external_id = str(raw.get("parent_asin") or raw.get("asin") or "")
        price = Decimal(str(raw.get("price", "")).replace("$", "").replace(",", ""))
        rating = Decimal(str(raw.get("average_rating", "")))
        count = int(raw.get("rating_number", 0))
        descriptions = raw.get("description") or []
        description = (
            " ".join(descriptions) if isinstance(descriptions, list) else str(descriptions)
        )
        features = [str(f)[:1000] for f in (raw.get("features") or [])][:30]
        images = raw.get("images") or []
        image = next(
            (
                i.get("large") or i.get("hi_res") or i.get("thumb")
                for i in images
                if isinstance(i, dict) and (i.get("large") or i.get("hi_res") or i.get("thumb"))
            ),
            "",
        )
        if not (
            title
            and external_id
            and price.is_finite()
            and 0 < price < 1000000
            and rating.is_finite()
            and 0 <= rating <= 5
            and count >= minimum_rating_count
            and (description or features)
            and str(image).startswith("https://")
        ):
            return None
        categories = [str(c) for c in (raw.get("categories") or []) if c]
        subcategory = categories[-1] if categories else category.replace("_", " ")
        details = raw.get("details") or {}
        brand = str(details.get("Brand") or raw.get("store") or "Unspecified")[:200]
        attributes = {
            str(k).lower().replace(" ", "_"): str(v)[:500]
            for k, v in details.items()
            if k
            in {
                "Color",
                "Size",
                "Material",
                "Battery Life",
                "Item Weight",
                "Connectivity Technology",
                "Water Resistance Level",
            }
        }
        # Normalized aliases preserve the source claim; never infer a feature from absent data.
        search_text = " ".join(
            [
                title,
                brand,
                category.replace("_", " "),
                subcategory,
                description,
                *features,
                json.dumps(attributes),
            ]
        ).lower()
        search_text = re.sub(r"noise[- ]cancell?ing", "noise cancelling", search_text)
        return {
            "id": str(uuid5(NAMESPACE_URL, f"amazon-reviews-2023:{external_id}")),
            "external_id": external_id,
            "major_category": category.replace("_", " "),
            "subcategory": subcategory[:200],
            "product_type": subcategory[:160].lower(),
            "title": title[:600],
            "brand": brand,
            "description": description[:8000],
            "features": features,
            "price": str(price.quantize(Decimal("0.01"))),
            "currency": "USD",
            "average_rating": str(rating),
            "rating_count": count,
            "image_url": image,
            "attributes": attributes,
            "source": "Amazon Reviews 2023",
            "search_text": search_text[:20000],
        }
    except (ValueError, TypeError, InvalidOperation, AttributeError):
        return None


def synthetic_inventory(product_id: str, seed: int = 42) -> dict[str, Any]:
    rng = random.Random(hashlib.sha256(f"{seed}:{product_id}".encode()).digest())
    return {
        "product_id": product_id,
        "stock_quantity": rng.randint(5, 70),
        "reserved_quantity": 0,
        "warehouse": rng.choice(["WH-MO-01", "WH-VA-01", "WH-CA-01"]),
        "shipping_days": rng.randint(1, 5),
        "discount_percentage": str(rng.choice([0, 0, 0, 5, 10])),
        "active": True,
    }
