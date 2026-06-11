from __future__ import annotations

from sqlalchemy import select

from app.entity.order_detail import OrderDetail
from app.repository.base_repository import BaseRepository


class OrderDetailRepository(BaseRepository[OrderDetail]):
    model = OrderDetail

    async def find_by_order_id(self, order_id: int) -> list[OrderDetail]:
        result = await self.session.execute(
            select(OrderDetail).where(OrderDetail.order_id == order_id)
        )
        return list(result.scalars().all())
