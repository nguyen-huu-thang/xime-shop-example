"""add orders.payment_deadline + orders.cancelled_at

Revision ID: a8c9d0e1f2b3
Revises: f7b8c9d0e1a2
Create Date: 2026-07-01

Giữ chỗ tồn kho kiểu Shopee: đơn online (mock) trừ kho NGAY lúc đặt và có hạn thanh toán
(payment_deadline). Quá hạn chưa trả -> job hoàn kho + đánh dấu cancelled_at. COD để null.

Reserve-on-order (Shopee-like): online orders decrement stock at creation and carry a
payment deadline; overdue unpaid orders get restocked and cancelled by a job.
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a8c9d0e1f2b3"
down_revision: Union[str, None] = "f7b8c9d0e1a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("payment_deadline", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("orders", "cancelled_at")
    op.drop_column("orders", "payment_deadline")
