from __future__ import annotations

from sqlalchemy import select

from app.entity.user import User
from app.repository.base_repository import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def find_by_username(self, username: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()

    async def find_by_email(self, email: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()
