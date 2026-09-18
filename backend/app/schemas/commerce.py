from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Constraints(StrictModel):
    major_category: str | None = Field(default=None, max_length=120)
    category: str | None = Field(default=None, max_length=160)
    subcategory: str | None = Field(default=None, max_length=200)
    min_price: Decimal | None = Field(default=None, ge=0)
    max_price: Decimal | None = Field(default=None, gt=0)
    brands: list[str] = Field(default_factory=list, max_length=10)
    min_rating: Decimal | None = Field(default=None, ge=0, le=5)
    required_features: list[str] = Field(default_factory=list, max_length=15)
    preferred_features: list[str] = Field(default_factory=list, max_length=15)
    size: str | None = Field(default=None, max_length=40)
    color: str | None = Field(default=None, max_length=40)
    max_shipping_days: int | None = Field(default=None, ge=1, le=60)
    available_only: bool = True
    use_case: str | None = Field(default=None, max_length=300)
    sort_preference: Literal["price_asc", "rating", "relevance"] | None = None

    @model_validator(mode="after")
    def bounds(self) -> "Constraints":
        if (
            self.min_price is not None
            and self.max_price is not None
            and self.min_price > self.max_price
        ):
            raise ValueError("min_price must not exceed max_price")
        return self


class SearchRequest(StrictModel):
    query: str = Field(default="", max_length=2000)
    constraints: Constraints = Field(default_factory=Constraints)
    limit: int = Field(default=5, ge=1, le=5)


class ProductInput(StrictModel):
    product_id: str = Field(min_length=1, max_length=36)


class CompareInput(StrictModel):
    product_ids: list[str] = Field(min_length=2, max_length=5)


class CartAdd(ProductInput):
    quantity: int = Field(default=1, ge=1, le=99)
    size: str | None = Field(default=None, max_length=40)
    color: str | None = Field(default=None, max_length=40)


class CartUpdate(StrictModel):
    quantity: int = Field(ge=1, le=99)


class ItemInput(StrictModel):
    item_id: str = Field(min_length=1, max_length=36)


class QuantityInput(ItemInput, CartUpdate):
    pass


class ConfirmInput(StrictModel):
    checkout_session_id: str = Field(min_length=1, max_length=36)
    confirmation_token: str = Field(min_length=16, max_length=200)
    confirmed: Literal[True]
    idempotency_key: str = Field(min_length=8, max_length=100)


class CreateOrderInput(StrictModel):
    checkout_session_id: str = Field(min_length=1, max_length=36)
    idempotency_key: str = Field(min_length=8, max_length=100)


class OrderInput(StrictModel):
    order_id: str = Field(min_length=1, max_length=36)


class ChatInput(StrictModel):
    session_id: str | None = Field(default=None, max_length=36)
    message: str = Field(min_length=1, max_length=2000)
    input_mode: Literal["text", "voice"] = "text"


class PreferenceInput(StrictModel):
    favorite_brands: list[str] = Field(default_factory=list, max_length=10)
    preferred_categories: list[str] = Field(default_factory=list, max_length=10)
    usual_sizes: dict[str, str] = Field(default_factory=dict, max_length=10)
    preferred_max_price: Decimal | None = Field(default=None, gt=0)


class AgentDecision(StrictModel):
    intent: Literal[
        "search",
        "compare",
        "add",
        "remove",
        "update",
        "cart",
        "checkout",
        "confirm",
        "status",
        "clarify",
    ]
    constraints: Constraints | None = None
    references: list[str] = Field(default_factory=list, max_length=5)
    quantity: int = Field(default=1, ge=1, le=99)
    size: str | None = None
    color: str | None = None
    clarification: str | None = None
    new_search: bool = False


JsonDict = dict[str, Any]
