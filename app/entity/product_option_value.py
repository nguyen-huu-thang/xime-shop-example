from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from xime.starters.sqlalchemy import Base


class ProductOptionValue(Base):
    """Bảng nối nhiều-nhiều giữa product_options và product_attribute_values."""

    __tablename__ = "product_option_values"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    option_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("product_options.id"), nullable=False
    )
    attribute_value_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("product_attribute_values.id"), nullable=False
    )
