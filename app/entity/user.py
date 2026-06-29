from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from xime.starters.sqlalchemy import Base, TimestampMixin


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(15), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    # Superadmin bypasses all permission checks (set only for the initial admin / trusted owner)
    # Superadmin vượt qua mọi kiểm tra quyền (chỉ đặt cho admin khởi tạo / chủ hệ thống tin cậy)
    is_superadmin: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false", nullable=False)
