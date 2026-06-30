from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from xime.starters.sqlalchemy import Base


class RefreshToken(Base):
    """Lưu id của refresh token + hạn + chủ sở hữu (để thu hồi toàn bộ phiên khi reset mật khẩu)."""

    __tablename__ = "refresh_tokens"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # user_id để thu hồi mọi refresh token của user khi đặt lại mật khẩu (quên mật khẩu).
    # nullable=True vì token cũ (trước migration) chưa có; token mới luôn set.
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
