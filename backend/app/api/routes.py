import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator import CommerceOrchestrator
from app.ai.factory import get_ai
from app.ai.openrouter_client import AIError, OpenRouterClient, RealOpenRouterClient, Usage
from app.core.config import get_settings
from app.core.errors import CommerceError
from app.db.session import get_db
from app.models.entities import AgentEvent, Conversation, Message, Order, User, UserPreference
from app.observability.telemetry import COMMERCE_ACTIONS, request_id
from app.repositories.catalog import CatalogRepository
from app.schemas.commerce import (
    CartAdd,
    CartUpdate,
    ChatInput,
    CompareInput,
    ConfirmInput,
    CreateOrderInput,
    PreferenceInput,
    SearchRequest,
)
from app.security.auth import current_user
from app.services.cart import CartService
from app.services.catalog import product_view
from app.services.checkout import CheckoutService

router = APIRouter(prefix="/api/v1")
Db = Annotated[AsyncSession, Depends(get_db)]
Identity = Annotated[User, Depends(current_user)]
AI = Annotated[OpenRouterClient, Depends(get_ai)]
LOG = logging.getLogger(__name__)


@router.get("/ready")
async def ready(db: Db) -> dict[str, str]:
    await db.execute(text("SELECT id FROM products LIMIT 1"))
    await db.execute(text("SELECT version_num FROM alembic_version"))
    return {"status": "ready"}


@router.get("/config")
async def public_config() -> dict[str, str]:
    settings = get_settings()
    return {
        "ai_mode": settings.ai_mode,
        "dataset_mode": settings.dataset_mode,
        "auth_mode": settings.auth_mode,
    }


@router.post("/products/search")
async def search_products(args: SearchRequest, db: Db, ai: AI) -> dict[str, Any]:
    from app.search.hybrid import HybridSearch

    return await HybridSearch(db, ai, get_settings()).search(args)


@router.post("/products/compare")
async def compare_products(args: CompareInput, db: Db) -> dict[str, Any]:
    repo = CatalogRepository(db)
    return {
        "products": [
            product_view(*(await repo.get(pid))) for pid in dict.fromkeys(args.product_ids)
        ]
    }


@router.get("/products/{product_id}")
async def get_product(product_id: str, db: Db) -> dict[str, Any]:
    return product_view(*(await CatalogRepository(db).get(product_id)))


@router.get("/cart")
async def get_cart(db: Db, user: Identity) -> dict[str, Any]:
    return await CartService(db, user.id, get_settings()).view()


@router.post("/cart/items")
async def add_cart_item(args: CartAdd, db: Db, user: Identity) -> dict[str, Any]:
    result = await CartService(db, user.id, get_settings()).add(args)
    COMMERCE_ACTIONS.labels("cart_add").inc()
    return result


@router.patch("/cart/items/{item_id}")
async def update_cart_item(
    item_id: str, args: CartUpdate, db: Db, user: Identity
) -> dict[str, Any]:
    return await CartService(db, user.id, get_settings()).change(item_id, args.quantity)


@router.delete("/cart/items/{item_id}")
async def remove_cart_item(item_id: str, db: Db, user: Identity) -> dict[str, Any]:
    return await CartService(db, user.id, get_settings()).change(item_id, None)


@router.post("/checkout/prepare")
async def prepare_checkout(db: Db, user: Identity) -> dict[str, Any]:
    COMMERCE_ACTIONS.labels("checkout_attempt").inc()
    return await CheckoutService(db, user.id, get_settings()).prepare()


@router.post("/checkout/confirm")
async def confirm_checkout(args: ConfirmInput, db: Db, user: Identity) -> dict[str, Any]:
    service = CheckoutService(db, user.id, get_settings())
    await service.confirm(args)
    result = await service.create_order(
        CreateOrderInput(
            checkout_session_id=args.checkout_session_id, idempotency_key=args.idempotency_key
        )
    )
    COMMERCE_ACTIONS.labels("confirmed_order").inc()
    return result


@router.get("/orders")
async def list_orders(db: Db, user: Identity) -> dict[str, Any]:
    ids = (
        await db.scalars(
            select(Order.id)
            .where(Order.user_id == user.id)
            .order_by(Order.created_at.desc())
            .limit(50)
        )
    ).all()
    service = CheckoutService(db, user.id, get_settings())
    return {"orders": [await service.order_view(order_id) for order_id in ids]}


@router.get("/orders/{order_id}")
async def get_order(order_id: str, db: Db, user: Identity) -> dict[str, Any]:
    return await CheckoutService(db, user.id, get_settings()).order_view(order_id)


@router.get("/preferences")
async def get_preferences(db: Db, user: Identity) -> dict[str, Any]:
    preference = await db.scalar(select(UserPreference).where(UserPreference.user_id == user.id))
    return preference.preferences if preference else {}


@router.put("/preferences")
async def save_preferences(args: PreferenceInput, db: Db, user: Identity) -> dict[str, Any]:
    await CartService(db, user.id, get_settings()).lock_user()
    preference = await db.scalar(select(UserPreference).where(UserPreference.user_id == user.id))
    if not preference:
        preference = UserPreference(user_id=user.id)
        db.add(preference)
    preference.preferences = args.model_dump(mode="json")
    return preference.preferences


async def run_chat(
    args: ChatInput, db: AsyncSession, user: User, ai: OpenRouterClient, emit: Any = None
) -> dict[str, Any]:
    usages: list[Usage] = []
    if isinstance(ai, RealOpenRouterClient):

        async def sink(usage: Usage) -> None:
            usages.append(usage)

        ai.usage_sink = sink
    result = await CommerceOrchestrator(db, user.id, ai, get_settings(), emit).run(
        args.message, args.session_id
    )
    for usage in usages:
        db.add(
            AgentEvent(
                session_id=result["session_id"], request_id=request_id.get(), **usage.__dict__
            )
        )
    db.add(
        AgentEvent(
            session_id=result["session_id"],
            request_id=request_id.get(),
            operation=result["intent"],
            details={"status": "success"},
        )
    )
    return result


@router.post("/chat")
async def chat(args: ChatInput, db: Db, user: Identity, ai: AI) -> dict[str, Any]:
    return await run_chat(args, db, user, ai)


@router.get("/chat/{session_id}")
async def history(session_id: str, db: Db, user: Identity) -> dict[str, Any]:
    conversation = await db.scalar(
        select(Conversation).where(Conversation.id == session_id, Conversation.user_id == user.id)
    )
    if not conversation:
        raise CommerceError("Conversation not found.", 404)
    messages = (
        await db.scalars(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at.desc())
            .limit(100)
        )
    ).all()
    return {
        "session_id": session_id,
        "messages": [{"role": m.role, "content": m.content} for m in reversed(messages)],
    }


@router.post("/chat/stream")
async def stream_chat(
    args: ChatInput, request: Request, db: Db, user: Identity, ai: AI
) -> StreamingResponse:
    async def events() -> AsyncIterator[str]:
        queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()

        async def emit(status: str) -> None:
            await queue.put(("status", {"status": status}))

        async def worker() -> None:
            try:
                result = await run_chat(args, db, user, ai, emit)
                # Commit BEFORE reporting success; streaming has already sent HTTP headers.
                await db.commit()
                await queue.put(("result", result))
            except (CommerceError, AIError) as exc:
                await db.rollback()
                await queue.put(("error", {"message": str(exc)}))
            except (SQLAlchemyError, Exception):
                await db.rollback()
                LOG.error("chat_stream_failed")
                await queue.put(
                    (
                        "error",
                        {"message": "ShopPilot is temporarily unavailable. Please try again."},
                    )
                )
            finally:
                await queue.put(("done", {}))

        task = asyncio.create_task(worker())
        try:
            while True:
                try:
                    event, data = await asyncio.wait_for(queue.get(), timeout=10)
                except TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                if event == "done":
                    break
                yield f"event: {event}\ndata: {json.dumps(data)}\n\n"
        finally:
            if not task.done():
                task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                await db.rollback()

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
