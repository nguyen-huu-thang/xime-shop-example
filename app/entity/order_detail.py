from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from xime.starters.sqlalchemy import Base


class OrderDetail(Base):
    __tablename__ = "order_details"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("orders.id"), nullable=False
    )
    # PHP entity tham chiếu Product trực tiếp + snapshot name/attribute/url
    product_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("products.id"), nullable=False
    )
    # Biến thể (option) đã đặt - cần để trừ kho đúng option lúc thanh toán online thành công.
    # Nullable cho đơn cũ (trước khi bổ sung cột này).
    # The ordered variant (option) - needed to decrement the right stock on online payment
    # success. Nullable for legacy orders created before this column existed.
    product_option_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("product_options.id"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    attribute: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(String(255), nullable=True)
