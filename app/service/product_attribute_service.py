"""
ProductAttributeService - quản lý thuộc tính (loại lựa chọn: size, màu...) của sản phẩm.
Port từ ProductAttributeService.php.

Collaborator transaction-agnostic: các method KHÔNG tự mở transaction. Chúng phải chạy
BÊN TRONG một transaction do service điều phối cấp cao (ProductService) mở. Lý do: framework
Xime tạo session mới cho mỗi `transaction()` (không reentrant), nên nếu sub-service tự mở
transaction riêng khi được ProductService gọi thì sẽ mất tính atomic (commit lẻ).

Transaction-agnostic collaborator: methods do NOT open their own transaction; they run inside
one opened by the orchestrating ProductService (single atomic transaction).
"""
from __future__ import annotations

from app.entity.product_attribute import ProductAttribute
from app.exception.app_exception import AppException
from app.repository.product_attribute_repository import ProductAttributeRepository


class ProductAttributeService:
    def __init__(
        self,
        product_attribute_repository: ProductAttributeRepository,
    ) -> None:
        self._repo = product_attribute_repository

    async def create_product_attribute(
        self, product_id: int, name: str
    ) -> ProductAttribute:
        attr = ProductAttribute(product_id=product_id, name=name)
        return await self._repo.save(attr)

    async def update_product_attribute(self, attr_id: int, name: str) -> ProductAttribute:
        attr = await self._repo.find(attr_id)
        if not attr:
            raise AppException("E10500")
        attr.name = name
        return await self._repo.save(attr)

    async def find_by_id(self, attr_id: int) -> ProductAttribute | None:
        return await self._repo.find(attr_id)

    async def get_product_attribute_by_id(self, attr_id: int) -> ProductAttribute:
        attr = await self._repo.find(attr_id)
        if not attr:
            raise AppException("E10500")
        return attr

    async def find_by_product_id(self, product_id: int) -> list[ProductAttribute]:
        return await self._repo.find_by_product_id(product_id)

    async def find_by_name_and_product_id(
        self, name: str, product_id: int
    ) -> ProductAttribute | None:
        return await self._repo.find_by_name_and_product_id(name, product_id)

    async def delete_product_attribute(self, attr_id: int) -> None:
        attr = await self._repo.find(attr_id)
        if not attr:
            raise AppException("E10500")
        await self._repo.delete(attr)
