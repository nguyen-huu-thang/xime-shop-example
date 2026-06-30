"""add notification link column

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-06-30

Thông báo - Phase 1: thêm cột `link` (đường dẫn FE bấm vào điều hướng) + index
(user_id, is_read) phục vụ hộp thư người dùng + đếm chưa đọc.

Notification Phase 1: add `link` column + (user_id, is_read) index for the per-user inbox.
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "notifications",
        sa.Column("link", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_notifications_user_id_is_read",
        "notifications",
        ["user_id", "is_read"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_notifications_user_id_is_read", table_name="notifications"
    )
    op.drop_column("notifications", "link")
