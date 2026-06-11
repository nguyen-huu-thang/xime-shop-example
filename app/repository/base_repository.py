"""
BaseRepository — CRUD chung cho mọi repository (thay Doctrine ServiceEntityRepository).

Pattern Xime: repository inject `AsyncSessionFactory`, lấy session hiện tại qua
`self._sessions.current()`. Session chỉ tồn tại bên trong `async with transaction()`
mở ở tầng service — kể cả thao tác đọc.

    class UserRepository(BaseRepository[User]):
        model = User

        async def find_by_username(self, username: str) -> User | None:
            result = await self.session.execute(
                select(User).where(User.username == username)
            )
            return result.scalar_one_or_none()
"""
from __future__ import annotations

from typing import Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from xime.starters.sqlalchemy import Base
from xime.starters.sqlalchemy.session import AsyncSessionFactory

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    # Subclass bắt buộc gán entity class:  model = User
    model: type[T]

    def __init__(self, sessions: AsyncSessionFactory) -> None:
        # Factory cung cấp session đang active của transaction hiện tại
        self._sessions = sessions

    @property
    def session(self) -> AsyncSession:
        """Session đang active. Raise nếu gọi ngoài transaction."""
        return self._sessions.current()

    async def find(self, id_: object) -> T | None:
        # Tra theo khóa chính
        return await self.session.get(self.model, id_)

    async def find_all(self) -> list[T]:
        result = await self.session.execute(select(self.model))
        return list(result.scalars().all())

    async def count(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(self.model))
        return int(result.scalar_one())

    async def save(self, entity: T) -> T:
        # add + flush để lấy id; commit do transaction ở service lo
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def delete(self, entity: T) -> None:
        await self.session.delete(entity)
        await self.session.flush()
