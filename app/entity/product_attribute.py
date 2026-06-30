from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from xime.starters.sqlalchemy import Base


class ProductAttribute(Base):
    __tablename__ = "product_attributes"
    # UNIQUE (product_id, name): mỗi sản phẩm không trùng tên thuộc tính
    # UNIQUE (product_id, name): no duplicate attribute name per product
    __table_args__ = (
        UniqueConstraint(
            "product_id", "name", name="uq_product_attributes_product_id_name"
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("products.id"), nullable=False, index=True
    )
    # Loại lựa chọn: size, màu sắc...
    name: Mapped[str] = mapped_column(String(50), nullable=False)
