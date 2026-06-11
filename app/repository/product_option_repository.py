from __future__ import annotations

from sqlalchemy import select

from app.entity.product_option import ProductOption
from app.repository.base_repository import BaseRepository


class ProductOptionRepository(BaseRepository[ProductOption]):
    model = ProductOption

    async def find_by_product_id(self, product_id: int) -> list[ProductOption]:
        result = await self.session.execute(
            select(ProductOption).where(ProductOption.product_id == product_id)
        )
        return list(result.scalars().all())
