from __future__ import annotations

from sqlalchemy import select

from app.entity.category import Category
from xime.starters.sqlalchemy import CrudRepository


class CategoryRepository(CrudRepository[Category]):
    model = Category

    async def find_by_parent_id(self, parent_id: int) -> list[Category]:
        result = await self.session.execute(
            select(Category).where(Category.parent_id == parent_id)
        )
        return list(result.scalars().all())

    async def find_root_categories(self) -> list[Category]:
        result = await self.session.execute(
            select(Category).where(Category.parent_id.is_(None))
        )
        return list(result.scalars().all())
