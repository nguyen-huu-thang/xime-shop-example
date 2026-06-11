from __future__ import annotations

from xime.adapters.web.routing import delete, get, post, put

from app.dto.request.order_request import OrderCreateRequest, OrderUpdateRequest
from app.dto.response.token_response import MessageResponse
from app.exception.app_exception import AppException
from app.security.current_user import require_login
from app.service.authorization_service import AuthorizationService
from app.service.order_service import OrderService


def _order_to_dict(order_tuple: list) -> dict:
    """Convert [Order, [[id,name,price,qty,url], ...]] to response dict.
    Chuyển tuple [Order, details] sang dict phản hồi.
    """
    order, details = order_tuple[0], order_tuple[1]
    return {
        "id": order.id,
        "userId": order.user_id,
        "address": order.address,
        "totalAmount": float(order.total_amount),
        "paymentMethod": order.payment_method,
        "shippingStatus": order.shipping_status,
        "paymentStatus": order.payment_status,
        "details": [
            {"id": d[0], "name": d[1], "price": d[2], "quantity": d[3], "url": d[4]}
            for d in details
        ],
    }


class OrderController:
    prefix = "/api/orders"
    tags = ["orders"]

    def __init__(
        self,
        order_service: OrderService,
        authorization_service: AuthorizationService,
    ) -> None:
        self._svc = order_service
        self._authz = authorization_service

    @get("/all")
    async def list(self, page: int = 1, limit: int = 10) -> list[dict]:
        user = require_login()
        await self._authz.require(user, "view_orders")
        orders = await self._svc.get_paginated_orders(page, limit)
        return [_order_to_dict(o) for o in orders]

    @get("")
    async def user_orders(self) -> list[dict]:
        user = require_login()
        orders = await self._svc.find_orders_by_user(user.id)
        return [_order_to_dict(o) for o in orders]

    @get("/{id}")
    async def detail(self, id: int) -> dict:
        order_tuple = await self._svc.get_order_by_id(id)
        return _order_to_dict(order_tuple)

    @post("", status_code=201)
    async def create(self, body: OrderCreateRequest) -> dict:
        user = require_login()
        data = body.model_dump(by_alias=False)
        order_tuple = await self._svc.create_order(user.id, data)
        return _order_to_dict(order_tuple)

    @put("/{id}")
    async def update(self, id: int, body: OrderUpdateRequest) -> dict:
        user = require_login()
        order_tuple = await self._svc.update_order(id, user, body.address)
        return _order_to_dict(order_tuple)

    @delete("/{id}")
    async def remove(self, id: int) -> MessageResponse:
        user = require_login()
        await self._authz.require(user, "delete_order", target_id=id)
        await self._svc.delete_order(id)
        return MessageResponse(message="Order deleted")
