import hashlib
import secrets
from datetime import UTC, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import CommerceError
from app.models.entities import Cart, CheckoutSession, Inventory, Order, OrderItem, utcnow
from app.schemas.commerce import ConfirmInput, CreateOrderInput
from app.services.cart import CartService
from app.services.payment import MockPaymentService


class CheckoutService:
    def __init__(self, db: AsyncSession, user_id: str, settings: Settings) -> None:
        self.db, self.user_id, self.settings = db, user_id, settings
        self.cart = CartService(db, user_id, settings)

    async def prepare(self) -> dict[str, Any]:
        cart = await self.cart.get_or_create()
        snapshot = await self.cart.view(cart, validate=True)
        if not snapshot["items"]:
            raise CommerceError("Your cart is empty.")
        token = secrets.token_urlsafe(32)
        checkout = CheckoutSession(
            user_id=self.user_id,
            cart_id=cart.id,
            cart_version=cart.version,
            snapshot=snapshot,
            total=Decimal(snapshot["total"]),
            expires_at=utcnow() + timedelta(seconds=self.settings.checkout_ttl_seconds),
            confirmation_hash=hashlib.sha256(token.encode()).hexdigest(),
        )
        self.db.add(checkout)
        await self.db.flush()
        return {
            "id": checkout.id,
            "snapshot": snapshot,
            "total": str(checkout.total),
            "expires_at": checkout.expires_at.isoformat(),
            "confirmation_token": token,
            "confirmed": False,
            "message": "Would you like me to place this order?",
        }

    async def owned_checkout(self, checkout_id: str) -> CheckoutSession:
        await self.cart.lock_user()
        checkout = await self.db.scalar(
            select(CheckoutSession)
            .where(CheckoutSession.id == checkout_id, CheckoutSession.user_id == self.user_id)
            .with_for_update()
        )
        if checkout is None:
            raise CommerceError("Checkout not found.", 404)
        return checkout

    @staticmethod
    def validate_expiry(checkout: CheckoutSession) -> None:
        if checkout.expires_at.replace(tzinfo=UTC) <= utcnow():
            raise CommerceError("Checkout expired. Please prepare checkout again.")

    async def confirm(self, args: ConfirmInput) -> CheckoutSession:
        checkout = await self.owned_checkout(args.checkout_session_id)
        if not secrets.compare_digest(
            checkout.confirmation_hash, hashlib.sha256(args.confirmation_token.encode()).hexdigest()
        ):
            raise CommerceError("Invalid confirmation token.", 403)
        if not checkout.consumed_at:
            self.validate_expiry(checkout)
        checkout.confirmed_at = checkout.confirmed_at or utcnow()
        await self.db.flush()
        return checkout

    async def create_order(self, args: CreateOrderInput) -> dict[str, Any]:
        checkout = await self.owned_checkout(args.checkout_session_id)
        existing = await self.db.scalar(
            select(Order).where(
                Order.user_id == self.user_id, Order.checkout_session_id == checkout.id
            )
        )
        if existing:
            return await self.order_view(existing.id)
        reused = await self.db.scalar(
            select(Order).where(
                Order.user_id == self.user_id, Order.idempotency_key == args.idempotency_key
            )
        )
        if reused:
            raise CommerceError("Idempotency key was already used for another checkout.")
        if checkout.confirmed_at is None:
            raise CommerceError("Explicit checkout confirmation is required.", 403)
        self.validate_expiry(checkout)
        cart = await self.db.get(Cart, checkout.cart_id)
        if not cart or cart.status != "open" or cart.version != checkout.cart_version:
            raise CommerceError("Your cart changed. Please review a new checkout.")
        ids = sorted({item["product"]["id"] for item in checkout.snapshot["items"]})
        inventories = (
            await self.db.scalars(
                select(Inventory)
                .where(Inventory.product_id.in_(ids))
                .order_by(Inventory.product_id)
                .with_for_update()
            )
        ).all()
        current = await self.cart.view(cart, validate=True)
        snapshot_prices = [
            (i["id"], i["quantity"], i["unit_price"]) for i in checkout.snapshot["items"]
        ]
        current_prices = [(i["id"], i["quantity"], i["unit_price"]) for i in current["items"]]
        if current_prices != snapshot_prices or current["total"] != str(checkout.total):
            raise CommerceError("Prices changed. Please review a new checkout before confirming.")
        quantities: dict[str, int] = {}
        for item in current["items"]:
            pid = item["product"]["id"]
            quantities[pid] = quantities.get(pid, 0) + item["quantity"]
        if len(inventories) != len(ids):
            raise CommerceError("Inventory changed. Please prepare checkout again.")
        for inventory in inventories:
            self.cart.validate_stock(inventory, quantities[inventory.product_id])
        payment_reference = await MockPaymentService(self.settings.payment_mode).charge(checkout.id)
        order = Order(
            user_id=self.user_id,
            checkout_session_id=checkout.id,
            idempotency_key=args.idempotency_key,
            subtotal=Decimal(current["subtotal"]),
            tax=Decimal(current["tax"]),
            total=checkout.total,
            payment_reference=payment_reference,
        )
        self.db.add(order)
        await self.db.flush()
        for item in current["items"]:
            self.db.add(
                OrderItem(
                    order_id=order.id,
                    product_id=item["product"]["id"],
                    title=item["product"]["title"],
                    variant=item["variant"],
                    quantity=item["quantity"],
                    unit_price=Decimal(item["unit_price"]),
                )
            )
        for inventory in inventories:
            inventory.stock_quantity -= quantities[inventory.product_id]
        cart.status = "closed"
        checkout.consumed_at = utcnow()
        await self.db.flush()
        return await self.order_view(order.id)

    async def order_view(self, order_id: str) -> dict[str, Any]:
        order = await self.db.scalar(
            select(Order).where(Order.id == order_id, Order.user_id == self.user_id)
        )
        if order is None:
            raise CommerceError("Order not found.", 404)
        items = (
            await self.db.scalars(select(OrderItem).where(OrderItem.order_id == order.id))
        ).all()
        return {
            "id": order.id,
            "status": order.status,
            "total": str(order.total),
            "subtotal": str(order.subtotal),
            "tax": str(order.tax),
            "created_at": order.created_at.isoformat(),
            "payment": "mock",
            "items": [
                {
                    "product_id": i.product_id,
                    "title": i.title,
                    "quantity": i.quantity,
                    "variant": i.variant,
                    "unit_price": str(i.unit_price),
                }
                for i in items
            ],
        }
