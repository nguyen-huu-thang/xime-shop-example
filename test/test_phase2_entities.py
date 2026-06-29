"""
Phase 2 - Test entity, schema & seed.

- Metadata có đủ 25 bảng.
- Insert + query một entity (Category) qua transaction, gồm quan hệ cha-con.
- Order dùng các cột theo QĐ-2 (product_discount, ship_discount, payment_status bool, coupon_id).
- Seed: 51 quyền + nhóm admin tồn tại trong DB.
"""
import pytest
from sqlalchemy import select

from app.config.dependency import dependency
from xime.starters.sqlalchemy import Base
from app.entity.category import Category
from app.entity.group import Group
from app.entity.order import Order
from app.entity.permission import Permission
from xime.starters.sqlalchemy import SqlAlchemyTransactionManager
from xime.starters.sqlalchemy.session import AsyncSessionFactory
from xime.testing import TestApplication

EXPECTED_TABLES = {
    "users", "permissions", "groups", "group_members", "user_permissions",
    "group_permissions", "categories", "products", "product_attributes",
    "product_attribute_values", "product_options", "product_option_values",
    "cart", "wishlist", "coupons", "orders", "order_details", "reviews",
    "notifications", "interactions", "actions", "files", "list_table",
    "refresh_tokens", "blacklist_tokens",
}


def test_metadata_has_all_25_tables():
    names = set(Base.metadata.tables.keys())
    assert EXPECTED_TABLES <= names
    assert len(EXPECTED_TABLES) == 25


def test_order_columns_match_decision_2():
    cols = set(Order.__table__.columns.keys())
    # Theo QĐ-2
    assert {"product_discount", "ship_discount", "coupon_id", "address"} <= cols
    assert str(Order.__table__.c.payment_status.type) in ("BOOLEAN", "BOOL")
    # Không có cột 'discount' đơn lẻ của schema cũ
    assert "discount" not in cols


def test_permission_has_default_value_column():
    cols = set(Permission.__table__.columns.keys())
    assert "default_value" in cols


@pytest.mark.asyncio
async def test_insert_and_query_category_hierarchy():
    async with TestApplication(binding=dependency) as app:
        tm = app.get(SqlAlchemyTransactionManager)
        sessions = app.get(AsyncSessionFactory)

        async def _cleanup():
            async with tm():
                session = sessions.current()
                rows = (
                    await session.execute(
                        select(Category).where(Category.name.like("%(test)%"))
                    )
                ).scalars().all()
                # Xóa con trước (parent_id) rồi tới cha
                for c in sorted(rows, key=lambda x: x.parent_id is None):
                    await session.delete(c)
                    await session.flush()

        await _cleanup()  # đảm bảo sạch trước khi chạy
        try:
            created_id = None
            async with tm():
                session = sessions.current()
                parent = Category(name="Thời trang (test)", description="cha")
                session.add(parent)
                await session.flush()
                child = Category(name="Dép (test)", parent_id=parent.id)
                session.add(child)
                await session.flush()
                created_id = child.id

            # Query lại + walk cha bằng query tường minh (đa lớp, async-safe)
            async with tm():
                session = sessions.current()
                child = await session.get(Category, created_id)
                assert child is not None
                assert child.parent_id is not None
                parent = await session.get(Category, child.parent_id)
                assert parent is not None
                assert parent.name == "Thời trang (test)"
        finally:
            await _cleanup()  # luôn dọn kể cả khi assert fail


@pytest.mark.asyncio
async def test_seed_permissions_and_admin_group_present():
    async with TestApplication(binding=dependency) as app:
        tm = app.get(SqlAlchemyTransactionManager)
        sessions = app.get(AsyncSessionFactory)
        async with tm():
            session = sessions.current()
            perms = (await session.execute(select(Permission))).scalars().all()
            assert len(perms) >= 51
            names = {p.name for p in perms}
            assert {"create_category", "manage_group_permissions", "view_orders"} <= names

            admin = (
                await session.execute(select(Group).where(Group.name == "admin"))
            ).scalar_one_or_none()
            assert admin is not None
