from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from xime.starters.sqlalchemy import Base


class ProductAttributeValue(Base):
    __tablename__ = "product_attribute_values"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    attribute_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("product_attributes.id"), nullable=False
    )
    # Giá trị cụ thể: 40, 41, đỏ, xanh...
    value: Mapped[str] = mapped_column(String(50), nullable=False)
