"""add permission scope_type

Revision ID: b2d3f4a5c6e7
Revises: a1c2e3f4b5d6
Create Date: 2026-06-29

Thêm cột permissions.scope_type (nullable) cho phân quyền theo nhánh category.
Add permissions.scope_type column (nullable) for category-subtree scoped authorization.
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2d3f4a5c6e7"
down_revision: Union[str, None] = "a1c2e3f4b5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "permissions",
        sa.Column("scope_type", sa.String(length=20), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("permissions", "scope_type")
