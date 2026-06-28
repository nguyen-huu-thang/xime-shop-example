from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.entity.base import Base, TimestampMixin


class Order(TimestampMixin, Base):
    """Đơn hàng. Cấu trúc theo QĐ-2 (lấy Order.php làm chuẩn + coupon_id)."""

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False
    )
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    payment_method: Mapped[str] = mapped_column(String(50), nullable=False)
    address: Mapped[str] = mapped_column(String(255), default="", server_default="", nullable=False)
    shipping_status: Mapped[str] = mapped_column(
        String(50), default="pending", server_default="pending", nullable=False
    )
    # payment_status kiểu Boolean (theo Order.php)
    payment_status: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    shipping_fee: Mapped[float] = mapped_column(
        Numeric(10, 2), default=0, server_default="0", nullable=False
    )
    product_discount: Mapped[float] = mapped_column(
        Numeric(10, 2), default=0, server_default="0", nullable=False
    )
    ship_discount: Mapped[float] = mapped_column(
        Numeric(10, 2), default=0, server_default="0", nullable=False
    )
    # coupon_id nullable - bổ sung theo QĐ-2 để liên kết coupon ↔ order
    coupon_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("coupons.id"), nullable=True
    )
