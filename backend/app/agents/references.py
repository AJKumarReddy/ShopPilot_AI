from decimal import Decimal
from typing import Any

from app.core.errors import CommerceError

ORDINALS = {
    "first": 0,
    "one": 0,
    "1": 0,
    "second": 1,
    "two": 1,
    "2": 1,
    "third": 2,
    "three": 2,
    "3": 2,
    "fourth": 3,
    "four": 3,
    "4": 3,
    "fifth": 4,
    "five": 4,
    "5": 4,
}


def resolve(
    references: list[str], products: list[dict[str, Any]], selected: list[str] | None = None
) -> list[str]:
    resolved = []
    for reference in references:
        reference = reference.lower().strip()
        if reference in ORDINALS:
            index = ORDINALS[reference]
            matches = [products[index]] if index < len(products) else []
        elif reference in {"cheaper", "cheapest"}:
            lowest = min((Decimal(p["price"]) for p in products), default=Decimal(0))
            matches = [p for p in products if Decimal(p["price"]) == lowest]
        elif reference == "selected":
            matches = [p for p in products if p["id"] in (selected or [])] or products
        else:
            matches = [p for p in products if reference in (p["brand"] + " " + p["title"]).lower()]
        if len(matches) != 1:
            raise CommerceError(
                "Which product do you mean? Please use its number or full name.", 422
            )
        resolved.append(matches[0]["id"])
    return list(dict.fromkeys(resolved))
