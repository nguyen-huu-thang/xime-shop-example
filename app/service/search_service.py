from app.service.product_service import ProductService


class SearchService:
    def __init__(self, product_service: ProductService) -> None:
        self._product_svc = product_service

    async def search_all(self, keywords: str) -> list:
        # PHP returns [] — not implemented upstream
        # PHP trả về [] — không có logic thực
        return []

    async def search_user(self, keywords: str) -> list:
        return []

    async def search_group(self, keywords: str) -> list:
        return []

    async def search_product(
        self,
        keywords: str,
        min_price: float | None = None,
        max_price: float | None = None,
        page: int = 1,
        limit: int = 10,
    ) -> dict:
        # Port from PHP SearchService::searchProduct:
        # 1. Fetch raw products via ILIKE keyword search
        # 2. Score by name (+5) and description (+2)
        # 3. Filter by price range and score > 0
        # 4. Sort by score desc, paginate
        #
        # Port từ PHP SearchService::searchProduct:
        # 1. Lấy sản phẩm thô qua tìm kiếm ILIKE
        # 2. Chấm điểm theo tên (+5) và mô tả (+2)
        # 3. Lọc theo khoảng giá và điểm > 0
        # 4. Sắp xếp theo điểm giảm dần, phân trang
        products = await self._product_svc.search_products_by_keywords(keywords)

        ranked: list[dict] = []
        for product in products:
            score = self._calculate_relevance_score(keywords, product)
            if score > 0 and self._is_within_price_range(product.get("price"), min_price, max_price):
                ranked.append({"product": product, "relevanceScore": score})

        ranked.sort(key=lambda x: x["relevanceScore"], reverse=True)

        total = len(ranked)
        offset = (page - 1) * limit
        paged = ranked[offset: offset + limit]

        return {
            "total": total,
            "page": page,
            "limit": limit,
            "results": paged,
        }

    async def search_product_in_category(self, keywords: str) -> list:
        return []

    async def search_product_in_cart(self, keywords: str) -> list:
        return []

    async def search_orders_for_users(self, keywords: str) -> list:
        return []

    def _calculate_relevance_score(self, keywords: str, product: dict) -> int:
        score = 0
        kw = keywords.lower()
        name = (product.get("name") or "").lower()
        desc = (product.get("description") or "").lower()
        if kw in name:
            score += 5
        if kw in desc:
            score += 2
        return score

    def _is_within_price_range(
        self, price: float | None, min_price: float | None, max_price: float | None
    ) -> bool:
        if price is None:
            return True
        if min_price is not None and price < min_price:
            return False
        if max_price is not None and price > max_price:
            return False
        return True
