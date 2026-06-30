from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from xime.starters.sqlalchemy import Base, TimestampMixin


class UserAddress(TimestampMixin, Base):
    """Sổ địa chỉ giao hàng của người dùng (có tọa độ để hiển thị bản đồ).

    Order snapshot lại địa chỉ + tọa độ lúc đặt nên xóa/sửa địa chỉ ở đây không ảnh
    hưởng đơn đã tạo.
    """

    __tablename__ = "user_addresses"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    recipient_name: Mapped[str] = mapped_column(String(100), nullable=False)
    recipient_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    province: Mapped[str] = mapped_column(String(100), nullable=False)
    district: Mapped[str] = mapped_column(String(100), nullable=False)
    ward: Mapped[str] = mapped_column(String(100), nullable=False)
    detail: Mapped[str] = mapped_column(String(255), nullable=False)
    # Coordinates for map display (demo); nullable - người dùng có thể không chọn
    # Tọa độ để hiển thị bản đồ (demo); cho phép null
    lat: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    lng: Mapped[float | None] = mapped_column(Numeric(10, 7), nullable=True)
    is_default: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )

    def full_address(self) -> str:
        """Gộp địa chỉ dạng người-đọc (snapshot vào order.address)."""
        parts = [self.detail, self.ward, self.district, self.province]
        return ", ".join(p for p in parts if p)
