from __future__ import annotations

from sqlalchemy import select

from app.entity.product_attribute_value import ProductAttributeValue
from app.repository.base_repository import BaseRepository


class ProductAttributeValueRepository(BaseRepository[ProductAttributeValue]):
    model = ProductAttributeValue

    async def find_by_attribute_id(self, attribute_id: int) -> list[ProductAttributeValue]:
        result = await self.session.execute(
            select(ProductAttributeValue).where(
                ProductAttributeValue.attribute_id == attribute_id
            )
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
