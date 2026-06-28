from __future__ import annotations

from typing import Any

from xime.adapters.web.routing import delete, get, post, put

from app.dto.request.product_request import (
    ProductAttributeUpdateRequest,
    ProductCreateRequest,
    ProductUpdateRequest,
)
from app.dto.response.token_response import CountResponse, MessageResponse
from app.exception.app_exception import AppException
from app.security.current_user import require_login
from app.service.authorization_service import AuthorizationService
from app.service.product_service import ProductService


class ProductController:
    prefix = "/api/products"
    tags = ["products"]

    def __init__(
        self,
        product_service: ProductService,
        authorization_service: AuthorizationService,
    ) -> None:
        self._svc = product_service
        self._authz = authorization_service

    @get("")
    async def list(self, page: int = 1, limit: int = 10) -> list[dict]:
        return await self._svc.get_paginated_product_dtos(page, limit)

    @get("/count")
    async def count(self) -> CountResponse:
        # Total products for FE pagination (public, mirrors the public list).
        # Tổng sản phẩm cho phân trang FE (công khai, khớp với list công khai).
        return CountResponse(total=await self._svc.count_products())

    @get("/by-category/{category_id}")
    async def by_category(self, category_id: int) -> list[dict]:
        products = await self._svc.get_products_by_category_id(category_id)
        if not products:
            raise AppException("E10200")
        return products

    @get("/options/{option_id}")
    async def get_option_values(self, option_id: int) -> dict:
        values = await self._svc.get_values_by_option_id(option_id)
        if not values:
            raise AppException("E10502")
        return values

    @get("/{id}")
    async def detail(self, id: int) -> dict:
        return await self._svc.get_product_dto_by_id(id)

    @get("/{id}/option-default")
    async def get_option_default(self, id: int) -> dict:
        product = await self._svc.get_product_by_id(id)
        return await self._svc.get_option_default(product)

    @post("", status_code=201)
    async def create(self, body: ProductCreateRequest) -> dict:
        user = require_login()
        await self._authz.require(user, "create_product")
        data = body.model_dump(by_alias=True)
        return await self._svc.create_product(data)

    @put("/{id}")
    async def update(self, id: int, body: ProductUpdateRequest) -> dict:
        user = require_login()
        await self._authz.require(user, "edit_product", target_id=id)
        data = body.model_dump(by_alias=True, exclude_unset=True)
        return await self._svc.update_product(id, data)

    @delete("/{id}")
    async def remove(self, id: int) -> MessageResponse:
        user = require_login()
        await self._authz.require(user, "delete_product")
        await self._svc.delete_product(id)
        return MessageResponse(message="Product deleted")

    @post("/{id}/attribute")
    async def update_attributes(self, id: int, body: ProductAttributeUpdateRequest) -> MessageResponse:
        user = require_login()
        await self._authz.require(user, "edit_product", target_id=id)
        data = body.model_dump()
        await self._svc.update_or_create_product_attributes_and_options(id, data)
        return MessageResponse(message="Attributes and options updated successfully")

    @post("/{id}/find-option")
    async def find_option(self, id: int, body: dict) -> dict:
        product = await self._svc.get_product_by_id(id)
        opt = await self._svc.find_product_option_by_json(product, body)
        return {"id": opt.id, "price": opt.price, "stock": opt.stock}
