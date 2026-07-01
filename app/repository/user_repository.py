from __future__ import annotations

from sqlalchemy import select

from app.entity.user import User
from app.pagination import paginate
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

    async def all_active_ids(self) -> list[int]:
        # Id mọi user đang hoạt động (phục vụ broadcast thông báo)
        # Ids of all active users (for notification broadcast)
        result = await self.session.execute(
            select(User.id).where(User.is_active == True)  # noqa: E712
        )
        return [int(r) for r in result.scalars().all()]

    async def find_all_paginated(self, page: int, limit: int) -> list[User]:
        # Admin user management: list all users (active + inactive), NEWEST FIRST so recently
        # registered users are visible on page 1 (consistent with orders/files admin lists).
        # Quản trị user: liệt kê mọi user (cả đang khóa), MỚI NHẤT TRƯỚC để user vừa đăng ký
        # hiện ở trang 1 (nhất quán với danh sách admin của orders/files).
        offset, limit = paginate(page, limit)
        result = await self.session.execute(
            select(User).order_by(User.id.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all())
