"""create user_category_affinity

Revision ID: e5a6b7c8d9f0
Revises: d4f5a6b7c8e9
Create Date: 2026-06-30

Cá nhân hóa - Phase 3: bảng materialized hồ sơ sở thích user theo category (decay-on-write).
PK kép (user_id, category_id); cascade khi xóa user/category.

Personalization Phase 3: materialized user-category affinity table.
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5a6b7c8d9f0"
down_revision: Union[str, None] = "d4f5a6b7c8e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_category_affinity",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("category_id", sa.BigInteger(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["category_id"], ["categories.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", "category_id"),
    )
    op.create_index(
        "ix_user_category_affinity_user_id",
        "user_category_affinity",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_user_category_affinity_user_id", table_name="user_category_affinity"
    )
    op.drop_table("user_category_affinity")
