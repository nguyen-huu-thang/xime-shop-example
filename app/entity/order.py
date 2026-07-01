from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from xime.starters.sqlalchemy import Base, TimestampMixin


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

    # ── Snapshot địa chỉ giao + tọa độ (checkout) ───────────────────────────────
    # Chốt tại thời điểm đặt; sửa/xóa sổ địa chỉ không ảnh hưởng đơn đã tạo.
    recipient_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    recipient_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ship_lat: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    ship_lng: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)

    # ── Thanh toán giả lập (checkout) ───────────────────────────────────────────
    # payment_provider: 'cod' | 'mock_online'
    payment_provider: Mapped[str] = mapped_column(
        String(20), default="cod", server_default="cod", nullable=False
    )
    # Mã giao dịch giả lập (uuid) cho cổng online; null với COD
    payment_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Thời điểm "thanh toán" thành công
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Hạn thanh toán cho đơn online (mock): quá hạn chưa trả -> hoàn kho + hủy đơn.
    # COD để null (thu tiền khi giao). Kho được trừ NGAY lúc đặt (giữ chỗ kiểu Shopee).
    # Payment deadline for online orders; overdue unpaid -> restock + cancel. Null for COD.
    payment_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Thời điểm đơn bị hủy (quá hạn thanh toán) - kho đã được hoàn lại.
    # When the order was cancelled (payment overdue) - stock has been restored.
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
