"""
ProductAttributeValueService - quản lý giá trị thuộc tính sản phẩm (vd: 40, đỏ...).
Port từ ProductAttributeValueService.php.

Collaborator transaction-agnostic (xem ghi chú ở ProductAttributeService): không tự mở
transaction; chạy trong transaction do ProductService mở.
"""
from __future__ import annotations

from app.entity.product_attribute_value import ProductAttributeValue
from app.exception.app_exception import AppException
from app.repository.product_attribute_value_repository import ProductAttributeValueRepository


class ProductAttributeValueService:
    def __init__(
        self,
        product_attribute_value_repository: ProductAttributeValueRepository,
    ) -> None:
        self._repo = product_attribute_value_repository

    async def create_product_attribute_value(
        self, attribute_id: int, value: str
    ) -> ProductAttributeValue:
        pav = ProductAttributeValue(attribute_id=attribute_id, value=value)
        return await self._repo.save(pav)

    async def update_product_attribute_value(
        self, pav: ProductAttributeValue, value: str
    ) -> ProductAttributeValue:
        db_pav = await self._repo.find(pav.id)
        if not db_pav:
            raise AppException("E10501")
        db_pav.value = value
        return await self._repo.save(db_pav)

    async def find_by_id(self, pav_id: int) -> ProductAttributeValue | None:
        return await self._repo.find(pav_id)

    async def find_by_attribute_id(self, attribute_id: int) -> list[ProductAttributeValue]:
        return await self._repo.find_by_attribute_id(attribute_id)

    async def find_by_attribute_ids(
        self, attribute_ids: set[int]
    ) -> list[ProductAttributeValue]:
        # Batch: ủy thác cho repo gom giá trị nhiều thuộc tính (chống N+1)
        # Batch: delegate to repo to load values of many attributes (avoid N+1)
        return await self._repo.find_by_attribute_ids(attribute_ids)

    async def find_by_value_and_attribute_id(
        self, value: str, attribute_id: int
    ) -> ProductAttributeValue | None:
        return await self._repo.find_by_value_and_attribute_id(value, attribute_id)

    async def delete_product_attribute_value(self, pav_id: int) -> None:
        pav = await self._repo.find(pav_id)
        if not pav:
            raise AppException("E10501")
        await self._repo.delete(pav)
