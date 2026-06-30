from __future__ import annotations

from xime.adapters.web.routing import delete, get, post, put

from app.dto.request.order_request import (
    OrderCreateRequest,
    OrderPreviewRequest,
    OrderUpdateRequest,
    ShippingStatusUpdateRequest,
)
from app.dto.response.order_response import (
    OrderPreviewResponse,
    OrderResponse,
    PaymentInitResponse,
)
from app.dto.response.token_response import CountResponse, MessageResponse
from app.security.current_user import require_login
from app.service.authorization_service import AuthorizationService
from app.service.email_service import EmailService
from app.service.interaction_service import InteractionService
from app.service.notification_service import NotificationService
from app.service.order_service import OrderService


class OrderController:
    prefix = "/api/orders"
    tags = ["orders"]

    def __init__(
        self,
        order_service: OrderService,
        authorization_service: AuthorizationService,
        interaction_service: InteractionService,
        notification_service: NotificationService,
        email_service: EmailService,
    ) -> None:
        self._svc = order_service
        self._authz = authorization_service
        self._interaction = interaction_service
        self._notification = notification_service
        self._email = email_service

    @get("/all")
    async def list(self, page: int = 1, limit: int = 10) -> list[OrderResponse]:
        user = require_login()
        await self._authz.require(user, "view_orders")
        orders = await self._svc.get_paginated_orders(page, limit)
        return [OrderResponse.from_entities(o, d) for o, d in orders]

    @get("/count")
    async def count(self) -> CountResponse:
        # Total orders for FE pagination (admin list, needs view_orders).
        # Tổng số đơn cho phân trang FE (trang admin, cần quyền view_orders).
        user = require_login()
        await self._authz.require(user, "view_orders")
        return CountResponse(total=await self._svc.count_orders())

    @get("")
    async def user_orders(self) -> list[OrderResponse]:
        user = require_login()
        orders = await self._svc.find_orders_by_user(user.id)
        return [OrderResponse.from_entities(o, d) for o, d in orders]

    @get("/{id}")
    async def detail(self, id: int) -> OrderResponse:
        user = require_login()
        order, details = await self._svc.get_order_by_id(id)
        # Vá IDOR: chủ đơn hoặc người có quyền xem chi tiết đơn mới được xem
        # Fix IDOR: only the order owner or a holder of view_order_details may view
        await self._authz.require_owner_or_permission(
            user, "view_order_details", order, target_id=id
        )
        return OrderResponse.from_entities(order, details)

    @post("/preview")
    async def preview(self, body: OrderPreviewRequest) -> OrderPreviewResponse:
        # Xem trước tổng tiền (subtotal + ship - giảm giá) trước khi đặt; không tạo đơn.
        user = require_login()
        result = await self._svc.preview_order(
            user.id, body.cart, body.address_id, body.coupon_code
        )
        return OrderPreviewResponse.from_dict(result)

    @post("", status_code=201)
    async def create(self, body: OrderCreateRequest) -> OrderResponse:
        user = require_login()
        data = body.model_dump(by_alias=False)
        order, details = await self._svc.create_order(user.id, data)
        # Ghi tín hiệu "purchase" (mạnh nhất) cho từng sản phẩm trong đơn, khử trùng (fault-tolerant)
        # Record the strongest "purchase" signal per distinct product in the order
        for product_id in {d.product_id for d in details}:
            await self._interaction.record(user.id, product_id, "purchase")
        # Thông báo in-app: đặt hàng thành công (fault-tolerant, không làm hỏng đơn)
        await self._notification.notify(
            user.id,
            "Đặt hàng thành công",
            f"Đơn #{order.id} đã được tạo.",
            link=f"/orders/{order.id}",
        )
        # Email xác nhận đơn (gửi NỀN, fault-tolerant; tự bỏ qua nếu chưa cấu hình SMTP)
        await self._email.send_order_confirmation(
            user.email, order.id, float(order.total_amount)
        )
        return OrderResponse.from_entities(order, details)

    @post("/{id}/pay")
    async def pay(self, id: int) -> PaymentInitResponse:
        # Bắt đầu thanh toán cổng online giả lập; trả mã giao dịch + URL trang mock.
        user = require_login()
        order, ref = await self._svc.start_payment(id, user.id)
        return PaymentInitResponse(
            orderId=order.id, paymentRef=ref, mockUrl=f"/payment/mock?ref={ref}"
        )

    @put("/{id}/shipping-status")
    async def update_shipping(
        self, id: int, body: ShippingStatusUpdateRequest
    ) -> OrderResponse:
        # Admin cập nhật trạng thái giao hàng -> thông báo cho chủ đơn.
        user = require_login()
        order = await self._svc.update_shipping_status(id, user, body.status)
        # Thông báo in-app + email cho chủ đơn (Phase B: also_email - notify tự tra email)
        await self._notification.notify(
            order.user_id,
            "Cập nhật đơn hàng",
            f"Đơn #{order.id}: {body.status}",
            link=f"/orders/{order.id}",
            also_email=True,
        )
        _, details = await self._svc.get_order_by_id(order.id)
        return OrderResponse.from_entities(order, details)

    @put("/{id}")
    async def update(self, id: int, body: OrderUpdateRequest) -> OrderResponse:
        user = require_login()
        order, details = await self._svc.update_order(id, user, body.address)
        return OrderResponse.from_entities(order, details)

    @delete("/{id}")
    async def remove(self, id: int) -> MessageResponse:
        user = require_login()
        await self._authz.require(user, "delete_order", target_id=id)
        await self._svc.delete_order(id)
        return MessageResponse(message="Order deleted")
