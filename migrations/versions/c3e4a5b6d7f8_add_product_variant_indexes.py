"""add product variant indexes and unique constraints

Revision ID: c3e4a5b6d7f8
Revises: b2d3f4a5c6e7
Create Date: 2026-06-30

Thêm index cho các khóa ngoại của nhóm bảng product/variant (Postgres không tự tạo index FK)
và UNIQUE chặn dữ liệu rác. Mục tiêu: gỡ N+1 + tăng tốc các truy vấn find_by_*_id.

Add FK indexes for the product/variant tables (Postgres does not auto-create FK indexes) plus
UNIQUE constraints to block duplicate rows. Supports the N+1 removal work.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3e4a5b6d7f8"
down_revision: Union[str, None] = "b2d3f4a5c6e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # FK indexes (Postgres không tự tạo index cho khóa ngoại)
    # FK indexes (Postgres does not auto-create indexes for foreign keys)
    op.create_index(
        "ix_product_attributes_product_id", "product_attributes", ["product_id"]
    )
    op.create_index(
        "ix_product_attribute_values_attribute_id",
        "product_attribute_values",
        ["attribute_id"],
    )
    op.create_index(
        "ix_product_options_product_id", "product_options", ["product_id"]
    )
    op.create_index(
        "ix_product_option_values_option_id", "product_option_values", ["option_id"]
    )
    op.create_index(
        "ix_product_option_values_attribute_value_id",
        "product_option_values",
        ["attribute_value_id"],
    )

    # UNIQUE chặn dữ liệu rác (đã kiểm tra không có bản ghi trùng trước khi thêm)
    # UNIQUE constraints to block duplicate rows (verified no duplicates beforehand)
    op.create_unique_constraint(
        "uq_product_attributes_product_id_name",
        "product_attributes",
        ["product_id", "name"],
    )
    op.create_unique_constraint(
        "uq_product_option_values_option_id_attribute_value_id",
        "product_option_values",
        ["option_id", "attribute_value_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_product_option_values_option_id_attribute_value_id",
        "product_option_values",
        type_="unique",
    )
    op.drop_constraint(
        "uq_product_attributes_product_id_name",
        "product_attributes",
        type_="unique",
    )
    op.drop_index(
        "ix_product_option_values_attribute_value_id",
        table_name="product_option_values",
    )
    op.drop_index(
        "ix_product_option_values_option_id", table_name="product_option_values"
    )
    op.drop_index("ix_product_options_product_id", table_name="product_options")
    op.drop_index(
        "ix_product_attribute_values_attribute_id",
        table_name="product_attribute_values",
    )
    op.drop_index(
        "ix_product_attributes_product_id", table_name="product_attributes"
    )
