from datetime import timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import CommerceError
from app.models.entities import CheckoutSession, Inventory, Order, Product, utcnow
from app.schemas.commerce import CartAdd, ConfirmInput, Constraints, CreateOrderInput
from app.security.auth import DEMO_USER_ID
from app.services.cart import CartService
from app.services.checkout import CheckoutService


async def test_cart_totals_stock_and_ownership(db: AsyncSession) -> None:
    cart = CartService(db, DEMO_USER_ID, Settings())
    view = await cart.add(CartAdd(product_id="product-0", quantity=2))
    assert view["subtotal"] == "160.00"
    assert view["tax"] == "13.20"
    assert view["total"] == "173.20"
    with pytest.raises(CommerceError):
        await cart.add(CartAdd(product_id="product-0", quantity=10))
    with pytest.raises(CommerceError, match="not found"):
        await CartService(db, "other", Settings()).change(view["items"][0]["id"], 1)
    updated = await cart.change(view["items"][0]["id"], 1)
    assert updated["subtotal"] == "80.00"
    assert (await cart.change(view["items"][0]["id"], None))["items"] == []


async def test_cart_merges_only_matching_variants_and_checks_combined_stock(
    db: AsyncSession,
) -> None:
    product = await db.get(Product, "product-0")
    assert product
    product.attributes = {"colors": ["black", "white"]}
    cart = CartService(db, DEMO_USER_ID, Settings())
    await cart.add(CartAdd(product_id=product.id, quantity=2, color="black"))
    await cart.add(CartAdd(product_id=product.id, quantity=3, color="white"))
    view = await cart.add(CartAdd(product_id=product.id, quantity=1, color="black"))
    assert {item["variant"]: item["quantity"] for item in view["items"]} == {
        "color: black": 3,
        "color: white": 3,
    }
    with pytest.raises(CommerceError, match="unavailable"):
        await cart.add(CartAdd(product_id=product.id, quantity=5, color="white"))
    assert (await cart.view())["subtotal"] == "480.00"


async def test_confirmation_and_idempotency(db: AsyncSession) -> None:
    await CartService(db, DEMO_USER_ID, Settings()).add(CartAdd(product_id="product-0"))
    checkout = CheckoutService(db, DEMO_USER_ID, Settings())
    prepared = await checkout.prepare()
    create = CreateOrderInput(checkout_session_id=prepared["id"], idempotency_key="test-order-key")
    with pytest.raises(CommerceError, match="confirmation"):
        await checkout.create_order(create)
    assert await db.scalar(select(func.count()).select_from(Order)) == 0
    await checkout.confirm(
        ConfirmInput(
            checkout_session_id=prepared["id"],
            confirmation_token=prepared["confirmation_token"],
            confirmed=True,
            idempotency_key=create.idempotency_key,
        )
    )
    order = await checkout.create_order(create)
    assert (await checkout.create_order(create))["id"] == order["id"]
    assert await db.scalar(select(func.count()).select_from(Order)) == 1
    inventory = await db.get(Inventory, "product-0")
    assert inventory and inventory.stock_quantity == 9
    with pytest.raises(CommerceError):
        await CheckoutService(db, "other", Settings()).order_view(order["id"])


@pytest.mark.parametrize("change", ["price", "cart", "expiry", "stock"])
async def test_stale_checkout_rejected(db: AsyncSession, change: str) -> None:
    cart = CartService(db, DEMO_USER_ID, Settings())
    await cart.add(CartAdd(product_id="product-0"))
    service = CheckoutService(db, DEMO_USER_ID, Settings())
    prepared = await service.prepare()
    args = ConfirmInput(
        checkout_session_id=prepared["id"],
        confirmation_token=prepared["confirmation_token"],
        confirmed=True,
        idempotency_key="stale-checkout",
    )
    await service.confirm(args)
    if change == "price":
        product = await db.get(Product, "product-0")
        assert product
        product.price = Decimal("99.99")
    elif change == "cart":
        await cart.add(CartAdd(product_id="product-1"))
    elif change == "stock":
        inventory = await db.get(Inventory, "product-0")
        assert inventory
        inventory.stock_quantity = 0
    else:
        checkout = await db.get(CheckoutSession, prepared["id"])
        assert checkout
        checkout.expires_at = utcnow() - timedelta(seconds=1)
    await db.flush()
    with pytest.raises(CommerceError):
        await service.create_order(
            CreateOrderInput(
                checkout_session_id=prepared["id"], idempotency_key=args.idempotency_key
            )
        )
    assert await db.scalar(select(func.count()).select_from(Order)) == 0


@pytest.mark.parametrize("mode", ["declined", "processing_error"])
async def test_payment_failure_rolls_back(db: AsyncSession, mode: str) -> None:
    service = CheckoutService(db, DEMO_USER_ID, Settings(payment_mode=mode))
    await service.cart.add(CartAdd(product_id="product-0"))
    await db.commit()
    with pytest.raises(CommerceError):
        async with db.begin():
            prepared = await service.prepare()
            await service.confirm(
                ConfirmInput(
                    checkout_session_id=prepared["id"],
                    confirmation_token=prepared["confirmation_token"],
                    confirmed=True,
                    idempotency_key="payment-test",
                )
            )
            await service.create_order(
                CreateOrderInput(checkout_session_id=prepared["id"], idempotency_key="payment-test")
            )
    assert await db.scalar(select(func.count()).select_from(Order)) == 0
    inventory = await db.get(Inventory, "product-0")
    assert inventory and inventory.stock_quantity == 10


def test_tool_and_constraint_validation() -> None:
    with pytest.raises(ValidationError):
        CartAdd(product_id="p", quantity=0)
    with pytest.raises(ValidationError):
        Constraints(min_price=200, max_price=100)
    with pytest.raises(ValidationError):
        ConfirmInput(
            checkout_session_id="c",
            confirmation_token="x" * 32,
            confirmed=False,
            idempotency_key="test-key",
        )
