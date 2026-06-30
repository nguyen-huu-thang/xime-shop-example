from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column

from xime.starters.sqlalchemy import Base


class Interaction(Base):
    __tablename__ = "interactions"
    # Index phục vụ đã-xem-gần-đây / trending / throttle (khớp migration d4f5a6b7c8e9)
    # Indexes for recently-viewed / trending / throttle (match migration d4f5a6b7c8e9)
    __table_args__ = (
        Index("ix_interactions_user_id_created_at", "user_id", "created_at"),
        Index(
            "ix_interactions_user_product_action",
            "user_id",
            "product_id",
            "action_id",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # Log interaction: xóa user/product thì log đi theo (ON DELETE CASCADE)
    # Interaction log: cascade-delete when the user/product is removed
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("actions.id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
