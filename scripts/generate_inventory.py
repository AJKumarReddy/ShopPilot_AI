"""Generate only missing inventory; never overwrite live stock on a rerun."""

import asyncio

from app.data.normalization import synthetic_inventory
from app.db.session import SessionFactory, engine
from app.models.entities import Inventory, Product
from sqlalchemy import select


async def run() -> None:
    async with SessionFactory() as db, db.begin():
        stream = await db.stream_scalars(
            select(Product.id)
            .outerjoin(Inventory)
            .where(Inventory.product_id.is_(None))
            .execution_options(yield_per=250)
        )
        async for product_id in stream:
            db.add(Inventory(**synthetic_inventory(product_id)))
        await db.flush()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run())
