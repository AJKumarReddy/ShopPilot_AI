from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

Json = JSON().with_variant(JSONB(), "postgresql")


def new_id() -> str:
    return str(uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Identified:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class User(Identified, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    token_hash: Mapped[str | None] = mapped_column(String(64), unique=True)


class UserPreference(Identified, Base):
    __tablename__ = "user_preferences"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    preferences: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)


class Product(Identified, Base):
    __tablename__ = "products"
    external_id: Mapped[str] = mapped_column(String(100), unique=True)
    major_category: Mapped[str] = mapped_column(String(120), index=True)
    subcategory: Mapped[str] = mapped_column(String(200), index=True)
    product_type: Mapped[str] = mapped_column(String(160), index=True)
    title: Mapped[str] = mapped_column(String(600))
    brand: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str] = mapped_column(Text)
    features: Mapped[list[str]] = mapped_column(Json, default=list)
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), index=True)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    average_rating: Mapped[Decimal] = mapped_column(Numeric(3, 2), index=True)
    rating_count: Mapped[int] = mapped_column(Integer)
    image_url: Mapped[str] = mapped_column(Text)
    attributes: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)
    source: Mapped[str] = mapped_column(String(100))
    search_text: Mapped[str] = mapped_column(Text)
    __table_args__ = (
        CheckConstraint("price > 0", name="product_positive_price"),
        CheckConstraint("average_rating >= 0 AND average_rating <= 5", name="valid_rating"),
    )


class EmbeddingIndex(Base):
    __tablename__ = "embedding_index"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    model: Mapped[str] = mapped_column(String(200))
    dimensions: Mapped[int] = mapped_column(Integer)
    version: Mapped[str] = mapped_column(String(40))


class ProductEmbedding(Base):
    __tablename__ = "product_embeddings"
    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )
    embedding: Mapped[Any] = mapped_column(Vector().with_variant(JSON(), "sqlite"))
    embedding_model: Mapped[str] = mapped_column(String(200), index=True)
    embedding_version: Mapped[str] = mapped_column(String(40))
    content_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Inventory(Base):
    __tablename__ = "inventory"
    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )
    stock_quantity: Mapped[int] = mapped_column(Integer)
    reserved_quantity: Mapped[int] = mapped_column(Integer, default=0)
    warehouse: Mapped[str] = mapped_column(String(50))
    shipping_days: Mapped[int] = mapped_column(Integer)
    discount_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    __table_args__ = (
        CheckConstraint(
            "stock_quantity >= reserved_quantity AND reserved_quantity >= 0",
            name="inventory_nonnegative",
        ),
        CheckConstraint(
            "discount_percentage >= 0 AND discount_percentage <= 100", name="valid_discount"
        ),
    )


class Review(Identified, Base):
    __tablename__ = "reviews"
    product_id: Mapped[str] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    external_id: Mapped[str] = mapped_column(String(100), unique=True)
    rating: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(600))
    text: Mapped[str] = mapped_column(Text)
    helpful_votes: Mapped[int] = mapped_column(Integer, default=0)
    review_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (CheckConstraint("rating >= 1 AND rating <= 5", name="review_rating"),)


class Cart(Identified, Base):
    __tablename__ = "carts"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="open")
    version: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (
        Index(
            "uq_open_cart_user",
            "user_id",
            unique=True,
            postgresql_where=text("status = 'open'"),
            sqlite_where=text("status = 'open'"),
        ),
    )


class CartItem(Identified, Base):
    __tablename__ = "cart_items"
    cart_id: Mapped[str] = mapped_column(ForeignKey("carts.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    variant: Mapped[str] = mapped_column(String(200), default="")
    __table_args__ = (
        UniqueConstraint("cart_id", "product_id", "variant"),
        CheckConstraint("quantity > 0 AND quantity <= 99", name="cart_quantity"),
    )


class CheckoutSession(Identified, Base):
    __tablename__ = "checkout_sessions"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    cart_id: Mapped[str] = mapped_column(ForeignKey("carts.id"), index=True)
    cart_version: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict[str, Any]] = mapped_column(Json)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmation_hash: Mapped[str] = mapped_column(String(64))


class Order(Identified, Base):
    __tablename__ = "orders"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    checkout_session_id: Mapped[str] = mapped_column(
        ForeignKey("checkout_sessions.id"), unique=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="CONFIRMED")
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    tax: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    payment_reference: Mapped[str] = mapped_column(String(100))
    __table_args__ = (UniqueConstraint("user_id", "idempotency_key"),)


class OrderItem(Identified, Base):
    __tablename__ = "order_items"
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"))
    title: Mapped[str] = mapped_column(String(600))
    variant: Mapped[str] = mapped_column(String(200), default="")
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))


class Conversation(Identified, Base):
    __tablename__ = "conversations"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    state: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)


class Message(Identified, Base):
    __tablename__ = "messages"
    session_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)


class AgentEvent(Identified, Base):
    __tablename__ = "agent_events"
    session_id: Mapped[str | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    request_id: Mapped[str | None] = mapped_column(String(36), index=True)
    operation: Mapped[str] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(200))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    details: Mapped[dict[str, Any]] = mapped_column(Json, default=dict)


class AgentCheckpoint(Base):
    __tablename__ = "agent_checkpoints"
    thread_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    checkpoint_ns: Mapped[str] = mapped_column(String(200), primary_key=True, default="")
    checkpoint_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    parent_id: Mapped[str | None] = mapped_column(String(100))
    checkpoint: Mapped[dict[str, Any]] = mapped_column(Json)
    checkpoint_metadata: Mapped[dict[str, Any]] = mapped_column(Json)
    pending_writes: Mapped[list[Any]] = mapped_column(Json, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
