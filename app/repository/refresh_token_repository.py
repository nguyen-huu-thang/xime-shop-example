from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete

from app.entity.refresh_token import RefreshToken
from app.repository.base_repository import BaseRepository


class RefreshTokenRepository(BaseRepository[RefreshToken]):
    model = RefreshToken

    async def delete_expired(self) -> None:
        # Remove tokens whose expiry has passed
        # Xóa các token đã hết hạn
        await self.session.execute(
            delete(RefreshToken).where(RefreshToken.expires_at < datetime.now(UTC))
        )
        await self.session.flush()
