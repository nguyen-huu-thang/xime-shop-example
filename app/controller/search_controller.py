from __future__ import annotations

from xime.adapters.web.routing import get

from app.exception.app_exception import AppException
from app.service.search_service import SearchService


class SearchController:
    prefix = "/api/search"
    tags = ["search"]

    def __init__(self, search_service: SearchService) -> None:
        self._svc = search_service

    @get("/all")
    async def search_all(self, keywords: str = "") -> list:
        if not keywords:
            raise AppException("E10711")
        return await self._svc.search_all(keywords)

    @get("/users")
    async def search_users(self, keywords: str = "") -> list:
        if not keywords:
            raise AppException("E10711")
        return await self._svc.search_user(keywords)

    @get("/groups")
    async def search_groups(self, keywords: str = "") -> list:
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
        if not keywords:
            raise AppException("E10711")
        return await self._svc.search_product_in_cart(keywords)

    @get("/orders")
    async def search_orders(self, keywords: str = "") -> list:
        if not keywords:
            raise AppException("E10711")
        return await self._svc.search_orders_for_users(keywords)
