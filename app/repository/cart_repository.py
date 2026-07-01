from __future__ import annotations

from sqlalchemy import select

from app.entity.cart import Cart
from app.utils.pagination import paginate
from xime.starters.sqlalchemy import CrudRepository


class CartRepository(CrudRepository[Cart]):
    model = Cart

    async def find_by_user_id(self, user_id: int) -> list[Cart]:
        result = await self.session.execute(
            select(Cart).where(Cart.user_id == user_id)
        )
        return list(result.scalars().all())

    async def find_by_user_and_option(
        self, user_id: int, product_option_id: int
    ) -> list[Cart]:
        result = await self.session.execute(
            select(Cart)
            .where(Cart.user_id == user_id)
            .where(Cart.product_option_id == product_option_id)
        )
        return list(result.scalars().all())

    async def find_by_ids(self, ids: list[int]) -> list[Cart]:
        if not ids:
            return []
        result = await self.session.execute(
            select(Cart).where(Cart.id.in_(ids))
        )
        return list(result.scalars().all())

    async def find_all_paginated(self, page: int, limit: int) -> list[Cart]:
        offset, limit = paginate(page, limit)
        result = await self.session.execute(
            select(Cart).offset(offset).limit(limit)
        )
        return list(result.scalars().all())
