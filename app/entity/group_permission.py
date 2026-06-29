from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

from xime.starters.sqlalchemy import Base


class GroupPermission(Base):
    __tablename__ = "group_permissions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("groups.id", ondelete="CASCADE"), nullable=False
    )
    permission_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("permissions.id", ondelete="CASCADE"), nullable=False
    )
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    is_denied: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
