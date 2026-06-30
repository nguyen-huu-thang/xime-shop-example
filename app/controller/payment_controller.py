from __future__ import annotations

from xime.adapters.web.routing import post

from app.dto.request.order_request import MockPaymentCallbackRequest
from app.dto.response.order_response import OrderResponse
from app.service.email_service import EmailService
from app.service.notification_service import NotificationService
from app.service.order_service import OrderService
from app.service.user_service import UserService


class PaymentController:
    """Cổng thanh toán giả lập (demo). Không tích hợp cổng thật; chỉ khớp payment_ref
    đang chờ rồi đánh dấu đã thanh toán. Xem .claude/docs/thiet-ke-checkout.md.
    """

    prefix = "/api/payments"
    tags = ["payments"]

    def __init__(
        self,
        order_service: OrderService,
        notification_service: NotificationService,
        email_service: EmailService,
        user_service: UserService,
    ) -> None:
        self._svc = order_service
        self._notification = notification_service
        self._email = email_service
        self._user_svc = user_service

    @post("/mock/callback")
    async def mock_callback(self, body: MockPaymentCallbackRequest) -> OrderResponse:
        # Callback giả lập từ trang thanh toán mock; không cần auth nhưng phải khớp
        # payment_ref đang chờ (uuid) để tránh set bừa.
        order = await self._svc.confirm_mock_payment(body.payment_ref, body.success)
        if order.payment_status:
            await self._notification.notify(
                order.user_id,
                "Thanh toán thành công",
                f"Đơn #{order.id} đã được thanh toán.",
                link=f"/orders/{order.id}",
            )
            # Email báo thanh toán thành công (gửi NỀN, fault-tolerant)
            user = await self._user_svc.get_user_by_id(order.user_id)
            if user:
                await self._email.send_payment_success(user.email, order.id)
        _, details = await self._svc.get_order_by_id(order.id)
        return OrderResponse.from_entities(order, details)
