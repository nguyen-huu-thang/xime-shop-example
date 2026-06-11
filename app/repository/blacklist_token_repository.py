from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete

from app.entity.blacklist_token import BlacklistToken
from app.repository.base_repository import BaseRepository


class BlacklistTokenRepository(BaseRepository[BlacklistToken]):
    model = BlacklistToken

    async def delete_expired(self) -> None:
        # Remove expired entries to keep the table lean
        # Xóa các bản ghi hết hạn để giữ bảng gọn nhẹ
        await self.session.execute(
            delete(BlacklistToken).where(BlacklistToken.expires_at < datetime.now(UTC))
        )
        await self.session.flush()
