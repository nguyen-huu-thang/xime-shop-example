from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from xime.starters.sqlalchemy import Base


class ProductOptionValue(Base):
    """Bảng nối nhiều-nhiều giữa product_options và product_attribute_values."""

    __tablename__ = "product_option_values"
    # UNIQUE (option_id, attribute_value_id): một option không nối trùng cùng một giá trị
    # UNIQUE (option_id, attribute_value_id): an option links a given value at most once
    __table_args__ = (
        UniqueConstraint(
            "option_id",
            "attribute_value_id",
            name="uq_product_option_values_option_id_attribute_value_id",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    option_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("product_options.id"), nullable=False, index=True
    )
    attribute_value_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("product_attribute_values.id"), nullable=False, index=True
    )
