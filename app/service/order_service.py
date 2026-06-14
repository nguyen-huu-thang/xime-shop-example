"""
OrderService — quản lý đơn hàng.
Port từ OrderService.php.

create_order dùng single transaction để đảm bảo atomicity:
  order + order_details + giảm tồn kho + xóa cart items.
"""
from __future__ import annotations

import json

from xime.core.transaction.manager import TransactionManager

from app.entity.order import Order
from app.entity.order_detail import OrderDetail
from app.exception.app_exception import AppException
from app.repository.cart_repository import CartRepository
from app.repository.order_detail_repository import OrderDetailRepository
from app.repository.order_repository import OrderRepository
from app.repository.product_attribute_repository import ProductAttributeRepository
from app.repository.product_attribute_value_repository import ProductAttributeValueRepository
from app.repository.product_option_repository import ProductOptionRepository
from app.repository.product_option_value_repository import ProductOptionValueRepository
from app.service.authorization_service import AuthorizationService


class OrderService:
    def __init__(
        self,
        transaction: TransactionManager,
        order_repository: OrderRepository,
        order_detail_repository: OrderDetailRepository,
        cart_repository: CartRepository,
        product_option_repository: ProductOptionRepository,
        product_option_value_repository: ProductOptionValueRepository,
        product_attribute_value_repository: ProductAttributeValueRepository,
        product_attribute_repository: ProductAttributeRepository,
        authorization_service: AuthorizationService,
    ) -> None:
        self._transaction = transaction
        self._order_repo = order_repository
        self._detail_repo = order_detail_repository
        self._cart_repo = cart_repository
        self._option_repo = product_option_repository
        self._option_val_repo = product_option_value_repository
        self._attr_val_repo = product_attribute_value_repository
        self._attr_repo = product_attribute_repository
        self._authz = authorization_service

    async def _build_order_dto(self, order: Order) -> list:
        async with self._transaction():
            details = await self._detail_repo.find_by_order_id(order.id)
        arr = [
            [d.id, d.name, float(d.price), d.quantity, d.url]
            for d in details
        ]
        return [order, arr]

    async def get_all_orders(self) -> list:
        async with self._transaction():
            orders = await self._order_repo.find_all()
        result = []
        for order in orders:
            result.append(await self._build_order_dto(order))
        return result

    async def get_paginated_orders(self, page: int, limit: int) -> list:
        async with self._transaction():
            orders = await self._order_repo.find_all_paginated(page, limit)
        result = []
        for order in orders:
            result.append(await self._build_order_dto(order))
        return result

    async def find_orders_by_user(self, user_id: int) -> list:
        async with self._transaction():
            orders = await self._order_repo.find_by_user_id(user_id)
        result = []
        for order in orders:
            result.append(await self._build_order_dto(order))
        return result

    async def find_order_by_id(self, order_id: int) -> Order | None:
        async with self._transaction():
            return await self._order_repo.find(order_id)

    async def get_order_by_id(self, order_id: int) -> list:
        async with self._transaction():
            order = await self._order_repo.find(order_id)
        if not order:
            raise AppException("E10500")
        return await self._build_order_dto(order)

    async def _get_option_attributes(self, option_id: int) -> str:
        """Build JSON attribute snapshot for OrderDetail (mirrors getValuesByOption).
        Build JSON snapshot thuộc tính cho OrderDetail.
        """
        async with self._transaction():
            opt_vals = await self._option_val_repo.find_by_option_id(option_id)
        result: dict[str, str] = {}
        for ov in opt_vals:
            async with self._transaction():
                pav = await self._attr_val_repo.find(ov.attribute_value_id)
            if pav:
                async with self._transaction():
                    attr = await self._attr_repo.find(pav.attribute_id)
                if attr:
                    result[attr.name] = pav.value
        return json.dumps(result)

    async def create_order(self, user_id: int, data: dict) -> list:
        """Create order + details + decrement stock + clear cart (atomic).
        Tạo đơn hàng + chi tiết + giảm tồn kho + xóa giỏ trong một transaction.
        """
        cart_ids: list[int] = data.get("cart") or []
        if not cart_ids:
            raise AppException("E10505")

        # Load carts and validate outside write transaction
        # Load giỏ hàng và validate trước khi mở transaction ghi
        async with self._transaction():
            cart_items = await self._cart_repo.find_by_ids(cart_ids)
        if not cart_items:
            raise AppException("E10505")

        # Validate stock and calculate subtotal
        # Kiểm tra tồn kho và tính tổng tiền
        option_cache: dict[int, object] = {}
        subtotal = 0.0
        for item in cart_items:
            async with self._transaction():
                opt = await self._option_repo.find(item.product_option_id)
            if not opt:
                raise AppException("E10502")
            if opt.stock < item.quantity:
                raise AppException("E10506")  # exceeds stock
            option_cache[item.id] = opt
            subtotal += item.quantity * float(opt.price or 0)

        # Build attribute snapshots before main transaction
        # Build snapshot thuộc tính trước transaction ghi
        attr_snapshots: dict[int, str] = {}
        for item in cart_items:
            opt = option_cache[item.id]
            attr_snapshots[item.id] = await self._get_option_attributes(opt.id)

        async with self._transaction():
            order = Order(
                user_id=user_id,
                address=data.get("address", ""),
                total_amount=subtotal,
                payment_method=data.get("paymentMethod") or data.get("payment_method", ""),
                shipping_status="Đơn hàng đã được tạo",
                payment_status=False,
            )
            order = await self._order_repo.save(order)

            detail_rows = []
            for item in cart_items:
                opt = option_cache[item.id]
                db_opt = await self._option_repo.find(opt.id)
                if not db_opt:
                    raise AppException("E10502")
                if db_opt.stock < item.quantity:
                    raise AppException("E10506")

                # Snapshot product name requires loading product
                # Snapshot tên sản phẩm cần load product
                from app.entity.product import Product
                from sqlalchemy import select as sa_select
                result = await self._order_repo.session.execute(
                    sa_select(Product).where(Product.id == db_opt.product_id)
                )
                product = result.scalar_one_or_none()
                if not product:
                    raise AppException("E10200")

                db_opt.stock -= item.quantity
                await self._option_repo.save(db_opt)

                detail = OrderDetail(
                    order_id=order.id,
                    product_id=product.id,
                    name=product.name,
                    quantity=item.quantity,
                    price=float(db_opt.price or 0),
                    attribute=attr_snapshots.get(item.id),
                    url=None,
                )
                detail = await self._detail_repo.save(detail)
                detail_rows.append([detail.id, detail.name, float(detail.price), detail.quantity, detail.url])

                # Remove cart item
                # Xóa cart item
                cart_db = await self._cart_repo.find(item.id)
                if cart_db:
                    await self._cart_repo.delete(cart_db)

        return [order, detail_rows]

    async def update_order(self, order_id: int, user, address: str) -> list:
        """Update order address; check permission (owner or update_shipping_status perm).
        Cập nhật địa chỉ đơn hàng; kiểm tra quyền.
        """
        async with self._transaction():
            order = await self._order_repo.find(order_id)
        if not order:
            raise AppException("E10500")

        is_owned = order.user_id == user.id
        await self._authz.require(user, "update_shipping_status", target_id=order_id, is_user_owned=is_owned)

        async with self._transaction():
            db_order = await self._order_repo.find(order_id)
            if not db_order:
                raise AppException("E10500")
            db_order.address = address
            await self._order_repo.save(db_order)

        return await self._build_order_dto(db_order)

    async def delete_order(self, order_id: int) -> None:
        async with self._transaction():
            order = await self._order_repo.find(order_id)
            if not order:
                raise AppException("E10500")
            # Delete child records first to avoid FK violation
            # Xóa order_details trước để tránh lỗi FK
            details = await self._detail_repo.find_by_order_id(order_id)
            for detail in details:
                await self._detail_repo.delete(detail)
            await self._order_repo.delete(order)
