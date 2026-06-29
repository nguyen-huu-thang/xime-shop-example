from __future__ import annotations

from xime.adapters.web.routing import delete, get, post, put

from app.dto.request.order_request import OrderCreateRequest, OrderUpdateRequest
from app.dto.response.order_response import OrderResponse
from app.dto.response.token_response import CountResponse, MessageResponse
from app.security.current_user import require_login
from app.service.authorization_service import AuthorizationService
from app.service.order_service import OrderService


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

    @post("", status_code=201)
    async def create(self, body: OrderCreateRequest) -> OrderResponse:
        user = require_login()
        data = body.model_dump(by_alias=False)
        order, details = await self._svc.create_order(user.id, data)
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
