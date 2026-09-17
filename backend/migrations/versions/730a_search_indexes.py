"""PostgreSQL lexical, vector, and attribute search indexes."""

from alembic import op

revision = "730a_search_indexes"
down_revision = "3052b7e6b8c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "CREATE INDEX ix_products_fts ON products USING gin (to_tsvector('english', search_text))"
    )
    op.execute("CREATE INDEX ix_products_attributes ON products USING gin (attributes)")
    op.execute(
        "CREATE INDEX ix_embedding_hnsw ON product_embeddings USING hnsw ((embedding::vector(1536)) vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX ix_embedding_hnsw")
    op.execute("DROP INDEX ix_products_attributes")
    op.execute("DROP INDEX ix_products_fts")
