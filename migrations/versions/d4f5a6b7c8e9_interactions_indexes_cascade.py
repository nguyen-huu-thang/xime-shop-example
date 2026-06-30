"""interactions indexes + ON DELETE CASCADE for user/product FK

Revision ID: d4f5a6b7c8e9
Revises: c3e4a5b6d7f8
Create Date: 2026-06-30

Cá nhân hóa - Phase 2: index cho bảng log interactions + đổi FK user_id/product_id sang
ON DELETE CASCADE (interactions là bảng nhật ký, xóa user/product thì log đi theo, không chặn).
FK action_id giữ NO ACTION (actions không bị xóa lúc chạy).

Personalization Phase 2: indexes for the interactions log + cascade-delete on user/product.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4f5a6b7c8e9"
down_revision: Union[str, None] = "c3e4a5b6d7f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Index phục vụ: đã-xem-gần-đây (user_id, created_at), trending/đếm (product_id, action_id),
    # và throttle exists-check (user_id, product_id, action_id).
    op.create_index(
        "ix_interactions_user_id_created_at",
        "interactions",
        ["user_id", "created_at"],
    )
    op.create_index("ix_interactions_product_id", "interactions", ["product_id"])
    op.create_index("ix_interactions_action_id", "interactions", ["action_id"])
    op.create_index(
        "ix_interactions_user_product_action",
        "interactions",
        ["user_id", "product_id", "action_id"],
    )

    # Đổi FK user_id / product_id sang ON DELETE CASCADE (drop + recreate)
    op.drop_constraint("interactions_user_id_fkey", "interactions", type_="foreignkey")
    op.create_foreign_key(
        "interactions_user_id_fkey",
        "interactions",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint(
        "interactions_product_id_fkey", "interactions", type_="foreignkey"
    )
    op.create_foreign_key(
        "interactions_product_id_fkey",
        "interactions",
        "products",
        ["product_id"],
        ["id"],
        ondelete="CASCADE",
    )


def downgrade() -> None:
    # Trả FK về NO ACTION (mặc định ban đầu)
    op.drop_constraint(
        "interactions_product_id_fkey", "interactions", type_="foreignkey"
    )
    op.create_foreign_key(
        "interactions_product_id_fkey",
        "interactions",
        "products",
        ["product_id"],
        ["id"],
    )
    op.drop_constraint("interactions_user_id_fkey", "interactions", type_="foreignkey")
    op.create_foreign_key(
        "interactions_user_id_fkey",
        "interactions",
        "users",
        ["user_id"],
        ["id"],
    )

    op.drop_index("ix_interactions_user_product_action", table_name="interactions")
    op.drop_index("ix_interactions_action_id", table_name="interactions")
    op.drop_index("ix_interactions_product_id", table_name="interactions")
    op.drop_index("ix_interactions_user_id_created_at", table_name="interactions")
