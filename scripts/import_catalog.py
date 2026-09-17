import argparse
import asyncio
from pathlib import Path

from app.data.normalization import synthetic_inventory
from app.db.session import SessionFactory, engine
from app.models.entities import Inventory, Product
from validate_catalog import load_catalog


async def run(path: Path) -> None:
    products = load_catalog(path)
    for start in range(0, len(products), 250):
        async with SessionFactory() as db, db.begin():
            for product in products[start : start + 250]:
                if not await db.get(Product, product["id"]):
                    db.add(Product(**product))
                    await db.flush()
                    db.add(Inventory(**synthetic_inventory(product["id"])))
        print(f"Imported through {min(start + 250, len(products))}/{len(products)}")
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    asyncio.run(run(parser.parse_args().path))
