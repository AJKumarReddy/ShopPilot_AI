from typing import Any, TypedDict


class CommerceState(TypedDict, total=False):
    session_id: str
    user_id: str
    messages: list[dict[str, str]]
    message: str
    intent: str
    shopping_constraints: dict[str, Any]
    candidate_product_ids: list[str]
    recommended_product_ids: list[str]
    selected_product_ids: list[str]
    cart_id: str | None
    checkout_session_id: str | None
    pending_confirmation: dict[str, Any] | None
    last_tool_result: dict[str, Any]
    last_order_id: str | None
    error: str | None
    decision: dict[str, Any]
    query: str
    response: str
