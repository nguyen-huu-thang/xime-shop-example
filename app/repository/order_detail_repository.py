from __future__ import annotations

from sqlalchemy import func, select

from app.entity.order_detail import OrderDetail
from app.repository.base_repository import BaseRepository


class OrderDetailRepository(BaseRepository[OrderDetail]):
    model = OrderDetail

    async def top_selling(self, limit: int) -> list[tuple[int, str, int]]:
        # Top sản phẩm bán chạy: gộp theo product_id, tổng số lượng đã bán.
        # Best-selling products: group by product_id, sum sold quantity.
        # Trả list (product_id, name, total_sold) giảm dần theo total_sold.
        result = await self.session.execute(
            select(
                OrderDetail.product_id,
                func.max(OrderDetail.name),
                func.sum(OrderDetail.quantity),
            )
            .group_by(OrderDetail.product_id)
            .order_by(func.sum(OrderDetail.quantity).desc())
            .limit(limit)
        )
        return [(int(pid), name, int(qty)) for pid, name, qty in result.all()]

    async def find_by_order_id(self, order_id: int) -> list[OrderDetail]:
        result = await self.session.execute(
            select(OrderDetail).where(OrderDetail.order_id == order_id)
        )
        return list(result.scalars().all())

    async def find_by_order_ids(self, order_ids: list[int]) -> list[OrderDetail]:
        # Batch-load details for many orders in one query (tránh N+1).
        # Tải chi tiết của nhiều đơn trong một truy vấn duy nhất.
        if not order_ids:
            return []
        result = await self.session.execute(
            select(OrderDetail).where(OrderDetail.order_id.in_(order_ids))
        )
        return list(result.scalars().all())
