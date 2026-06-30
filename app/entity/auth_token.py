from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from xime.starters.sqlalchemy import Base


class AuthToken(Base):
    """Token/mã dùng một lần cho email bảo mật (dùng chung 1 bảng cho mọi loại).

    type: 'verify_email' | 'reset_password' | 'otp'.
    token_hash: SHA-256 hex của token/mã thô (KHÔNG lưu thô). attempts: số lần thử sai (OTP).
    Hết hạn (expires_at) hoặc đã dùng (used_at) -> không còn hiệu lực.
    """

    __tablename__ = "auth_tokens"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
