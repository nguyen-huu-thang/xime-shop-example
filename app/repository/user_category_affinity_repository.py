from __future__ import annotations

from sqlalchemy import select

from app.entity.user_category_affinity import UserCategoryAffinity
from xime.starters.sqlalchemy import CrudRepository


class UserCategoryAffinityRepository(CrudRepository[UserCategoryAffinity]):
    model = UserCategoryAffinity

    async def get_one(
        self, user_id: int, category_id: int
    ) -> UserCategoryAffinity | None:
        # PK kép -> không dùng find() của CrudRepository (vốn cho PK đơn).
        # Composite PK -> custom lookup instead of CrudRepository.find().
        result = await self.session.execute(
            select(UserCategoryAffinity)
            .where(UserCategoryAffinity.user_id == user_id)
            .where(UserCategoryAffinity.category_id == category_id)
        )
        return result.scalar_one_or_none()

    async def find_by_user(self, user_id: int) -> list[UserCategoryAffinity]:
        result = await self.session.execute(
            select(UserCategoryAffinity).where(
                UserCategoryAffinity.user_id == user_id
            )
        )
        return list(result.scalars().all())
