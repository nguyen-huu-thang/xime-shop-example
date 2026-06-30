"""auth_tokens + refresh_tokens.user_id + users.email_verified

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-06-30

Email bảo mật - tạo bảng auth_tokens (token/mã dùng một lần: verify_email/reset_password/otp),
thêm refresh_tokens.user_id (để thu hồi toàn bộ phiên khi reset mật khẩu), users.email_verified.

Security email: create auth_tokens, add refresh_tokens.user_id, users.email_verified.
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # users.email_verified
    op.add_column(
        "users",
        sa.Column(
            "email_verified", sa.Boolean(), server_default="false", nullable=False
        ),
    )

    # refresh_tokens.user_id (nullable - token cũ chưa có; token mới luôn set)
    op.add_column(
        "refresh_tokens", sa.Column("user_id", sa.BigInteger(), nullable=True)
    )
    op.create_foreign_key(
        "fk_refresh_tokens_user_id",
        "refresh_tokens",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"]
    )

    # auth_tokens
    op.create_table(
        "auth_tokens",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_auth_tokens_type_hash", "auth_tokens", ["type", "token_hash"]
    )
    op.create_index(
        "ix_auth_tokens_user_type", "auth_tokens", ["user_id", "type"]
    )


def downgrade() -> None:
    op.drop_index("ix_auth_tokens_user_type", table_name="auth_tokens")
    op.drop_index("ix_auth_tokens_type_hash", table_name="auth_tokens")
    op.drop_table("auth_tokens")

    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_constraint("fk_refresh_tokens_user_id", "refresh_tokens", type_="foreignkey")
    op.drop_column("refresh_tokens", "user_id")

    op.drop_column("users", "email_verified")
