"""add order_details.product_option_id

Revision ID: f7b8c9d0e1a2
Revises: e1f2a3b4c5d6
Create Date: 2026-07-01

Bổ sung cột order_details.product_option_id (biến thể đã đặt) để khi thanh toán online
thành công có thể trừ kho đúng option. Cột nullable cho đơn cũ.

Add order_details.product_option_id so online payment success can decrement the exact
ordered variant's stock. Nullable for legacy rows.
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f7b8c9d0e1a2"
down_revision: Union[str, None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "order_details",
        sa.Column("product_option_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_order_details_product_option_id",
        "order_details",
        "product_options",
        ["product_option_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_order_details_product_option_id", "order_details", type_="foreignkey"
    )
    op.drop_column("order_details", "product_option_id")
