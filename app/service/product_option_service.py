"""
ProductOptionService - quản lý option sản phẩm (1 SKU = 1 tổ hợp giá + tồn kho).
Port từ ProductOptionService.php.
"""
from __future__ import annotations

from xime.core.transaction.manager import TransactionManager

from app.entity.product_option import ProductOption
from app.exception.app_exception import AppException
from app.repository.product_option_repository import ProductOptionRepository


class ProductOptionService:
    def __init__(
        self,
        transaction: TransactionManager,
        product_option_repository: ProductOptionRepository,
    ) -> None:
        self._transaction = transaction
        self._repo = product_option_repository

    async def create_product_option(
        self, product_id: int, price: float | None, stock: int
    ) -> ProductOption:
        async with self._transaction():
            opt = ProductOption(product_id=product_id, price=price, stock=stock)
            return await self._repo.save(opt)

    async def update_product_option(
        self, option: ProductOption, price: float | None, stock: int | None
    ) -> ProductOption:
        async with self._transaction():
            db_opt = await self._repo.find(option.id)
            if not db_opt:
                raise AppException("E10502")
            if price is not None:
                db_opt.price = price
            if stock is not None:
                db_opt.stock = stock
            return await self._repo.save(db_opt)

    async def get_product_option_by_id(self, option_id: int) -> ProductOption:
        async with self._transaction():
            opt = await self._repo.find(option_id)
        if not opt:
            raise AppException("E10502")
        return opt

    async def find_by_product_id(self, product_id: int) -> list[ProductOption]:
        async with self._transaction():
            return await self._repo.find_by_product_id(product_id)

    async def delete_product_option(self, option_id: int) -> None:
        async with self._transaction():
            opt = await self._repo.find(option_id)
            if not opt:
                raise AppException("E10502")
            await self._repo.delete(opt)
