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
from app.repository.address_repository import AddressRepository
from app.repository.cart_repository import CartRepository
from app.repository.order_detail_repository import OrderDetailRepository
from app.repository.order_repository import OrderRepository
from app.repository.product_attribute_repository import ProductAttributeRepository
from app.repository.product_attribute_value_repository import ProductAttributeValueRepository
from app.repository.product_option_repository import ProductOptionRepository
from app.repository.product_option_value_repository import ProductOptionValueRepository
from app.repository.product_repository import ProductRepository
from app.service import pricing
from app.service.authorization_service import AuthorizationService
from app.service.coupon_service import CouponService


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
        address_repository: AddressRepository,
        coupon_service: CouponService,
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
        self._address_repo = address_repository
        self._coupon_svc = coupon_service
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

    # ── Tính tiền & xem trước (preview) ─────────────────────────────────────────

    async def _subtotal_from_cart(self, cart_items: list) -> float:
        """Tổng tiền hàng từ các cart item (giá lấy theo product_option). Trong transaction."""
        subtotal = 0.0
        for item in cart_items:
            opt = await self._option_repo.find(item.product_option_id)
            if not opt:
                raise AppException("E10502")
            subtotal += item.quantity * float(opt.price or 0)
        return subtotal

    async def _verify_address_owner(self, address_id: int, user_id: int):
        """Lấy địa chỉ thuộc về user; không thấy / không phải của user -> E10320. Trong transaction."""
        addr = await self._address_repo.find(address_id)
        if not addr or addr.user_id != user_id:
            raise AppException("E10320")
        return addr

    async def preview_order(
        self,
        user_id: int,
        cart_ids: list[int],
        address_id: int | None,
        coupon_code: str | None,
    ) -> dict:
        """Tính breakdown tiền cho FE (subtotal, ship, giảm giá, total). KHÔNG tạo đơn."""
        if not cart_ids:
            raise AppException("E10505")
        async with self._transaction():
            cart_items = await self._cart_repo.find_by_ids(cart_ids)
            if not cart_items:
                raise AppException("E10505")
            if address_id is not None:
                await self._verify_address_owner(address_id, user_id)

            subtotal = await self._subtotal_from_cart(cart_items)
            ship = pricing.shipping_fee(subtotal)
            product_discount = 0.0
            ship_discount = 0.0
            coupon_applied = False
            applied_code: str | None = None
            if coupon_code:
                app = await self._coupon_svc.resolve(
                    coupon_code, subtotal, ship, user_id
                )
                product_discount = app.product_discount
                ship_discount = app.ship_discount
                coupon_applied = True
                applied_code = app.coupon.code

            total = pricing.order_total(
                subtotal, ship, product_discount, ship_discount
            )
            return {
                "subtotal": round(subtotal, 2),
                "shipping_fee": ship,
                "product_discount": product_discount,
                "ship_discount": ship_discount,
                "total": total,
                "coupon_applied": coupon_applied,
                "coupon_code": applied_code,
            }

    async def create_order(
        self, user_id: int, data: dict
    ) -> tuple[Order, list[OrderDetail]]:
        """Create order + details + decrement stock + clear cart (atomic, một transaction).
        Tạo đơn hàng + chi tiết + giảm tồn kho + xóa giỏ trong một transaction.
        """
        cart_ids: list[int] = data.get("cart") or []
        if not cart_ids:
            raise AppException("E10505")

        address_id = data.get("address_id")
        if not address_id:
            raise AppException("E10320")

        payment_provider = data.get("payment_provider") or "cod"
        if payment_provider not in ("cod", "mock_online"):
            raise AppException("E10508")

        coupon_code = data.get("coupon_code")

        async with self._transaction():
            cart_items = await self._cart_repo.find_by_ids(cart_ids)
            if not cart_items:
                raise AppException("E10505")

            # Snapshot địa chỉ giao + tọa độ lúc đặt (đổi sổ địa chỉ sau không ảnh hưởng đơn)
            addr = await self._verify_address_owner(address_id, user_id)

            order = Order(
                user_id=user_id,
                address=addr.full_address(),
                recipient_name=addr.recipient_name,
                recipient_phone=addr.recipient_phone,
                ship_lat=addr.lat,
                ship_lng=addr.lng,
                total_amount=0,
                # payment_method giữ giá trị provider để cột cũ vẫn có dữ liệu hiển thị
                payment_method=payment_provider,
                payment_provider=payment_provider,
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

            # Phí ship + áp coupon (nối đầy đủ vào total_amount)
            # Shipping fee + coupon (fully wired into total_amount)
            ship = pricing.shipping_fee(subtotal)
            product_discount = 0.0
            ship_discount = 0.0
            coupon_app = None
            if coupon_code:
                coupon_app = await self._coupon_svc.resolve(
                    coupon_code, subtotal, ship, user_id
                )
                product_discount = coupon_app.product_discount
                ship_discount = coupon_app.ship_discount
                order.coupon_id = coupon_app.coupon.id

            order.shipping_fee = ship
            order.product_discount = product_discount
            order.ship_discount = ship_discount
            order.total_amount = pricing.order_total(
                subtotal, ship, product_discount, ship_discount
            )
            await self._order_repo.save(order)

            # Tăng lượt dùng coupon trong cùng transaction (atomic với việc tạo đơn)
            if coupon_app is not None:
                await self._coupon_svc.increment_usage(coupon_app.coupon)

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

    # ── Thanh toán giả lập (mock online gateway) ────────────────────────────────

    async def start_payment(self, order_id: int, user_id: int) -> tuple[Order, str]:
        """Bắt đầu thanh toán cổng online giả lập: sinh payment_ref cho đơn của user.
        Lỗi: E10500 không thấy đơn, E2021 không phải chủ, E10507 đã thanh toán,
        E10508 đơn không dùng cổng online (vd COD).
        """
        import uuid

        async with self._transaction():
            order = await self._order_repo.find(order_id)
            if not order:
                raise AppException("E10500")
            if order.user_id != user_id:
                raise AppException("E2021")
            if order.payment_status:
                raise AppException("E10507")
            if order.payment_provider != "mock_online":
                raise AppException("E10508")
            ref = uuid.uuid4().hex
            order.payment_ref = ref
            await self._order_repo.save(order)
            return order, ref

    async def confirm_mock_payment(self, payment_ref: str, success: bool) -> Order:
        """Callback giả lập: khớp payment_ref đang chờ -> set đã thanh toán nếu success.
        Lỗi E10509 nếu ref không khớp hoặc đơn đã xử lý (đã thanh toán).
        """
        from datetime import datetime, timezone

        async with self._transaction():
            order = await self._order_repo.find_by_payment_ref(payment_ref)
            if not order or order.payment_status:
                raise AppException("E10509")
            if success:
                order.payment_status = True
                order.paid_at = datetime.now(timezone.utc)
                order.shipping_status = "Đã thanh toán, chờ giao"
            await self._order_repo.save(order)
            return order

    # ── Cập nhật trạng thái giao hàng (admin) ───────────────────────────────────

    async def update_shipping_status(
        self, order_id: int, user, status: str
    ) -> Order:
        """Admin cập nhật trạng thái giao hàng. Cần quyền update_shipping_status."""
        # authz mở transaction riêng -> gọi trước, ngoài transaction cập nhật
        await self._authz.require(user, "update_shipping_status", target_id=order_id)
        async with self._transaction():
            order = await self._order_repo.find(order_id)
            if not order:
                raise AppException("E10500")
            order.shipping_status = status
            await self._order_repo.save(order)
            return order
