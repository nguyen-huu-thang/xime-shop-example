from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.entity.order import Order
from xime.starters.sqlalchemy import CrudRepository


class OrderRepository(CrudRepository[Order]):
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

    async def find_by_payment_ref(self, payment_ref: str) -> Order | None:
        # Tra đơn theo mã giao dịch giả lập (callback thanh toán online)
        result = await self.session.execute(
            select(Order).where(Order.payment_ref == payment_ref)
        )
        return result.scalar_one_or_none()

    async def count_by_coupon_and_user(self, coupon_id: int, user_id: int) -> int:
        # Số đơn của user đã dùng một coupon (phục vụ per_user_once)
        # How many orders this user placed with a given coupon (for per_user_once)
        result = await self.session.execute(
            select(func.count())
            .select_from(Order)
            .where(Order.coupon_id == coupon_id, Order.user_id == user_id)
        )
        return int(result.scalar_one())

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
