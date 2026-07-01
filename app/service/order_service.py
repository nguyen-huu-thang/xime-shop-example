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
from app.money import money, quantize
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
from app.service.product_service import ProductService


class OrderService:
    # Hạn thanh toán cho đơn online (mock), tính bằng giây. Quá hạn -> hoàn kho + hủy đơn.
    # Payment window for online (mock) orders, in seconds. Overdue -> restock + cancel.
    _online_payment_ttl = 24 * 3600  # 1 ngày / 1 day

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
        product_service: ProductService,
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
        self._product_svc = product_service

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

    async def _subtotal_from_cart(self, cart_items: list):
        """Tổng tiền hàng từ các cart item (giá lấy theo product_option). Trong transaction.
        Trả Decimal (tránh sai số float khi cộng dồn)."""
        subtotal = money(0)
        for item in cart_items:
            opt = await self._option_repo.find(item.product_option_id)
            if not opt:
                raise AppException("E10502")
            # Áp % giảm giá của sản phẩm vào đơn giá trước khi cộng dồn.
            # Apply the product percent discount to the unit price before summing.
            product = await self._product_repo.find(opt.product_id)
            discount = product.discount_percentage if product else 0
            unit_price = pricing.apply_percent_discount(opt.price, discount)
            subtotal += unit_price * item.quantity
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
            product_discount = money(0)
            ship_discount = money(0)
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
                "subtotal": quantize(subtotal),
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
        # Giữ chỗ tồn kho kiểu Shopee: MỌI đơn (COD lẫn online) trừ kho + tăng lượt coupon NGAY
        # lúc đặt. Đơn online có hạn thanh toán (payment_deadline); quá hạn chưa trả -> job hoàn
        # kho + hủy đơn. Tránh cảnh khách săn mã/hàng hiếm mà kho chỉ trừ khi thanh toán.
        # Reserve-on-order (Shopee-like): every order decrements stock + bumps coupon at creation;
        # online orders carry a payment deadline and get restocked+cancelled if overdue.
        is_online = payment_provider == "mock_online"

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
            affected_product_ids: set[int] = set()
            subtotal = money(0)
            for item in cart_items:
                # Khóa dòng option (SELECT FOR UPDATE) chống bán vượt tồn kho khi nhiều đơn
                # cùng trừ kho. Trừ kho NGAY cho mọi đơn (giữ chỗ).
                # Lock the option row to prevent overselling; decrement stock now for every order.
                opt = await self._option_repo.find_for_update(item.product_option_id)
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
                affected_product_ids.add(product.id)

                # Đơn giá đã trừ % giảm giá sản phẩm (giá thực tính tiền, lưu vào chi tiết đơn).
                # Unit price after the product percent discount (the charged price).
                price = pricing.apply_percent_discount(opt.price, product.discount_percentage)
                detail = OrderDetail(
                    order_id=order.id,
                    product_id=product.id,
                    product_option_id=opt.id,
                    name=product.name,
                    quantity=item.quantity,
                    price=price,
                    attribute=attribute,
                    url=None,
                )
                detail = await self._detail_repo.save(detail)
                details.append(detail)
                subtotal += price * item.quantity

                # Remove cart item
                # Xóa cart item
                await self._cart_repo.delete(item)

            # Phí ship + áp coupon (nối đầy đủ vào total_amount)
            # Shipping fee + coupon (fully wired into total_amount)
            ship = pricing.shipping_fee(subtotal)
            product_discount = money(0)
            ship_discount = money(0)
            coupon_app = None
            if coupon_code:
                # Khóa dòng coupon (tăng used_count an toàn dưới truy cập đồng thời - săn mã).
                # Lock the coupon row so used_count bumps atomically under contention.
                coupon_app = await self._coupon_svc.resolve(
                    coupon_code, subtotal, ship, user_id, for_update=True
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
            # Đơn online: đặt hạn thanh toán (1 ngày). Quá hạn -> job hoàn kho + hủy đơn.
            # Online order: set a 1-day payment deadline; overdue -> job restocks + cancels.
            if is_online:
                from datetime import datetime, timedelta, timezone

                order.payment_deadline = datetime.now(timezone.utc) + timedelta(
                    seconds=self._online_payment_ttl
                )
            await self._order_repo.save(order)

            # Tăng lượt dùng coupon ngay khi đặt (atomic với việc trừ kho tạo đơn). Nếu đơn
            # online quá hạn bị hủy, job sẽ nhả lại lượt dùng (decrement_usage).
            # Bump coupon usage at order time; overdue online orders release it on cancel.
            if coupon_app is not None:
                await self._coupon_svc.increment_usage(coupon_app.coupon)

            # Tồn kho vừa đổi -> xóa cache DTO sản phẩm để /products không hiển thị tồn kho cũ.
            # Stock changed -> drop product DTO cache so listings don't show stale stock.
            for pid in affected_product_ids:
                await self._product_svc.invalidate_cache(pid)

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
            if order.cancelled_at is not None:
                raise AppException("E10509")  # đơn đã hủy (quá hạn thanh toán)
            if order.payment_provider != "mock_online":
                raise AppException("E10508")
            ref = uuid.uuid4().hex
            order.payment_ref = ref
            await self._order_repo.save(order)
            return order, ref

    async def confirm_mock_payment(self, payment_ref: str, success: bool) -> Order:
        """Callback giả lập: khớp payment_ref đang chờ -> set đã thanh toán nếu success.

        Kho đã được trừ lúc đặt (giữ chỗ), nên ở đây chỉ đánh dấu đã thanh toán. Đơn đã bị hủy
        do quá hạn (cancelled_at đã set, kho đã hoàn) thì KHÔNG cho thanh toán nữa (E10509).

        Lỗi E10509 nếu ref không khớp / đơn đã thanh toán / đơn đã hủy quá hạn.
        """
        from datetime import datetime, timezone

        async with self._transaction():
            order = await self._order_repo.find_by_payment_ref(payment_ref)
            if not order or order.payment_status or order.cancelled_at is not None:
                raise AppException("E10509")
            if success:
                order.payment_status = True
                order.paid_at = datetime.now(timezone.utc)
                order.payment_deadline = None  # đã trả, bỏ hạn
                order.shipping_status = "Đã thanh toán, chờ giao"
            await self._order_repo.save(order)
            return order

    async def expire_overdue_online_orders(self, cutoff: datetime | None = None) -> int:
        """Hủy các đơn online quá hạn thanh toán và HOÀN KHO lại (giữ chỗ đã hết hạn).

        Với mỗi đơn quá hạn: cộng lại tồn kho từng dòng (khóa dòng option), nhả lại lượt dùng
        coupon (decrement_usage), đánh dấu cancelled_at + trạng thái hủy. Trả về số đơn đã hủy.
        Gọi bởi ExpireOrdersJob theo lịch; test có thể truyền cutoff (mốc thời gian) để mô phỏng.

        Cancel overdue unpaid online orders and restore their reserved stock + coupon usage.
        """
        from datetime import datetime as _dt
        from datetime import timezone as _tz

        now = _dt.now(_tz.utc)
        cutoff = cutoff or now
        affected_product_ids: set[int] = set()
        async with self._transaction():
            orders = await self._order_repo.find_overdue_unpaid_online(cutoff)
            cancelled = 0
            for order in orders:
                details = await self._detail_repo.find_by_order_id(order.id)
                for d in details:
                    if d.product_option_id is None:
                        continue  # đơn cũ trước khi có cột option_id
                    opt = await self._option_repo.find_for_update(d.product_option_id)
                    if opt is not None:
                        opt.stock += d.quantity  # hoàn lại phần đã giữ chỗ
                        await self._option_repo.save(opt)
                        affected_product_ids.add(opt.product_id)
                # Nhả lại lượt dùng coupon (nếu đơn có áp mã)
                # Release the coupon usage slot (if the order used one)
                if order.coupon_id is not None:
                    coupon = await self._coupon_svc.get_coupon_for_update(order.coupon_id)
                    if coupon is not None:
                        await self._coupon_svc.decrement_usage(coupon)
                order.cancelled_at = now
                order.shipping_status = "Đã hủy: quá hạn thanh toán"
                await self._order_repo.save(order)
                cancelled += 1

            # Tồn kho được hoàn -> xóa cache DTO sản phẩm bị ảnh hưởng.
            # Stock restored -> drop affected product DTO caches.
            for pid in affected_product_ids:
                await self._product_svc.invalidate_cache(pid)
            return cancelled

    async def cancel_order(self, order_id: int, user_id: int) -> Order:
        """Chủ đơn CHỦ ĐỘNG hủy đơn online chưa thanh toán -> hoàn kho + nhả coupon (như quá hạn).

        Lỗi: E10500 không thấy đơn, E2021 không phải chủ, E10507 đã thanh toán,
        E10508 không phải đơn online (COD không cần hủy kiểu này), E10509 đơn đã hủy.

        Owner cancels their own unpaid online order -> restock + release coupon (same as expiry).
        """
        from datetime import datetime, timezone

        affected_product_ids: set[int] = set()
        async with self._transaction():
            order = await self._order_repo.find(order_id)
            if not order:
                raise AppException("E10500")
            if order.user_id != user_id:
                raise AppException("E2021")
            if order.payment_status:
                raise AppException("E10507")  # đã thanh toán, không tự hủy
            if order.cancelled_at is not None:
                raise AppException("E10509")  # đã hủy rồi
            if order.payment_provider != "mock_online":
                raise AppException("E10508")  # chỉ đơn online chờ thanh toán mới tự hủy

            # Hoàn lại tồn kho đã giữ chỗ (khóa dòng option chống race với đơn khác).
            # Restore reserved stock (lock option rows to avoid races).
            details = await self._detail_repo.find_by_order_id(order.id)
            for d in details:
                if d.product_option_id is None:
                    continue
                opt = await self._option_repo.find_for_update(d.product_option_id)
                if opt is not None:
                    opt.stock += d.quantity
                    await self._option_repo.save(opt)
                    affected_product_ids.add(opt.product_id)
            # Nhả lại lượt dùng coupon (nếu có)
            # Release coupon usage (if any)
            if order.coupon_id is not None:
                coupon = await self._coupon_svc.get_coupon_for_update(order.coupon_id)
                if coupon is not None:
                    await self._coupon_svc.decrement_usage(coupon)
            order.cancelled_at = datetime.now(timezone.utc)
            order.payment_deadline = None
            order.shipping_status = "Đã hủy: người mua hủy đơn"
            await self._order_repo.save(order)

            for pid in affected_product_ids:
                await self._product_svc.invalidate_cache(pid)
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
