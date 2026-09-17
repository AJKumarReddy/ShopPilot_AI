from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.models.entities import Inventory, Product


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def effective_price(product: Product, inventory: Inventory) -> Decimal:
    return money(product.price * (1 - inventory.discount_percentage / Decimal(100)))


def product_view(product: Product, inventory: Inventory) -> dict[str, Any]:
    return {
        "id": product.id,
        "title": product.title,
        "brand": product.brand,
        "major_category": product.major_category,
        "subcategory": product.subcategory,
        "product_type": product.product_type,
        "price": str(effective_price(product, inventory)),
        "original_price": str(product.price),
        "currency": product.currency,
        "average_rating": str(product.average_rating),
        "rating_count": product.rating_count,
        "image_url": product.image_url,
        "description": product.description,
        "features": product.features,
        "attributes": product.attributes,
        "source": product.source,
        "inventory": {
            "available": inventory.active
            and inventory.stock_quantity > inventory.reserved_quantity,
            "stock_quantity": inventory.stock_quantity - inventory.reserved_quantity,
            "shipping_days": inventory.shipping_days,
            "discount_percentage": str(inventory.discount_percentage),
        },
    }
