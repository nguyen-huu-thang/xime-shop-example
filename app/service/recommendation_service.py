"""
RecommendationService - facade đọc cho cá nhân hóa (không AI, theo luật + chấm điểm).

Ba tính năng:
  - recently_viewed: sản phẩm user xem gần đây (từ interactions, khử trùng).
  - trending: sản phẩm thịnh hành toàn site (tổng trọng số điểm trong cửa sổ gần đây), cache RAM TTL ngắn.
  - for_you: gợi ý theo affinity category của user, loại sản phẩm đã mua; cold-start -> trending.

Chỉ điều phối các service khác (interaction / affinity / product) + cache. Dựng DTO qua
ProductService.get_product_dtos_by_ids (đã batch, không N+1).
"""
from __future__ import annotations

import json

from xime.starters.cache import CacheService

from app.service.affinity_service import AffinityService
from app.service.cooccurrence_service import CooccurrenceService
from app.service.interaction_service import InteractionService
from app.service.product_service import ProductService


class RecommendationService:
    _TRENDING_CACHE_KEY = "rec:trending"
    _TRENDING_TTL = 900  # giây / seconds (15 phút)
    # Số category đầu (theo affinity) để gom ứng viên cho for-you
    _TOP_CATEGORIES = 10

    def __init__(
        self,
        cache: CacheService,
        interaction_service: InteractionService,
        affinity_service: AffinityService,
        product_service: ProductService,
        cooccurrence_service: CooccurrenceService,
    ) -> None:
        self._cache = cache
        self._interaction = interaction_service
        self._affinity = affinity_service
        self._product = product_service
        self._cooccurrence = cooccurrence_service

    async def recently_viewed(self, user_id: int, limit: int = 10) -> list[dict]:
        ids = await self._interaction.get_recent_viewed_product_ids(user_id, limit)
        return await self._product.get_product_dtos_by_ids(ids)

    async def trending(self, limit: int = 10) -> list[dict]:
        # Cache toàn cục (một entry) TTL ngắn - trending đổi chậm, đọc nhiều.
        cached = await self._cache_get_json(self._TRENDING_CACHE_KEY)
        if cached is not None:
            return cached[:limit]
        ids = await self._interaction.get_trending_product_ids(limit)
        dtos = await self._product.get_product_dtos_by_ids(ids)
        await self._cache_set_json(self._TRENDING_CACHE_KEY, dtos)
        return dtos

    async def for_you(self, user_id: int, limit: int = 10) -> list[dict]:
        top_cats = await self._affinity.get_top_category_ids(
            user_id, limit=self._TOP_CATEGORIES
        )
        if not top_cats:
            # Cold-start: chưa có affinity -> trả về thịnh hành
            return await self.trending(limit)

        purchased = await self._interaction.get_purchased_product_ids(user_id)
        # Gom ứng viên theo thứ tự category yêu thích, loại đã mua / trùng / đã xóa
        candidate_ids: list[int] = []
        seen: set[int] = set()
        for category_id in top_cats:
            products = await self._product.find_products_by_category_id(category_id)
            for product in products:
                if (
                    product.id in seen
                    or product.id in purchased
                    or product.is_delete
                ):
                    continue
                seen.add(product.id)
                candidate_ids.append(product.id)
                if len(candidate_ids) >= limit:
                    break
            if len(candidate_ids) >= limit:
                break

        if not candidate_ids:
            return await self.trending(limit)
        return await self._product.get_product_dtos_by_ids(candidate_ids)

    async def related(self, product_id: int, limit: int = 10) -> list[dict]:
        """Sản phẩm hay mua cùng `product_id` (co-occurrence). Rỗng nếu chưa dựng bảng."""
        ids = await self._cooccurrence.get_related_product_ids(product_id, limit)
        return await self._product.get_product_dtos_by_ids(ids)

    # ─── Cache helpers (JSON) ───────────────────────────────────────────────
    async def _cache_get_json(self, key: str):
        raw = await self._cache.get(key)
        return json.loads(raw) if raw is not None else None

    async def _cache_set_json(self, key: str, value) -> None:
        payload = json.dumps(value, default=float).encode("utf-8")
        await self._cache.set(key, payload, ttl=self._TRENDING_TTL)
