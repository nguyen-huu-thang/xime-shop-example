"""
Base cho mọi SQLAlchemy entity của shop.

Dùng lại `Base` + `TimestampMixin` của starter Xime để chia sẻ chung metadata
(Alembic autogenerate đọc `Base.metadata`).

    from app.entity.base import Base, TimestampMixin

    class User(Base):
        __tablename__ = "users"
        id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
"""
from xime.starters.sqlalchemy import Base, TimestampMixin

__all__ = ["Base", "TimestampMixin"]
