"""add order checkout columns (address snapshot + payment)

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-06-30

Checkout - Phase 4/5: snapshot địa chỉ giao + tọa độ vào đơn (recipient_name/phone,
ship_lat/lng) + thông tin thanh toán giả lập (payment_provider/payment_ref/paid_at).

Checkout Phase 4/5: order address snapshot + mock payment columns.
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d0e1f2a3b4c5"
down_revision: Union[str, None] = "c9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "orders", sa.Column("recipient_name", sa.String(length=100), nullable=True)
    )
    op.add_column(
        "orders", sa.Column("recipient_phone", sa.String(length=20), nullable=True)
    )
    op.add_column(
        "orders", sa.Column("ship_lat", sa.Numeric(precision=10, scale=7), nullable=True)
    )
    op.add_column(
        "orders", sa.Column("ship_lng", sa.Numeric(precision=10, scale=7), nullable=True)
    )
    op.add_column(
        "orders",
        sa.Column(
            "payment_provider",
            sa.String(length=20),
            server_default="cod",
            nullable=False,
        ),
    )
    op.add_column(
        "orders", sa.Column("payment_ref", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "orders",
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("orders", "paid_at")
    op.drop_column("orders", "payment_ref")
    op.drop_column("orders", "payment_provider")
    op.drop_column("orders", "ship_lng")
    op.drop_column("orders", "ship_lat")
    op.drop_column("orders", "recipient_phone")
    op.drop_column("orders", "recipient_name")
