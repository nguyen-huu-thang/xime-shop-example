from __future__ import annotations

from sqlalchemy import func, select

from app.entity.product_option import ProductOption
from app.repository.base_repository import BaseRepository


class ProductOptionRepository(BaseRepository[ProductOption]):
    model = ProductOption

    async def find_by_product_id(self, product_id: int) -> list[ProductOption]:
        result = await self.session.execute(
            select(ProductOption).where(ProductOption.product_id == product_id)
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
