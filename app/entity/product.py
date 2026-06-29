from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from xime.starters.sqlalchemy import Base, TimestampMixin


class Product(TimestampMixin, Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    popularity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # location_address: địa chỉ cơ sở đang bán sản phẩm
    location_address: Mapped[str] = mapped_column(String(255), nullable=False)
    category_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("categories.id"), nullable=True
    )
    discount_percentage: Mapped[int | None] = mapped_column(
        Integer, default=0, server_default="0", nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    is_delete: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
