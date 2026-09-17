import time
from typing import Any

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.openrouter_client import OpenRouterClient
from app.core.config import Settings
from app.core.errors import CommerceError
from app.observability.telemetry import COMMERCE_ACTIONS, TOOL_ERRORS, TOOL_LATENCY
from app.repositories.catalog import CatalogRepository
from app.schemas.commerce import (
    CartAdd,
    CompareInput,
    ConfirmInput,
    CreateOrderInput,
    ItemInput,
    OrderInput,
    ProductInput,
    QuantityInput,
    SearchRequest,
    StrictModel,
)
from app.search.hybrid import HybridSearch
from app.services.cart import CartService
from app.services.catalog import product_view
from app.services.checkout import CheckoutService


class NoArgs(StrictModel):
    pass


TOOL_SCHEMAS: dict[str, type[BaseModel]] = {
    "search_products": SearchRequest,
    "get_product": ProductInput,
    "compare_products": CompareInput,
    "check_inventory": ProductInput,
    "get_recommendations": SearchRequest,
    "get_cart": NoArgs,
    "add_to_cart": CartAdd,
    "remove_from_cart": ItemInput,
    "update_cart_quantity": QuantityInput,
    "prepare_checkout": NoArgs,
    "confirm_checkout": ConfirmInput,
    "create_order": CreateOrderInput,
    "get_order_status": OrderInput,
}


class CommerceTools:
    def __init__(
        self, db: AsyncSession, user_id: str, ai: OpenRouterClient, settings: Settings
    ) -> None:
        self.catalog = CatalogRepository(db)
        self.cart = CartService(db, user_id, settings)
        self.checkout = CheckoutService(db, user_id, settings)
        self.search = HybridSearch(db, ai, settings)

    @staticmethod
    def definitions() -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": f"Validated ShopPilot {name.replace('_', ' ')} operation.",
                    "parameters": schema.model_json_schema(),
                },
            }
            for name, schema in TOOL_SCHEMAS.items()
            if name not in {"confirm_checkout", "create_order"}
        ]

    async def call(self, name: str, arguments: dict[str, Any], allowed: set[str]) -> dict[str, Any]:
        if name not in allowed or name not in TOOL_SCHEMAS:
            raise CommerceError("This action is not authorized for the current request.", 403)
        args = TOOL_SCHEMAS[name].model_validate(arguments).model_dump()
        started = time.perf_counter()
        try:
            result = await self.dispatch(name, args)
            COMMERCE_ACTIONS.labels(name).inc()
            return result
        except Exception:
            TOOL_ERRORS.labels(name).inc()
            raise
        finally:
            TOOL_LATENCY.labels(name).observe(time.perf_counter() - started)

    async def dispatch(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        if name in {"search_products", "get_recommendations"}:
            return await self.search.search(SearchRequest(**args))
        if name in {"get_product", "check_inventory"}:
            product, inventory = await self.catalog.get(args["product_id"])
            view = product_view(product, inventory)
            return view if name == "get_product" else view["inventory"]
        if name == "compare_products":
            products = [
                product_view(*(await self.catalog.get(pid)))
                for pid in dict.fromkeys(args["product_ids"])
            ]
            return {"comparison": products}
        if name == "get_cart":
            return {"cart": await self.cart.view()}
        if name == "add_to_cart":
            return {"cart": await self.cart.add(CartAdd(**args))}
        if name in {"remove_from_cart", "update_cart_quantity"}:
            return {"cart": await self.cart.change(args["item_id"], args.get("quantity"))}
        if name == "prepare_checkout":
            return {"checkout": await self.checkout.prepare()}
        if name == "confirm_checkout":
            await self.checkout.confirm(ConfirmInput(**args))
            return {"confirmed": True}
        if name == "create_order":
            return {"order": await self.checkout.create_order(CreateOrderInput(**args))}
        if name == "get_order_status":
            return {"order": await self.checkout.order_view(args["order_id"])}
        raise CommerceError("Unknown commerce action.", 400)
