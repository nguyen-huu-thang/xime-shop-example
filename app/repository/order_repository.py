from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

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

    # ── Dashboard aggregates ─────────────────────────────────────────

    async def revenue_paid(self) -> float:
        # Tổng doanh thu từ đơn đã thanh toán (payment_status=True).
        # Total revenue from paid orders.
        result = await self.session.execute(
            select(func.coalesce(func.sum(Order.total_amount), 0)).where(
                Order.payment_status.is_(True)
            )
        )
        return float(result.scalar_one())

    async def count_unpaid(self) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(Order).where(Order.payment_status.is_(False))
        )
        return int(result.scalar_one())

    async def count_created_since(self, since: datetime) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(Order).where(Order.created_at >= since)
        )
        return int(result.scalar_one())
