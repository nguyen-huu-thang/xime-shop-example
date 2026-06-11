"""
ProductAttributeService — quản lý thuộc tính (loại lựa chọn: size, màu...) của sản phẩm.
Port từ ProductAttributeService.php.
"""
from __future__ import annotations

from xime.core.transaction.manager import TransactionManager

from app.entity.product_attribute import ProductAttribute
from app.exception.app_exception import AppException
from app.repository.product_attribute_repository import ProductAttributeRepository


class ProductAttributeService:
    def __init__(
        self,
        transaction: TransactionManager,
        product_attribute_repository: ProductAttributeRepository,
    ) -> None:
        self._transaction = transaction
        self._repo = product_attribute_repository

    async def create_product_attribute(
        self, product_id: int, name: str
    ) -> ProductAttribute:
        async with self._transaction():
            attr = ProductAttribute(product_id=product_id, name=name)
            return await self._repo.save(attr)

    async def update_product_attribute(self, attr_id: int, name: str) -> ProductAttribute:
        async with self._transaction():
            attr = await self._repo.find(attr_id)
            if not attr:
                raise AppException("E10500")
            attr.name = name
            return await self._repo.save(attr)

    async def get_product_attribute_by_id(self, attr_id: int) -> ProductAttribute:
        async with self._transaction():
            attr = await self._repo.find(attr_id)
        if not attr:
            raise AppException("E10500")
        return attr

    async def find_by_product_id(self, product_id: int) -> list[ProductAttribute]:
        async with self._transaction():
            return await self._repo.find_by_product_id(product_id)

    async def find_by_name_and_product_id(
        self, name: str, product_id: int
    ) -> ProductAttribute | None:
        async with self._transaction():
            return await self._repo.find_by_name_and_product_id(name, product_id)

    async def delete_product_attribute(self, attr_id: int) -> None:
        async with self._transaction():
            attr = await self._repo.find(attr_id)
            if not attr:
                raise AppException("E10500")
            await self._repo.delete(attr)
