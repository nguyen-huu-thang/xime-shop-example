from sqlalchemy import select

from app.entity.wishlist import Wishlist
from app.repository.base_repository import BaseRepository


class WishlistRepository(BaseRepository[Wishlist]):
    model = Wishlist

    async def find_by_user_id(self, user_id: int) -> list[Wishlist]:
        result = await self.session.execute(
            select(Wishlist).where(Wishlist.user_id == user_id)
        )
        return list(result.scalars().all())

    async def find_by_product_id(self, product_id: int) -> list[Wishlist]:
        result = await self.session.execute(
            select(Wishlist).where(Wishlist.product_id == product_id)
        )
        return list(result.scalars().all())
