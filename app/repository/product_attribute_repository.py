from __future__ import annotations

from sqlalchemy import select

from app.entity.product_attribute import ProductAttribute
from xime.starters.sqlalchemy import CrudRepository


class ProductAttributeRepository(CrudRepository[ProductAttribute]):
    model = ProductAttribute

    async def find_by_product_id(self, product_id: int) -> list[ProductAttribute]:
        result = await self.session.execute(
            select(ProductAttribute).where(ProductAttribute.product_id == product_id)
        )
        return list(result.scalars().all())

    async def find_by_name_and_product_id(
        self, name: str, product_id: int
    ) -> ProductAttribute | None:
        result = await self.session.execute(
            select(ProductAttribute)
            .where(ProductAttribute.name == name)
            .where(ProductAttribute.product_id == product_id)
        )
        return result.scalar_one_or_none()
