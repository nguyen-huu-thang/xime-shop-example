"""
RefreshTokenService - quản lý refresh token trong DB.
Port từ RefreshTokenService.php.
"""
from __future__ import annotations

from datetime import datetime

from xime.core.transaction.manager import TransactionManager

from app.entity.refresh_token import RefreshToken
from app.repository.refresh_token_repository import RefreshTokenRepository


class RefreshTokenService:
    def __init__(
        self,
        transaction: TransactionManager,
        refresh_token_repository: RefreshTokenRepository,
    ) -> None:
        self._transaction = transaction
        self._repo = refresh_token_repository

    async def create_token(self, jti: str, expires_at: datetime) -> RefreshToken:
        """Save refresh token id + expiry to DB.
        Lưu id của refresh token + hạn dùng vào DB.
        """
        async with self._transaction():
            token = RefreshToken(id=jti, expires_at=expires_at)
            return await self._repo.save(token)

    async def get_token_by_id(self, jti: str) -> RefreshToken | None:
        """Look up a refresh token by jti.
        Tra cứu refresh token theo jti.
        """
        async with self._transaction():
            return await self._repo.find(jti)

    async def delete_token(self, jti: str) -> None:
        """Remove a refresh token (called on logout).
        Xóa refresh token - gọi khi đăng xuất.
        """
        async with self._transaction():
            token = await self._repo.find(jti)
            if token:
                await self._repo.delete(token)

    async def delete_expired_tokens(self) -> None:
        """Purge all expired refresh tokens from DB.
        Dọn dẹp tất cả refresh token đã hết hạn.
        """
        async with self._transaction():
            await self._repo.delete_expired()
