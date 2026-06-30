"""
ProductOptionValueService - bảng nối option ↔ attribute_value.
Port từ ProductOptionValueService.php.

Collaborator transaction-agnostic (xem ghi chú ở ProductAttributeService): không tự mở
transaction; chạy trong transaction do ProductService mở.
"""
from __future__ import annotations

from app.entity.product_option_value import ProductOptionValue
from app.exception.app_exception import AppException
from app.repository.product_option_value_repository import ProductOptionValueRepository


class ProductOptionValueService:
    def __init__(
        self,
        product_option_value_repository: ProductOptionValueRepository,
    ) -> None:
        self._repo = product_option_value_repository

    async def create_product_option_value(
        self, option_id: int, attribute_value_id: int
    ) -> ProductOptionValue:
        pov = ProductOptionValue(
            option_id=option_id, attribute_value_id=attribute_value_id
        )
        return await self._repo.save(pov)

    async def find_by_option_id(self, option_id: int) -> list[ProductOptionValue]:
        return await self._repo.find_by_option_id(option_id)

    async def find_by_option_ids(
        self, option_ids: set[int]
    ) -> list[ProductOptionValue]:
        # Batch: ủy thác cho repo gom liên kết option-value nhiều option (chống N+1)
        # Batch: delegate to repo to load option-value links of many options (avoid N+1)
        return await self._repo.find_by_option_ids(option_ids)

    async def find_by_value_and_option(
        self, attribute_value_id: int, option_id: int
    ) -> ProductOptionValue | None:
        return await self._repo.find_by_value_and_option(attribute_value_id, option_id)

    async def delete_product_option_value(self, pov_id: int) -> None:
        pov = await self._repo.find(pov_id)
        if not pov:
            raise AppException("E10503")
        await self._repo.delete(pov)
