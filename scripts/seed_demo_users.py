"""Idempotently seed identities and the bundled, curated Amazon demo catalog."""

import asyncio
import json
from pathlib import Path

from app.core.config import get_settings
from app.data.normalization import synthetic_inventory
from app.db.session import SessionFactory, engine
from app.models.entities import Inventory, Product, User, UserPreference
from app.security.auth import DEMO_USER_ID, token_hash


async def seed() -> None:
    settings = get_settings()
    async with SessionFactory() as db, db.begin():
        user = await db.get(User, DEMO_USER_ID)
        if not user:
            db.add(
                User(
                    id=DEMO_USER_ID,
                    email="demo@shoppilot.example",
                    name="Alex",
                    token_hash=token_hash(settings.demo_auth_token.get_secret_value()),
                )
            )
            await db.flush()
            db.add(UserPreference(user_id=DEMO_USER_ID, preferences={}))
        else:
            user.token_hash = token_hash(settings.demo_auth_token.get_secret_value())
        path = Path(__file__).resolve().parents[1] / "data/samples/products.jsonl"
        count = 0
        if settings.dataset_mode == "demo" and path.exists():
            with path.open(encoding="utf-8") as source:
                for line in source:
                    record = json.loads(line)
                    if not await db.get(Product, record["id"]):
                        db.add(Product(**record))
                        await db.flush()
                        db.add(Inventory(**synthetic_inventory(record["id"])))
                        count += 1
        print(f"Demo account ready; inserted {count} catalog products.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
