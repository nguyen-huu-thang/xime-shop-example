"""upgrade coupons (discount_type, limits, scope)

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-06-30

Checkout - Phase 2: nâng cấp coupon - thêm loại giảm %/số tiền (+ trần), đơn tối thiểu,
scope SP/ship, giới hạn lượt dùng, mỗi-user-một-lần.

Checkout Phase 2: coupon upgrade columns.
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c9d0e1f2a3b4"
down_revision: Union[str, None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "coupons",
        sa.Column(
            "discount_type",
            sa.String(length=10),
            server_default="fixed",
            nullable=False,
        ),
    )
    op.add_column(
        "coupons",
        sa.Column("max_discount", sa.Numeric(precision=10, scale=2), nullable=True),
    )
    op.add_column(
        "coupons",
        sa.Column(
            "min_order_amount",
            sa.Numeric(precision=10, scale=2),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "coupons",
        sa.Column(
            "applies_to",
            sa.String(length=10),
            server_default="product",
            nullable=False,
        ),
    )
    op.add_column(
        "coupons", sa.Column("usage_limit", sa.Integer(), nullable=True)
    )
    op.add_column(
        "coupons",
        sa.Column(
            "used_count", sa.Integer(), server_default="0", nullable=False
        ),
    )
    op.add_column(
        "coupons",
        sa.Column(
            "per_user_once",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("coupons", "per_user_once")
    op.drop_column("coupons", "used_count")
    op.drop_column("coupons", "usage_limit")
    op.drop_column("coupons", "applies_to")
    op.drop_column("coupons", "min_order_amount")
    op.drop_column("coupons", "max_discount")
    op.drop_column("coupons", "discount_type")
