from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.entity.base import Base


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # default_value: fallback của check_permission khi user/nhóm không có quyền (QĐ-3)
    # Tên cột theo đúng PHP entity (defaultValue → default_value)
    default_value: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
