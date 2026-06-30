from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, Integer, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from xime.starters.sqlalchemy import Base


class ProductOption(Base):
    __tablename__ = "product_options"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("products.id"), nullable=False, index=True
    )
    # Một tổ hợp lựa chọn hoàn chỉnh = 1 SKU có giá + tồn kho
    price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    stock: Mapped[int] = mapped_column(Integer, nullable=False)
