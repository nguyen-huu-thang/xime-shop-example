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

    async def find_by_option_ids(
        self, option_ids: set[int]
    ) -> list[ProductOptionValue]:
        # Batch load: gom liên kết option-value của nhiều option trong 1 query (chống N+1)
        # Batch load option-value links of many options in one query (avoid N+1)
        if not option_ids:
            return []
        result = await self.session.execute(
            select(ProductOptionValue)
            .where(ProductOptionValue.option_id.in_(option_ids))
            .order_by(ProductOptionValue.id.asc())
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
