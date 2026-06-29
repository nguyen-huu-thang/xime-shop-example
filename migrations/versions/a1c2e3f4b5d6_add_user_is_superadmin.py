"""add user is_superadmin

Revision ID: a1c2e3f4b5d6
Revises: 7d62679560d0
Create Date: 2026-06-29

Thêm cột users.is_superadmin (Boolean, default false) cho cơ chế superadmin bypass.
Add users.is_superadmin column for the superadmin-bypass mechanism.
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1c2e3f4b5d6"
down_revision: Union[str, None] = "7d62679560d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_superadmin",
            sa.Boolean(),
            server_default="false",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "is_superadmin")
