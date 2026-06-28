"""
BlacklistTokenService - quản lý danh sách token bị thu hồi.
Port từ BlacklistTokenService.php.
"""
from __future__ import annotations

from datetime import UTC, datetime

from xime.core.transaction.manager import TransactionManager

from app.entity.blacklist_token import BlacklistToken
from app.repository.blacklist_token_repository import BlacklistTokenRepository


class BlacklistTokenService:
    def __init__(
        self,
        transaction: TransactionManager,
        blacklist_token_repository: BlacklistTokenRepository,
    ) -> None:
        self._transaction = transaction
        self._repo = blacklist_token_repository

    async def add_token(self, jti: str, expires_at: datetime) -> BlacklistToken:
        """Blacklist an access token id until it expires.
        Đưa jti vào blacklist cho đến khi token hết hạn tự nhiên.
        """
        async with self._transaction():
            token = BlacklistToken(id=jti, expires_at=expires_at)
            return await self._repo.save(token)

    async def is_blacklisted(self, token_id: str) -> bool:
        """Return True if token id is in blacklist and not yet expired.
        Trả về True nếu token đang trong blacklist và chưa hết hạn.
        """
        async with self._transaction():
            token = await self._repo.find(token_id)
        if token is None:
            return False
        return token.expires_at > datetime.now(UTC)

    async def delete_expired_tokens(self) -> None:
        """Purge expired blacklist entries.
        Dọn dẹp các bản ghi đã hết hạn.
        """
        async with self._transaction():
            await self._repo.delete_expired()
