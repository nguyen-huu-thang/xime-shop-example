from sqlalchemy import select

from app.entity.review import Review
from app.pagination import paginate
from xime.starters.sqlalchemy import CrudRepository


class ReviewRepository(CrudRepository[Review]):
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

    async def find_approved_by_product_id(
        self, product_id: int, page: int, limit: int
    ) -> list[Review]:
        # Approved reviews of a product, newest first, paginated (public listing)
        # Đánh giá đã duyệt của sản phẩm, mới nhất trước, có phân trang (công khai)
        offset, limit = paginate(page, limit)
        result = await self.session.execute(
            select(Review)
            .where(Review.product_id == product_id)
            .where(Review.is_approved.is_(True))
            .order_by(Review.id.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())
