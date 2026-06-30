from __future__ import annotations

from xime.adapters.web.routing import get

from app.exception.app_exception import AppException
from app.security.current_user import require_login
from app.service.authorization_service import AuthorizationService
from app.service.search_service import SearchService


class SearchController:
    prefix = "/api/search"
    tags = ["search"]

    def __init__(
        self,
        search_service: SearchService,
        authorization_service: AuthorizationService,
    ) -> None:
        self._svc = search_service
        self._authz = authorization_service

    @get("/all")
    async def search_all(self, keywords: str = "") -> list:
        # Công khai (tìm kiếm chung; hiện trả []). Sản phẩm tìm ở /products.
        if not keywords:
            raise AppException("E10711")
        return await self._svc.search_all(keywords)

    @get("/users")
    async def search_users(self, keywords: str = "") -> list:
        # Dữ liệu người dùng - chỉ admin (quyền view_users)
        user = require_login()
        await self._authz.require(user, "view_users")
        if not keywords:
            raise AppException("E10711")
        return await self._svc.search_user(keywords)

    @get("/groups")
    async def search_groups(self, keywords: str = "") -> list:
        # Dữ liệu nhóm - chỉ admin (quyền view_groups)
        user = require_login()
        await self._authz.require(user, "view_groups")
        if not keywords:
            raise AppException("E10711")
        return await self._svc.search_group(keywords)

    @get("/products")
    async def search_products(
        self,
        keywords: str = "",
        min_price: float | None = None,
        max_price: float | None = None,
        page: int = 1,
        limit: int = 10,
    ) -> dict:
        if not keywords:
            raise AppException("E10711")
        page = max(1, page)
        limit = max(1, limit)
        return await self._svc.search_product(keywords, min_price, max_price, page, limit)

    @get("/products/category")
    async def search_products_in_category(self, keywords: str = "") -> list:
        if not keywords:
            raise AppException("E10711")
        return await self._svc.search_product_in_category(keywords)

    @get("/cart")
    async def search_products_in_cart(self, keywords: str = "") -> list:
        # Giỏ hàng của người dùng - cần đăng nhập
        require_login()
        if not keywords:
            raise AppException("E10711")
        return await self._svc.search_product_in_cart(keywords)

    @get("/orders")
    async def search_orders(self, keywords: str = "") -> list:
        # Đơn hàng của người dùng - cần đăng nhập
        require_login()
        if not keywords:
            raise AppException("E10711")
        return await self._svc.search_orders_for_users(keywords)
