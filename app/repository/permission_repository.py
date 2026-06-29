from __future__ import annotations

from sqlalchemy import select

from app.entity.permission import Permission
from xime.starters.sqlalchemy import CrudRepository


class PermissionRepository(CrudRepository[Permission]):
    model = Permission

    async def find_by_name(self, name: str) -> Permission | None:
        result = await self.session.execute(
            select(Permission).where(Permission.name == name)
        )
        return result.scalar_one_or_none()
