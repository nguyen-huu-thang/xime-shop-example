from sqlalchemy import select

from app.entity.review import Review
from app.repository.base_repository import BaseRepository


class ReviewRepository(BaseRepository[Review]):
    model = Review

    async def find_by_product_id(self, product_id: int) -> list[Review]:
        result = await self.session.execute(
            select(Review).where(Review.product_id == product_id)
        )
        return list(result.scalars().all())

    async def find_by_user_id(self, user_id: int) -> list[Review]:
        result = await self.session.execute(
            select(Review).where(Review.user_id == user_id)
        )
        return list(result.scalars().all())
