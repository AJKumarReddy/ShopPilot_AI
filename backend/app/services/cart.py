from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import CommerceError
from app.models.entities import Cart, CartItem, Inventory, Product, User
from app.repositories.catalog import CatalogRepository
from app.schemas.commerce import CartAdd
from app.services.catalog import effective_price, money, product_view


class CartService:
    def __init__(self, db: AsyncSession, user_id: str, settings: Settings) -> None:
        self.db, self.user_id, self.settings = db, user_id, settings

    async def lock_user(self) -> None:
        user = await self.db.scalar(select(User).where(User.id == self.user_id).with_for_update())
        if user is None:
            raise CommerceError("Account not found.", 401)

    async def get_or_create(self) -> Cart:
        await self.lock_user()
        cart = await self.db.scalar(
            select(Cart).where(Cart.user_id == self.user_id, Cart.status == "open")
        )
        if cart is None:
            cart = Cart(user_id=self.user_id)
            self.db.add(cart)
            await self.db.flush()
        return cart

    async def view(self, cart: Cart | None = None, validate: bool = False) -> dict[str, Any]:
        cart = cart or await self.get_or_create()
        if cart.user_id != self.user_id:
            raise CommerceError("Cart not found.", 404)
        rows = (
            await self.db.execute(
                select(CartItem, Product, Inventory)
                .join(Product, CartItem.product_id == Product.id)
                .join(Inventory, Inventory.product_id == Product.id)
                .where(CartItem.cart_id == cart.id)
                .order_by(CartItem.id)
            )
        ).all()
        subtotal, discounts = Decimal(0), Decimal(0)
        items = []
        for item, product, inventory in rows:
            if validate:
                self.validate_stock(inventory, item.quantity)
            price = effective_price(product, inventory)
            subtotal += price * item.quantity
            discounts += (product.price - price) * item.quantity
            items.append(
                {
                    "id": item.id,
                    "product": product_view(product, inventory),
                    "quantity": item.quantity,
                    "variant": item.variant,
                    "unit_price": str(price),
                    "line_total": str(money(price * item.quantity)),
                }
            )
        subtotal = money(subtotal)
        tax = money(subtotal * Decimal(self.settings.tax_rate))
        return {
            "id": cart.id,
            "version": cart.version,
            "items": items,
            "subtotal": str(subtotal),
            "discounts": str(money(discounts)),
            "tax": str(tax),
            "total": str(money(subtotal + tax)),
            "currency": "USD",
        }

    @staticmethod
    def validate_stock(inventory: Inventory, quantity: int) -> None:
        if (
            not inventory.active
            or quantity > inventory.stock_quantity - inventory.reserved_quantity
        ):
            raise CommerceError(
                "This quantity is unavailable. Please choose fewer items or another product."
            )

    async def add(self, args: CartAdd) -> dict[str, Any]:
        cart = await self.get_or_create()
        product, inventory = await CatalogRepository(self.db).get(args.product_id, lock=True)
        variants = []
        for key, value in (("size", args.size), ("color", args.color)):
            if value:
                known = product.attributes.get(key + "s", product.attributes.get(key, []))
                known = known if isinstance(known, list) else [known]
                if value.casefold() not in [str(v).casefold() for v in known]:
                    raise CommerceError(f"That {key} is not listed for this product.")
                variants.append(f"{key}: {value}")
        variant = ", ".join(variants)
        item = await self.db.scalar(
            select(CartItem).where(
                CartItem.cart_id == cart.id,
                CartItem.product_id == product.id,
                CartItem.variant == variant,
            )
        )
        existing = list(
            (
                await self.db.scalars(
                    select(CartItem).where(
                        CartItem.cart_id == cart.id, CartItem.product_id == product.id
                    )
                )
            ).all()
        )
        self.validate_stock(inventory, sum(i.quantity for i in existing) + args.quantity)
        if item:
            if item.quantity + args.quantity > 99:
                raise CommerceError("The maximum quantity is 99.")
            item.quantity += args.quantity
        else:
            self.db.add(
                CartItem(
                    cart_id=cart.id, product_id=product.id, quantity=args.quantity, variant=variant
                )
            )
        cart.version += 1
        await self.db.flush()
        return await self.view(cart)

    async def change(self, item_id: str, quantity: int | None) -> dict[str, Any]:
        cart = await self.get_or_create()
        item = await self.db.scalar(
            select(CartItem).where(CartItem.id == item_id, CartItem.cart_id == cart.id)
        )
        if item is None:
            raise CommerceError("Cart item not found.", 404)
        if quantity is None:
            await self.db.delete(item)
        else:
            _, inventory = await CatalogRepository(self.db).get(item.product_id, lock=True)
            siblings = (
                await self.db.scalars(
                    select(CartItem).where(
                        CartItem.cart_id == cart.id,
                        CartItem.product_id == item.product_id,
                        CartItem.id != item.id,
                    )
                )
            ).all()
            self.validate_stock(inventory, quantity + sum(i.quantity for i in siblings))
            item.quantity = quantity
        cart.version += 1
        await self.db.flush()
        return await self.view(cart)
