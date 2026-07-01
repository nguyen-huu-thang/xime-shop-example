from __future__ import annotations

from sqlalchemy import select

from app.entity.group import Group
from app.pagination import paginate
from xime.starters.sqlalchemy import CrudRepository


class GroupRepository(CrudRepository[Group]):
    model = Group

    async def find_all_paginated(self, page: int, limit: int) -> list[Group]:
        offset, limit = paginate(page, limit)
        result = await self.session.execute(
            select(Group).offset(offset).limit(limit)
        )
        return list(result.scalars().all())

    async def find_by_name(self, name: str) -> Group | None:
        result = await self.session.execute(
            select(Group).where(Group.name == name)
        )
        return result.scalar_one_or_none()
