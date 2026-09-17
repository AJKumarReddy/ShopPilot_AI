"""Deterministic offline AI adapter for demos and tests; never opens a network socket."""

import hashlib
import re
from collections.abc import AsyncIterator
from typing import Any

from app.ai.openrouter_client import ChatResult, T


def demo_decision(message: str) -> dict[str, Any]:
    text = message.lower().strip()
    constraints: dict[str, Any] = {}
    intent = "search"
    if re.fullmatch(
        r"(yes[,! .]*|yes,? (please|place (the |my )?order)[.! ]*|confirm( order)?[.! ]*)", text
    ):
        intent = "confirm"
    elif "checkout" in text or "check out" in text:
        intent = "checkout"
    elif "status" in text or "where" in text and "order" in text:
        intent = "status"
    elif (
        "compare" in text
        or "which" in text
        and any(w in text for w in ("first", "three", "battery"))
    ):
        intent = "compare"
    elif re.search(r"\b(add|buy)\b", text):
        intent = "add"
    elif re.search(r"\b(remove|delete)\b", text):
        intent = "remove"
    elif "quantity" in text:
        intent = "update"
    elif "cart" in text:
        intent = "cart"
    price = re.search(r"(?:under|below|less than|up to)\s*\$?(\d+(?:\.\d+)?)", text)
    if price:
        constraints["max_price"] = price.group(1)
    rating = re.search(
        r"(?:rated?\s*(?:above|over|at least)?|rating\s*(?:above|over|at least)?)\s*(\d(?:\.\d+)?)",
        text,
    )
    if rating:
        constraints["min_rating"] = rating.group(1)
    categories = {
        "headphone": "headphones",
        "earbud": "earbuds",
        "hiking boot": "hiking boots",
        "running shoe": "running shoes",
        "coffee": "coffee",
        "laptop": "laptop",
        "skincare": "skin care",
    }
    for phrase, category in categories.items():
        if phrase in text:
            constraints["category"] = category
            break
    required = [feature for feature in ["wireless", "waterproof"] if feature in text]
    if re.search(r"noise[- ]cancell?ing", text):
        required.append("noise cancelling")
    if required:
        constraints["required_features"] = required
    preferred = [
        feature for feature in ["lightweight", "wide", "battery", "cushioning"] if feature in text
    ]
    if preferred:
        constraints["preferred_features"] = preferred
    brands = [
        brand
        for brand in ["Nike", "Adidas", "Sony", "JBL", "Bose", "Soundcore"]
        if brand.lower() in text
    ]
    if brands:
        constraints["brands"] = brands
    references = re.findall(
        r"\b(?:first|second|third|fourth|fifth|one|two|three|four|five|[1-5])\b", text
    )
    if "first three" in text:
        references = ["first", "second", "third"]
    if not references and intent in {"add", "remove", "compare"}:
        references = ["cheaper" if "cheaper" in text else next((b for b in brands), "selected")]
    quantity_match = re.search(r"(?:quantity (?:to )?|add )(\d+|two|three)\b", text)
    quantity = 1
    if quantity_match:
        q = quantity_match.group(1)
        quantity = {"two": 2, "three": 3}.get(q, int(q) if q.isdigit() else 1)
    size = re.search(r"size\s+(\d+(?:\.\d+)?(?:\s+wide)?)", text)
    return {
        "intent": intent,
        "constraints": constraints or None,
        "references": references,
        "quantity": quantity,
        "size": size.group(1) if size else None,
        "new_search": bool(constraints.get("category"))
        and not text.startswith(("only", "same", "show")),
    }


class FakeOpenRouterClient:
    def __init__(self, responses: list[str] | None = None, dimensions: int = 1536) -> None:
        self.responses = list(responses or [])
        self.dimensions = dimensions
        self.calls: list[str] = []

    async def aclose(self) -> None:
        pass

    async def chat(self, messages: list[dict[str, Any]], *, reasoning: bool = False) -> ChatResult:
        self.calls.append("chat")
        return ChatResult(
            self.responses.pop(0) if self.responses else "Here are your matching products."
        )

    async def chat_with_tools(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]
    ) -> ChatResult:
        return await self.chat(messages)

    async def structured_completion(self, messages: list[dict[str, Any]], schema: type[T]) -> T:
        self.calls.append("structured_completion")
        if self.responses:
            return schema.model_validate_json(self.responses.pop(0))
        user_message = str(messages[-1]["content"])
        result = demo_decision(user_message)
        return schema.model_validate(
            result if schema.__name__ == "AgentDecision" else result["constraints"] or {}
        )

    async def embed_text(self, text: str) -> list[float]:
        return (await self.embed_batch([text]))[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self.calls.append("embed_batch")
        return [
            [
                (hashlib.sha256(f"{text}:{index}".encode()).digest()[0] - 128) / 128
                for index in range(self.dimensions)
            ]
            for text in texts
        ]

    async def chat_stream(self, messages: list[dict[str, Any]]) -> AsyncIterator[str]:
        result = await self.chat(messages)
        for word in result.content.split():
            yield word + " "
