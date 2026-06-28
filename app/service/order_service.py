"""
OrderService - quản lý đơn hàng.
Port từ OrderService.php.

create_order dùng MỘT transaction để đảm bảo atomicity:
  order + order_details + giảm tồn kho + xóa cart items.

Các method đọc gom truy vấn trong một transaction và batch-load order_details để tránh N+1.
Mọi method trả về tuple `(Order, list[OrderDetail])` (hoặc list các tuple); controller map sang
OrderResponse DTO.
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
from app.repository.product_repository import ProductRepository
from app.service.authorization_service import AuthorizationService


class OrderService:
    def __init__(
        self,
        transaction: TransactionManager,
        order_repository: OrderRepository,
        order_detail_repository: OrderDetailRepository,
        cart_repository: CartRepository,
        product_repository: ProductRepository,
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
        self._product_repo = product_repository
        self._option_repo = product_option_repository
        self._option_val_repo = product_option_value_repository
        self._attr_val_repo = product_attribute_value_repository
        self._attr_repo = product_attribute_repository
        self._authz = authorization_service

    # ── Read helpers ───────────────────────────────────────────────────────────

    async def _attach_details(
        self, orders: list[Order]
    ) -> list[tuple[Order, list[OrderDetail]]]:
        """Batch-load order_details cho danh sách order (một truy vấn, tránh N+1).
        Phải được gọi BÊN TRONG một transaction đang mở.
        """
        if not orders:
            return []
        order_ids = [o.id for o in orders]
        details = await self._detail_repo.find_by_order_ids(order_ids)
        by_order: dict[int, list[OrderDetail]] = {}
        for d in details:
            by_order.setdefault(d.order_id, []).append(d)
        return [(o, by_order.get(o.id, [])) for o in orders]

    async def get_all_orders(self) -> list[tuple[Order, list[OrderDetail]]]:
        async with self._transaction():
            orders = await self._order_repo.find_all()
            return await self._attach_details(orders)

    async def count_orders(self) -> int:
        # Total orders (for FE pagination).
        # Tổng số đơn hàng (phục vụ phân trang FE).
        async with self._transaction():
            return await self._order_repo.count()

    async def get_paginated_orders(
        self, page: int, limit: int
    ) -> list[tuple[Order, list[OrderDetail]]]:
        async with self._transaction():
            orders = await self._order_repo.find_all_paginated(page, limit)
            return await self._attach_details(orders)

    async def find_orders_by_user(
        self, user_id: int
    ) -> list[tuple[Order, list[OrderDetail]]]:
        async with self._transaction():
            orders = await self._order_repo.find_by_user_id(user_id)
            return await self._attach_details(orders)

    async def find_order_by_id(self, order_id: int) -> Order | None:
        async with self._transaction():
            return await self._order_repo.find(order_id)

    async def get_order_by_id(self, order_id: int) -> tuple[Order, list[OrderDetail]]:
        async with self._transaction():
            order = await self._order_repo.find(order_id)
            if not order:
                raise AppException("E10500")
            details = await self._detail_repo.find_by_order_id(order_id)
            return order, details

    # ── Order creation ─────────────────────────────────────────────────────────

    async def _build_option_attributes(self, option_id: int) -> str:
        """Build JSON attribute snapshot for OrderDetail (mirrors getValuesByOption).
        Build JSON snapshot thuộc tính cho OrderDetail. Chạy trong transaction đang mở.
        """
        opt_vals = await self._option_val_repo.find_by_option_id(option_id)
        result: dict[str, str] = {}
        for ov in opt_vals:
            pav = await self._attr_val_repo.find(ov.attribute_value_id)
            if not pav:
                continue
            attr = await self._attr_repo.find(pav.attribute_id)
            if attr:
                result[attr.name] = pav.value
        return json.dumps(result)

    async def create_order(
        self, user_id: int, data: dict
    ) -> tuple[Order, list[OrderDetail]]:
        """Create order + details + decrement stock + clear cart (atomic, một transaction).
        Tạo đơn hàng + chi tiết + giảm tồn kho + xóa giỏ trong một transaction.
        """
        cart_ids: list[int] = data.get("cart") or []
        if not cart_ids:
            raise AppException("E10505")

        async with self._transaction():
            cart_items = await self._cart_repo.find_by_ids(cart_ids)
            if not cart_items:
                raise AppException("E10505")

            order = Order(
                user_id=user_id,
                address=data.get("address", ""),
                total_amount=0,
                payment_method=data.get("paymentMethod") or data.get("payment_method", ""),
                shipping_status="Đơn hàng đã được tạo",
                payment_status=False,
            )
            order = await self._order_repo.save(order)

            details: list[OrderDetail] = []
            subtotal = 0.0
            for item in cart_items:
                opt = await self._option_repo.find(item.product_option_id)
                if not opt:
                    raise AppException("E10502")
                if opt.stock < item.quantity:
                    raise AppException("E10506")  # exceeds stock / vượt tồn kho

                product = await self._product_repo.find(opt.product_id)
                if not product:
                    raise AppException("E10200")

                # Snapshot attributes before mutating stock
                # Snapshot thuộc tính trước khi giảm tồn kho
                attribute = await self._build_option_attributes(opt.id)

                opt.stock -= item.quantity
                await self._option_repo.save(opt)

                price = float(opt.price or 0)
                detail = OrderDetail(
                    order_id=order.id,
                    product_id=product.id,
                    name=product.name,
                    quantity=item.quantity,
                    price=price,
                    attribute=attribute,
                    url=None,
                )
                detail = await self._detail_repo.save(detail)
                details.append(detail)
                subtotal += item.quantity * price

                # Remove cart item
                # Xóa cart item
                await self._cart_repo.delete(item)

            order.total_amount = subtotal
            await self._order_repo.save(order)

            return order, details

    async def update_order(
        self, order_id: int, user, address: str
    ) -> tuple[Order, list[OrderDetail]]:
        """Update order address; check permission (owner or update_shipping_status perm).
        Cập nhật địa chỉ đơn hàng; kiểm tra quyền.
        """
        async with self._transaction():
            order = await self._order_repo.find(order_id)
            if not order:
                raise AppException("E10500")
            is_owned = order.user_id == user.id

        # authz mở transaction riêng -> gọi ngoài transaction trên để không lồng
        # authz opens its own transaction -> call outside the block above
        await self._authz.require(
            user, "update_shipping_status", target_id=order_id, is_user_owned=is_owned
        )

        async with self._transaction():
            db_order = await self._order_repo.find(order_id)
            if not db_order:
                raise AppException("E10500")
            db_order.address = address
            await self._order_repo.save(db_order)
            details = await self._detail_repo.find_by_order_id(order_id)
            return db_order, details

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
