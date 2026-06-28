from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.entity.base import Base


class ListTable(Base):
    """Liệt kê tên bảng - phục vụ quan hệ đa hình của files.

    Lưu ý: tên bảng là 'list_table' (số ít) và PK là cột 'id' (string) theo PHP entity.
    """

    __tablename__ = "list_table"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
