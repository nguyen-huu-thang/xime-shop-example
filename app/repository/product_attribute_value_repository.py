from __future__ import annotations

from sqlalchemy import select

from app.entity.product_attribute_value import ProductAttributeValue
from xime.starters.sqlalchemy import CrudRepository


class ProductAttributeValueRepository(CrudRepository[ProductAttributeValue]):
    model = ProductAttributeValue

    async def find_by_attribute_id(self, attribute_id: int) -> list[ProductAttributeValue]:
        result = await self.session.execute(
            select(ProductAttributeValue).where(
                ProductAttributeValue.attribute_id == attribute_id
            )
        )
        return list(result.scalars().all())

    async def find_by_attribute_ids(
        self, attribute_ids: set[int]
    ) -> list[ProductAttributeValue]:
        # Batch load: gom giá trị của nhiều thuộc tính trong 1 query (chống N+1)
        # Batch load values of many attributes in one query (avoid N+1)
        if not attribute_ids:
            return []
        result = await self.session.execute(
            select(ProductAttributeValue)
            .where(ProductAttributeValue.attribute_id.in_(attribute_ids))
            .order_by(ProductAttributeValue.id.asc())
        )
        return list(result.scalars().all())

    async def find_by_value_and_attribute_id(
        self, value: str, attribute_id: int
    ) -> ProductAttributeValue | None:
        result = await self.session.execute(
            select(ProductAttributeValue)
            .where(ProductAttributeValue.value == value)
            .where(ProductAttributeValue.attribute_id == attribute_id)
        )
        return result.scalar_one_or_none()
