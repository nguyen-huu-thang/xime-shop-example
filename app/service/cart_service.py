"""
CartService — quản lý giỏ hàng.
Port từ CartService.php.
"""
from __future__ import annotations

from xime.core.transaction.manager import TransactionManager

from app.entity.cart import Cart
from app.exception.app_exception import AppException
from app.repository.cart_repository import CartRepository
from app.repository.product_option_repository import ProductOptionRepository
from app.service.authorization_service import AuthorizationService


class CartService:
    def __init__(
        self,
        transaction: TransactionManager,
        cart_repository: CartRepository,
        product_option_repository: ProductOptionRepository,
        authorization_service: AuthorizationService,
    ) -> None:
        self._transaction = transaction
        self._repo = cart_repository
        self._option_repo = product_option_repository
        self._authz = authorization_service

    async def get_all_cart_items(self) -> list[Cart]:
        async with self._transaction():
            return await self._repo.find_all()

    async def get_paginated_cart_items(self, page: int, limit: int) -> list[Cart]:
        async with self._transaction():
            return await self._repo.find_all_paginated(page, limit)

    async def get_user_cart(self, user_id: int) -> list[Cart]:
        async with self._transaction():
            return await self._repo.find_by_user_id(user_id)

    async def get_cart_item_by_id(self, cart_id: int) -> Cart | None:
        async with self._transaction():
            return await self._repo.find(cart_id)

    async def get_cart_items_by_ids(self, ids: list[int]) -> list[Cart]:
        async with self._transaction():
            return await self._repo.find_by_ids(ids)

    async def create_cart_item(self, user_id: int, data: dict) -> Cart:
        """Add item to cart or increment quantity if already present.
        Thêm item vào giỏ hoặc tăng số lượng nếu đã có.
        """
        option_id: int = data.get("product_option_id") or data.get("productOptionId")
        quantity: int = data.get("quantity", 1)

        async with self._transaction():
            option = await self._option_repo.find(option_id)
        if not option:
            raise AppException("E10502")

        async with self._transaction():
            existing = await self._repo.find_by_user_and_option(user_id, option_id)

        if existing:
            cart = existing[0]
            new_qty = cart.quantity + quantity
            if option.stock < new_qty:
                raise AppException("E10600")  # exceeds stock
            async with self._transaction():
                db_cart = await self._repo.find(cart.id)
                if db_cart:
                    db_cart.quantity = new_qty
                    return await self._repo.save(db_cart)
            return cart
        else:
            if option.stock < quantity:
                raise AppException("E10600")
            async with self._transaction():
                cart = Cart(user_id=user_id, product_option_id=option_id, quantity=quantity)
                return await self._repo.save(cart)

    async def update_cart_item(self, cart_id: int, user, quantity: int) -> Cart:
        """Update cart quantity; check ownership/permission.
        Cập nhật số lượng giỏ hàng; kiểm tra quyền ownership.
        """
        async with self._transaction():
            cart = await self._repo.find(cart_id)
        if not cart:
            raise AppException("E10601")

        is_owned = cart.user_id == user.id
        await self._authz.require(user, "edit_carts", target_id=cart_id, is_user_owned=is_owned)

        async with self._transaction():
            db_cart = await self._repo.find(cart_id)
            if not db_cart:
                raise AppException("E10601")
            db_cart.quantity = quantity
            return await self._repo.save(db_cart)

    async def delete_cart_item(self, cart_id: int, user) -> None:
        async with self._transaction():
            cart = await self._repo.find(cart_id)
        if not cart:
            raise AppException("E10601")

        is_owned = cart.user_id == user.id
        await self._authz.require(user, "edit_carts", target_id=cart_id, is_user_owned=is_owned)

        async with self._transaction():
            db_cart = await self._repo.find(cart_id)
            if db_cart:
                await self._repo.delete(db_cart)
