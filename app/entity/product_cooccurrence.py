from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column

from xime.starters.sqlalchemy import Base


class ProductCooccurrence(Base):
    """Đồng xuất hiện sản phẩm (mua/xem cùng), materialized - dựng lại theo batch.

    Lưu cặp có hướng (product_id -> related_product_id) + số lần đồng xuất hiện `count`,
    để truy vấn "sản phẩm liên quan tới P" chỉ cần WHERE product_id = P ORDER BY count DESC.
    PK kép (product_id, related_product_id). Xem CooccurrenceService.
    """

    __tablename__ = "product_cooccurrence"
    __table_args__ = (
        Index("ix_product_cooccurrence_product_id", "product_id"),
    )

    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("products.id", ondelete="CASCADE"),
        primary_key=True,
    )
    related_product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("products.id", ondelete="CASCADE"),
        primary_key=True,
    )
    count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
