"""
Seed dữ liệu khởi tạo — port từ SetupInitialCommand.php.

Tạo danh sách quyền (~55) + nhóm 'admin' được cấp toàn bộ quyền.
Chạy:  python -m app.seed

Idempotent: chạy lại không tạo trùng (kiểm tra tồn tại trước khi insert).
Dùng DI của framework Xime (TransactionManager + AsyncSessionFactory).

Tài khoản admin (có mật khẩu) seed ở Phase 9 — cần UserService (Phase 3).
"""
from __future__ import annotations

import asyncio

from sqlalchemy import select

from xime import Application
from xime.starters.sqlalchemy import SqlAlchemyTransactionManager
from xime.starters.sqlalchemy.session import AsyncSessionFactory

from app.entity.group import Group
from app.entity.group_member import GroupMember
from app.entity.group_permission import GroupPermission
from app.entity.list_table import ListTable
from app.entity.permission import Permission
from app.entity.user import User
from app.service.list_table_service import _TABLE_DESCRIPTIONS
from app.service.user_service import UserService

# Danh sách quyền (name → mô tả) — nguồn: giải thích cơ sở dữ liệu.txt
PERMISSIONS: dict[str, str] = {
    # Quản lý người dùng
    "view_users": "Xem danh sách người dùng",
    "view_user_details": "Xem chi tiết người dùng",
    "create_user": "Tạo người dùng mới",
    "edit_user": "Chỉnh sửa thông tin người dùng",
    "delete_user": "Xóa người dùng",
    "activate_deactivate_user": "Kích hoạt/khóa người dùng",
    "manage_user_permissions": "Quản lý phân quyền cá nhân",
    # Quản lý nhóm
    "view_groups": "Xem danh sách nhóm",
    "view_group_details": "Xem chi tiết nhóm",
    "create_group": "Tạo nhóm mới",
    "edit_group": "Chỉnh sửa thông tin nhóm",
    "delete_group": "Xóa nhóm",
    "manage_group_members": "Quản lý thành viên nhóm",
    "manage_group_permissions": "Quản lý phân quyền nhóm",
    # Quản lý quyền
    "view_permissions": "Xem danh sách quyền",
    "create_permission": "Tạo quyền mới",
    "edit_permission": "Chỉnh sửa quyền",
    "delete_permission": "Xóa quyền",
    # Quản lý sản phẩm
    "view_products": "Xem danh sách sản phẩm",
    "view_product_details": "Xem chi tiết sản phẩm",
    "create_product": "Tạo sản phẩm mới",
    "edit_product": "Chỉnh sửa thông tin sản phẩm",
    "delete_product": "Xóa sản phẩm",
    "manage_featured_products": "Quản lý sản phẩm nổi bật",
    "manage_product_stock": "Quản lý số lượng tồn kho",
    # Quản lý danh mục
    "view_categories": "Xem danh sách danh mục",
    "create_category": "Tạo danh mục mới",
    "edit_category": "Chỉnh sửa danh mục",
    "delete_category": "Xóa danh mục",
    # Quản lý giỏ hàng
    "view_carts": "Xem giỏ hàng của người dùng",
    "create_cart": "Thêm sản phẩm vào giỏ hàng",
    "edit_carts": "Chỉnh sửa giỏ hàng của người dùng",
    "delete_carts": "Xóa giỏ hàng của người dùng",
    # Quản lý danh sách yêu thích
    "view_wishlists": "Xem danh sách yêu thích của người dùng",
    "edit_wishlists": "Chỉnh sửa danh sách yêu thích của người dùng",
    "delete_wishlists": "Xóa sản phẩm khỏi danh sách yêu thích",
    # Quản lý mã giảm giá
    "view_coupons": "Xem danh sách mã giảm giá",
    "create_coupon": "Tạo mã giảm giá mới",
    "edit_coupon": "Chỉnh sửa mã giảm giá",
    "delete_coupon": "Xóa mã giảm giá",
    "activate_deactivate_coupon": "Kích hoạt/Vô hiệu hóa mã giảm giá",
    # Quản lý đơn hàng
    "view_orders": "Xem danh sách đơn hàng",
    "view_order_details": "Xem chi tiết đơn hàng",
    "update_shipping_status": "Cập nhật trạng thái vận chuyển",
    "update_payment_status": "Cập nhật trạng thái thanh toán",
    "delete_order": "Xóa đơn hàng",
    # Quản lý đánh giá sản phẩm
    "view_reviews": "Xem danh sách đánh giá",
    "approve_disapprove_review": "Duyệt/Không duyệt đánh giá",
    "delete_review": "Xóa đánh giá",
    # Quản lý thông báo
    "view_notifications": "Xem danh sách thông báo",
    "create_notification": "Tạo thông báo mới",
    "delete_notification": "Xóa thông báo",
    # Quản lý toàn hệ thống
    "access_admin_dashboard": "Truy cập Dashboard quản trị",
    "manage_system_settings": "Quản lý cấu hình hệ thống",
    "view_system_logs": "Quản lý nhật ký hệ thống",
}

ADMIN_GROUP_NAME = "admin"


async def seed() -> None:
    application = Application()
    await application.start()
    try:
        tm = application.get(SqlAlchemyTransactionManager)
        sessions = application.get(AsyncSessionFactory)

        async with tm():
            session = sessions.current()

            # 1. Seed permissions (idempotent)
            existing = {
                p.name
                for p in (await session.execute(select(Permission))).scalars().all()
            }
            created = 0
            for name, desc in PERMISSIONS.items():
                if name not in existing:
                    session.add(Permission(name=name, description=desc, default_value=False))
                    created += 1
            await session.flush()
            print(f"Permissions: +{created} mới, tổng {len(PERMISSIONS)}.")

            # 2. Nhóm admin
            admin = (
                await session.execute(
                    select(Group).where(Group.name == ADMIN_GROUP_NAME)
                )
            ).scalar_one_or_none()
            if admin is None:
                admin = Group(name=ADMIN_GROUP_NAME, description="Quản trị viên — toàn quyền")
                session.add(admin)
                await session.flush()
                print(f"Tạo nhóm '{ADMIN_GROUP_NAME}'.")
            else:
                print(f"Nhóm '{ADMIN_GROUP_NAME}' đã tồn tại.")

            # 3. Cấp toàn bộ quyền cho nhóm admin (target_id=None = full)
            all_perms = (await session.execute(select(Permission))).scalars().all()
            existing_links = {
                gp.permission_id
                for gp in (
                    await session.execute(
                        select(GroupPermission).where(GroupPermission.group_id == admin.id)
                    )
                ).scalars().all()
            }
            linked = 0
            for perm in all_perms:
                if perm.id not in existing_links:
                    session.add(
                        GroupPermission(
                            group_id=admin.id,
                            permission_id=perm.id,
                            target_id=None,
                            is_active=True,
                            is_denied=False,
                        )
                    )
                    linked += 1
            print(f"Gán quyền cho nhóm admin: +{linked} mới.")

            # 4. Seed list_table (table names for polymorphic file relation)
            # Seed list_table (tên bảng dùng cho quan hệ file đa hình)
            existing_tables = {
                t.id
                for t in (await session.execute(select(ListTable))).scalars().all()
            }
            lt_added = 0
            for table_name, desc in _TABLE_DESCRIPTIONS.items():
                if table_name not in existing_tables:
                    session.add(ListTable(id=table_name, description=desc))
                    lt_added += 1
            await session.flush()
            print(f"ListTable: +{lt_added} mới, tổng {len(_TABLE_DESCRIPTIONS)}.")

            # 5. Tài khoản admin đầu tiên (username=admin, password=Admin@123)
            # Tài khoản này chỉ dùng để bắt đầu — đổi mật khẩu ngay sau khi seed
            # First admin account (change password immediately after seeding)
            admin_username = "admin"
            existing_admin = (
                await session.execute(
                    select(User).where(User.username == admin_username)
                )
            ).scalar_one_or_none()
            if existing_admin is None:
                hashed = UserService.hash_password("Admin@123")
                admin_user = User(
                    username=admin_username,
                    email="admin@shop.local",
                    password=hashed,
                    is_active=True,
                )
                session.add(admin_user)
                await session.flush()

                # Add admin user to admin group
                # Thêm user admin vào nhóm admin
                session.add(GroupMember(user_id=admin_user.id, group_id=admin.id))
                await session.flush()
                print(f"Tạo tài khoản admin (username='{admin_username}', password='Admin@123').")
                print("⚠️  Đổi mật khẩu admin ngay sau khi khởi động!")
            else:
                print(f"Tài khoản '{admin_username}' đã tồn tại.")

        print("Seed hoàn tất.")
    finally:
        await application.stop()


if __name__ == "__main__":
    asyncio.run(seed())
