"""create product_cooccurrence

Revision ID: f6a7b8c9d0e1
Revises: e5a6b7c8d9f0
Create Date: 2026-06-30

Cá nhân hóa - Phase 5: bảng materialized đồng xuất hiện sản phẩm (mua/xem cùng), dựng lại batch.
PK kép (product_id, related_product_id); cascade khi xóa product.

Personalization Phase 5: materialized product co-occurrence table.
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5a6b7c8d9f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "product_cooccurrence",
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("related_product_id", sa.BigInteger(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["related_product_id"], ["products.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("product_id", "related_product_id"),
    )
    op.create_index(
        "ix_product_cooccurrence_product_id",
        "product_cooccurrence",
        ["product_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_product_cooccurrence_product_id", table_name="product_cooccurrence"
    )
    op.drop_table("product_cooccurrence")
