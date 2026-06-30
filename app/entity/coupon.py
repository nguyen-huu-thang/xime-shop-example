from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from xime.starters.sqlalchemy import Base


class Coupon(Base):
    __tablename__ = "coupons"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    # discount: nếu discount_type='percent' là số phần trăm (0-100), nếu 'fixed' là số tiền
    discount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)

    # ── Nâng cấp coupon (checkout) ───────────────────────────────────────────────
    # Loại giảm: 'fixed' (số tiền) | 'percent' (%)
    discount_type: Mapped[str] = mapped_column(
        String(10), default="fixed", server_default="fixed", nullable=False
    )
    # Trần giảm tối đa khi percent (vd giảm 20% tối đa 100k); null = không trần
    max_discount: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    # Giá trị đơn tối thiểu để áp mã (tính trên tiền hàng - subtotal)
    min_order_amount: Mapped[float] = mapped_column(
        Numeric(10, 2), default=0, server_default="0", nullable=False
    )
    # Phạm vi giảm: 'product' (giảm tiền hàng) | 'shipping' (giảm phí ship)
    applies_to: Mapped[str] = mapped_column(
        String(10), default="product", server_default="product", nullable=False
    )
    # Tổng số lượt dùng cho phép; null = không giới hạn
    usage_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Đã dùng bao nhiêu lượt
    used_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    # Mỗi user chỉ dùng 1 lần (đếm qua orders.coupon_id + user_id)
    per_user_once: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
