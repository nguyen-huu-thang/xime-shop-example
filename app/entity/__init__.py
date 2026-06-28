"""
Export Base + toàn bộ entity.

Import package này (hoặc các module con) để mọi entity đăng ký vào Base.metadata -
cần cho Alembic autogenerate.
"""
from app.entity.base import Base, TimestampMixin

# Cluster A - user & phân quyền
from app.entity.user import User
from app.entity.permission import Permission
from app.entity.group import Group
from app.entity.group_member import GroupMember
from app.entity.user_permission import UserPermission
from app.entity.group_permission import GroupPermission

# Cluster B - catalog
from app.entity.category import Category
from app.entity.product import Product
from app.entity.product_attribute import ProductAttribute
from app.entity.product_attribute_value import ProductAttributeValue
from app.entity.product_option import ProductOption
from app.entity.product_option_value import ProductOptionValue

# Cluster C - mua hàng
from app.entity.cart import Cart
from app.entity.wishlist import Wishlist
from app.entity.coupon import Coupon
from app.entity.order import Order
from app.entity.order_detail import OrderDetail

# Cluster D - tương tác & nội dung
from app.entity.review import Review
from app.entity.notification import Notification
from app.entity.interaction import Interaction
from app.entity.action import Action

# Cluster E - hạ tầng
from app.entity.file import File
from app.entity.list_table import ListTable
from app.entity.refresh_token import RefreshToken
from app.entity.blacklist_token import BlacklistToken

__all__ = [
    "Base",
    "TimestampMixin",
    "User",
    "Permission",
    "Group",
    "GroupMember",
    "UserPermission",
    "GroupPermission",
    "Category",
    "Product",
    "ProductAttribute",
    "ProductAttributeValue",
    "ProductOption",
    "ProductOptionValue",
    "Cart",
    "Wishlist",
    "Coupon",
    "Order",
    "OrderDetail",
    "Review",
    "Notification",
    "Interaction",
    "Action",
    "File",
    "ListTable",
    "RefreshToken",
    "BlacklistToken",
]
