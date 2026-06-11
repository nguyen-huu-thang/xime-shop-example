"""
ProductAttributeValueService — quản lý giá trị thuộc tính sản phẩm (vd: 40, đỏ...).
Port từ ProductAttributeValueService.php.
"""
from __future__ import annotations

from xime.core.transaction.manager import TransactionManager

from app.entity.product_attribute_value import ProductAttributeValue
from app.exception.app_exception import AppException
from app.repository.product_attribute_value_repository import ProductAttributeValueRepository


class ProductAttributeValueService:
    def __init__(
        self,
        transaction: TransactionManager,
        product_attribute_value_repository: ProductAttributeValueRepository,
    ) -> None:
        self._transaction = transaction
        self._repo = product_attribute_value_repository

    async def create_product_attribute_value(
        self, attribute_id: int, value: str
    ) -> ProductAttributeValue:
        async with self._transaction():
            pav = ProductAttributeValue(attribute_id=attribute_id, value=value)
            return await self._repo.save(pav)

    async def update_product_attribute_value(
        self, pav: ProductAttributeValue, value: str
    ) -> ProductAttributeValue:
        async with self._transaction():
            db_pav = await self._repo.find(pav.id)
            if not db_pav:
                raise AppException("E10501")
            db_pav.value = value
            return await self._repo.save(db_pav)

    async def find_by_attribute_id(self, attribute_id: int) -> list[ProductAttributeValue]:
        async with self._transaction():
            return await self._repo.find_by_attribute_id(attribute_id)

    async def find_by_value_and_attribute_id(
        self, value: str, attribute_id: int
    ) -> ProductAttributeValue | None:
        async with self._transaction():
            return await self._repo.find_by_value_and_attribute_id(value, attribute_id)

    async def delete_product_attribute_value(self, pav_id: int) -> None:
        async with self._transaction():
            pav = await self._repo.find(pav_id)
            if not pav:
                raise AppException("E10501")
            await self._repo.delete(pav)
