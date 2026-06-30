from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column

from xime.starters.sqlalchemy import Base


class UserCategoryAffinity(Base):
    """Hồ sơ sở thích của user theo ngành hàng (materialized, cập nhật decay-on-write).

    score = điểm tích lũy ĐÃ decay tới `updated_at`. Khi đọc để xếp hạng, decay tiếp tới read-time.
    PK kép (user_id, category_id). Xem AffinityService cho công thức.
    """

    __tablename__ = "user_category_affinity"
    __table_args__ = (
        Index("ix_user_category_affinity_user_id", "user_id"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    category_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("categories.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # Điểm đã decay tới updated_at
    # Score already decayed up to updated_at
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
