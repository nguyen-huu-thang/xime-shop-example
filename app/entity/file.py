from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.entity.base import Base


class File(Base):
    __tablename__ = "files"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sort: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # target_id: id bản ghi trong bảng được trỏ tới (quan hệ đa hình)
    target_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)
    # list_table_id: tên bảng được file trỏ tới (FK → list_table.id)
    list_table_id: Mapped[str | None] = mapped_column(
        String(100), ForeignKey("list_table.id"), nullable=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
