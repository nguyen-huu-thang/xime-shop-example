from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete

from app.entity.refresh_token import RefreshToken
from xime.starters.sqlalchemy import CrudRepository


class RefreshTokenRepository(CrudRepository[RefreshToken]):
    model = RefreshToken

    async def delete_expired(self) -> None:
        # Remove tokens whose expiry has passed
        # Xóa các token đã hết hạn
        await self.session.execute(
            delete(RefreshToken).where(RefreshToken.expires_at < datetime.now(UTC))
        )
        await self.session.flush()

    async def delete_by_user_id(self, user_id: int) -> int:
        # Thu hồi mọi refresh token của một user (đặt lại mật khẩu)
        # Revoke all refresh tokens of a user (password reset)
        result = await self.session.execute(
            delete(RefreshToken).where(RefreshToken.user_id == user_id)
        )
        await self.session.flush()
        return result.rowcount

    async def delete_by_user_id_except(self, user_id: int, keep_jti: str | None) -> int:
        # Thu hồi refresh token của mọi phiên khác, GIỮ phiên hiện tại (keep_jti).
        # Revoke all other sessions' refresh tokens, keeping the current one (keep_jti).
        stmt = delete(RefreshToken).where(RefreshToken.user_id == user_id)
        if keep_jti is not None:
            stmt = stmt.where(RefreshToken.id != keep_jti)
        result = await self.session.execute(stmt)
        await self.session.flush()
        return result.rowcount
