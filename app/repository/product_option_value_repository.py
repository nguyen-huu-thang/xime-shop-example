from __future__ import annotations

from sqlalchemy import select

from app.entity.product_option_value import ProductOptionValue
from xime.starters.sqlalchemy import CrudRepository


class ProductOptionValueRepository(CrudRepository[ProductOptionValue]):
    model = ProductOptionValue

    async def find_by_option_id(self, option_id: int) -> list[ProductOptionValue]:
        result = await self.session.execute(
            select(ProductOptionValue).where(ProductOptionValue.option_id == option_id)
        )
        return list(result.scalars().all())

    async def find_by_attribute_value_id(
        self, attribute_value_id: int
    ) -> list[ProductOptionValue]:
        result = await self.session.execute(
            select(ProductOptionValue).where(
                ProductOptionValue.attribute_value_id == attribute_value_id
            )
        )
        return list(result.scalars().all())

    async def find_by_value_and_option(
        self, attribute_value_id: int, option_id: int
    ) -> ProductOptionValue | None:
        result = await self.session.execute(
            select(ProductOptionValue)
            .where(ProductOptionValue.attribute_value_id == attribute_value_id)
            .where(ProductOptionValue.option_id == option_id)
        )
        return result.scalar_one_or_none()
