from __future__ import annotations

from sqlalchemy import func, select

from app.entity.product_option import ProductOption
from xime.starters.sqlalchemy import CrudRepository


class ProductOptionRepository(CrudRepository[ProductOption]):
    model = ProductOption

    async def find_by_product_id(self, product_id: int) -> list[ProductOption]:
        result = await self.session.execute(
            select(ProductOption).where(ProductOption.product_id == product_id)
        )
        return list(result.scalars().all())

    async def find_by_product_ids(self, product_ids: set[int]) -> list[ProductOption]:
        # Batch load: gom option của nhiều sản phẩm trong 1 query (chống N+1)
        # Batch load options of many products in one query (avoid N+1)
        if not product_ids:
            return []
        result = await self.session.execute(
            select(ProductOption)
            .where(ProductOption.product_id.in_(product_ids))
            .order_by(ProductOption.id.asc())
        )
        return list(result.scalars().all())

    async def count_low_stock(self, threshold: int) -> int:
        # Đếm option có tồn kho dưới ngưỡng (cảnh báo sắp hết hàng).
        # Count options with stock below the threshold (low-stock warning).
        result = await self.session.execute(
            select(func.count())
            .select_from(ProductOption)
            .where(ProductOption.stock < threshold)
        )
        return int(result.scalar_one())
