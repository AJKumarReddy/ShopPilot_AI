from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import CommerceError
from app.models.entities import Inventory, Product


class CatalogRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def metadata(self, major_category: str | None = None) -> dict[str, list[str]]:
        categories = await self.db.scalars(
            select(Product.major_category)
            .join(Inventory)
            .where(Inventory.active.is_(True))
            .distinct()
            .order_by(Product.major_category)
        )
        brands = select(Product.brand).join(Inventory).where(Inventory.active.is_(True))
        if major_category:
            brands = brands.where(Product.major_category == major_category)
        return {
            "categories": list(categories),
            "brands": list(await self.db.scalars(brands.distinct().order_by(Product.brand))),
        }

    async def get(self, product_id: str, lock: bool = False) -> tuple[Product, Inventory]:
        query = select(Product, Inventory).join(Inventory).where(Product.id == product_id)
        if lock:
            query = query.with_for_update(of=Inventory)
        row = (await self.db.execute(query)).first()
        if row is None:
            raise CommerceError("Product not found.", 404)
        return row[0], row[1]
