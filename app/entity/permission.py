from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from xime.starters.sqlalchemy import Base


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
    # scope_type: null = quyền cấp hành động/khớp đúng đối tượng (như cũ);
    #             'category' = target_id mang nghĩa category, khớp theo nhánh cây (subtree).
    # scope_type: null = action-level / exact-object match; 'category' = target_id is a category,
    # matched along the category subtree.
    scope_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
