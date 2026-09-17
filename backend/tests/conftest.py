from collections.abc import AsyncIterator
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.entities import Base, Inventory, Product, User
from app.security.auth import DEMO_USER_ID


@pytest.fixture
async def db() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(User(id=DEMO_USER_ID, email="demo@example.test", name="Demo"))
        session.add(User(id="other", email="other@example.test", name="Other"))
        for index in range(8):
            session.add(
                Product(
                    id=f"product-{index}",
                    external_id=f"TEST{index}",
                    major_category="Electronics",
                    subcategory="Headphones",
                    product_type="headphones",
                    title=f"Wireless noise cancelling headphones {index}",
                    brand="Test Brand",
                    description="Wireless noise cancelling headphones. 40 hour battery life.",
                    features=["wireless", "noise cancelling", "40 hour battery"],
                    price=Decimal(80 + index * 15),
                    average_rating=Decimal("4.5"),
                    rating_count=100 + index,
                    image_url="https://example.test/image.jpg",
                    attributes={"color": "black", "battery_life": "40 hours"},
                    source="test-fixture",
                    search_text="wireless noise cancelling headphones 40 hour battery life",
                )
            )
        await session.flush()
        for index in range(8):
            session.add(
                Inventory(
                    product_id=f"product-{index}",
                    stock_quantity=10,
                    warehouse="WH-MO-01",
                    shipping_days=2,
                )
            )
        await session.commit()
        yield session
    await engine.dispose()
