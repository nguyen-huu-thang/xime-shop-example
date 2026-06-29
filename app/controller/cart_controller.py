from __future__ import annotations

from xime.adapters.web.routing import delete, get, post, put

from app.dto.request.cart_request import CartCreateRequest, CartUpdateRequest
from app.dto.response.token_response import CountResponse, MessageResponse
from app.exception.app_exception import AppException
from app.security.current_user import require_login
from app.service.authorization_service import AuthorizationService
from app.service.cart_service import CartService
from app.service.product_service import ProductService


class CartController:
    prefix = "/api/cart"
    tags = ["cart"]

    def __init__(
        self,
        cart_service: CartService,
        product_service: ProductService,
        authorization_service: AuthorizationService,
    ) -> None:
        self._svc = cart_service
        self._product_svc = product_service
        self._authz = authorization_service

    async def _item_to_dict(self, item) -> dict:
        # Enrich each line with product name + unit price so the cart page can show
        # name/price/line-total and compute a client-side subtotal.
        # Làm giàu mỗi dòng với tên sản phẩm + đơn giá để trang giỏ hiển thị
        # tên/giá/thành tiền và tính tạm tính phía client.
        detail = await self._product_svc.get_cart_item_detail(item.product_option_id)
        price = detail["price"]
        return {
            "id": item.id,
            "userId": item.user_id,
            "productId": detail["productId"],
            "productName": detail["productName"],
            "productOptionId": item.product_option_id,
            "price": price,
            "quantity": item.quantity,
            "subtotal": (price or 0) * item.quantity,
            "optionValues": detail["optionValues"],
        }

    @get("/all")
    async def list(self, page: int = 1, limit: int = 10) -> list[dict]:
        user = require_login()
        await self._authz.require(user, "view_carts")
        items = await self._svc.get_paginated_cart_items(page, limit)
        return [await self._item_to_dict(i) for i in items]

    @get("/count")
    async def count(self) -> CountResponse:
        # Total cart items for FE pagination (admin list, needs view_carts).
        # Tổng số item giỏ cho phân trang FE (trang admin, cần quyền view_carts).
        user = require_login()
        await self._authz.require(user, "view_carts")
        return CountResponse(total=await self._svc.count_cart_items())

    @get("")
    async def user_cart(self) -> list[dict]:
        user = require_login()
        items = await self._svc.get_user_cart(user.id)
        return [await self._item_to_dict(i) for i in items]

    @get("/{id}")
    async def detail(self, id: int) -> dict:
        user = require_login()
        item = await self._svc.get_cart_item_by_id(id)
        if not item:
            raise AppException("E10601")
        # Chủ sở hữu hoặc người có quyền view_carts mới được xem
        # Owner or holder of view_carts may view
        await self._authz.require_owner_or_permission(user, "view_carts", item, target_id=id)
        return await self._item_to_dict(item)

    @post("", status_code=201)
    async def create(self, body: CartCreateRequest) -> dict:
        user = require_login()
        await self._authz.require(user, "create_cart")
        data = body.model_dump(by_alias=False)
        item = await self._svc.create_cart_item(user.id, data)
        return await self._item_to_dict(item)

    @put("/{id}")
    async def update(self, id: int, body: CartUpdateRequest) -> dict:
        user = require_login()
        item = await self._svc.update_cart_item(id, user, body.quantity)
        return await self._item_to_dict(item)

    @delete("/{id}")
    async def remove(self, id: int) -> MessageResponse:
        user = require_login()
        await self._svc.delete_cart_item(id, user)
        return MessageResponse(message="Cart item deleted")
