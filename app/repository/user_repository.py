from __future__ import annotations

from sqlalchemy import select

from app.entity.user import User
from xime.starters.sqlalchemy import CrudRepository


class UserRepository(CrudRepository[User]):
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

    async def find_all_paginated(self, page: int, limit: int) -> list[User]:
        # Admin user management: list all users (active + inactive) so they can be
        # activated/deactivated, ordered by id.
        # Quản trị user: liệt kê mọi user (cả đang khóa) để có thể kích hoạt/khóa lại,
        # sắp theo id.
        offset = (page - 1) * limit
        result = await self.session.execute(
            select(User).order_by(User.id.asc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all())
