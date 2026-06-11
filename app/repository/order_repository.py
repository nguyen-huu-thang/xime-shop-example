from __future__ import annotations

from sqlalchemy import select

from app.entity.order import Order
from app.repository.base_repository import BaseRepository


class OrderRepository(BaseRepository[Order]):
    model = Order

    async def find_by_user_id(self, user_id: int) -> list[Order]:
        result = await self.session.execute(
            select(Order).where(Order.user_id == user_id)
        )
        return list(result.scalars().all())

    async def find_all_paginated(self, page: int, limit: int) -> list[Order]:
        offset = (page - 1) * limit
        result = await self.session.execute(
            select(Order).order_by(Order.id.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all())
