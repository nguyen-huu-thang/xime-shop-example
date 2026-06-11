"""
ProductOptionValueService — bảng nối option ↔ attribute_value.
Port từ ProductOptionValueService.php.
"""
from __future__ import annotations

from xime.core.transaction.manager import TransactionManager

from app.entity.product_option_value import ProductOptionValue
from app.exception.app_exception import AppException
from app.repository.product_option_value_repository import ProductOptionValueRepository


class ProductOptionValueService:
    def __init__(
        self,
        transaction: TransactionManager,
        product_option_value_repository: ProductOptionValueRepository,
    ) -> None:
        self._transaction = transaction
        self._repo = product_option_value_repository

    async def create_product_option_value(
        self, option_id: int, attribute_value_id: int
    ) -> ProductOptionValue:
        async with self._transaction():
            pov = ProductOptionValue(
                option_id=option_id, attribute_value_id=attribute_value_id
            )
            return await self._repo.save(pov)

    async def find_by_option_id(self, option_id: int) -> list[ProductOptionValue]:
        async with self._transaction():
            return await self._repo.find_by_option_id(option_id)

    async def find_by_value_and_option(
        self, attribute_value_id: int, option_id: int
    ) -> ProductOptionValue | None:
        async with self._transaction():
            return await self._repo.find_by_value_and_option(attribute_value_id, option_id)

    async def delete_product_option_value(self, pov_id: int) -> None:
        async with self._transaction():
            pov = await self._repo.find(pov_id)
            if not pov:
                raise AppException("E10503")
            await self._repo.delete(pov)
