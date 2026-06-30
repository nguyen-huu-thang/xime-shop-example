"""
InteractionService - ghi nhật ký hành động người dùng (implicit feedback) cho cá nhân hóa.

record() là điểm vào duy nhất để ghi một interaction. Đặc tính:
  - An toàn: ghi log KHÔNG được làm hỏng hành động chính. Mọi lỗi được bắt + log lại rồi nuốt,
    record() không bao giờ raise ra ngoài (controller gọi không cần try/except).
  - Throttle: hành động tín hiệu yếu (view, search_click) bị chặn trùng trong THROTTLE_WINDOW
    để khỏi phình bảng; tín hiệu mạnh (add_to_cart/wishlist/purchase/review) luôn ghi.
  - Tự mở transaction riêng (gọi sau khi thao tác chính đã xong, không lồng transaction khác).

Phase 3 sẽ nối thêm cập nhật affinity (decay-on-write) vào record().
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from xime.core.transaction.manager import TransactionManager

from app.entity.interaction import Interaction
from app.repository.interaction_repository import InteractionRepository
from app.repository.product_repository import ProductRepository
from app.service.action_service import ActionService
from app.service.affinity_service import AffinityService

logger = logging.getLogger(__name__)


class InteractionService:
    # Cửa sổ chặn trùng cho tín hiệu yếu (giây). 10 phút.
    # Throttle window for weak signals (seconds). 10 minutes.
    _THROTTLE_WINDOW = 600
    # Hành động bị throttle (tín hiệu yếu, lượng ghi lớn).
    _THROTTLED = {"view", "search_click"}

    def __init__(
        self,
        transaction: TransactionManager,
        interaction_repository: InteractionRepository,
        action_service: ActionService,
        affinity_service: AffinityService,
        product_repository: ProductRepository,
    ) -> None:
        self._transaction = transaction
        self._repo = interaction_repository
        self._action_svc = action_service
        self._affinity_svc = affinity_service
        self._product_repo = product_repository

    async def record(self, user_id: int, product_id: int, action_name: str) -> None:
        """Ghi một interaction (fault-tolerant, không bao giờ raise). Throttle tín hiệu yếu."""
        try:
            # Resolve action TRƯỚC khi mở transaction của ta (get_by_name có thể tự mở
            # transaction để nạp registry - tránh lồng transaction không reentrant).
            # Resolve action before opening our transaction (registry load may open its own).
            action = await self._action_svc.get_by_name(action_name)
            if action is None:
                logger.warning("Bỏ qua interaction: action '%s' không tồn tại", action_name)
                return

            now = datetime.now(timezone.utc)
            async with self._transaction():
                if action_name in self._THROTTLED:
                    since = now - timedelta(seconds=self._THROTTLE_WINDOW)
                    if await self._repo.exists_recent(
                        user_id, product_id, action.id, since
                    ):
                        return  # đã ghi gần đây -> bỏ qua
                await self._repo.save(
                    Interaction(
                        user_id=user_id,
                        product_id=product_id,
                        action_id=action.id,
                    )
                )
                # Cập nhật affinity theo category sản phẩm (decay-on-write), cùng transaction
                # Update category affinity (decay-on-write) in the same transaction
                product = await self._product_repo.find(product_id)
                if product is not None and product.category_id is not None:
                    await self._affinity_svc.apply(
                        user_id, product.category_id, action.score, now
                    )
        except Exception:
            # Không để lỗi ghi log phá hành động chính; log đầy đủ để điều tra.
            # Never let logging break the primary action; log fully for investigation.
            logger.exception(
                "Ghi interaction thất bại (user=%s product=%s action=%s)",
                user_id,
                product_id,
                action_name,
            )

    async def get_recent_viewed_product_ids(
        self, user_id: int, limit: int = 10
    ) -> list[int]:
        """Id sản phẩm user xem gần đây nhất, khử trùng, giữ thứ tự mới -> cũ."""
        view = await self._action_svc.get_by_name("view")
        if view is None:
            return []
        async with self._transaction():
            # Lấy dư để sau khi khử trùng vẫn đủ `limit`
            rows = await self._repo.find_recent_by_user_and_action(
                user_id, view.id, limit * 5
            )
        seen: list[int] = []
        for r in rows:
            if r.product_id not in seen:
                seen.append(r.product_id)
            if len(seen) >= limit:
                break
        return seen

    # Cửa sổ tính thịnh hành (giây). 14 ngày.
    _TRENDING_WINDOW = 14 * 24 * 3600

    async def get_trending_product_ids(self, limit: int = 10) -> list[int]:
        """Id sản phẩm thịnh hành (tổng trọng số điểm trong cửa sổ gần đây)."""
        since = datetime.now(timezone.utc) - timedelta(seconds=self._TRENDING_WINDOW)
        async with self._transaction():
            return await self._repo.trending_product_ids(since, limit)

    async def get_purchased_product_ids(self, user_id: int) -> set[int]:
        """Tập product_id user đã mua (để loại khỏi gợi ý)."""
        purchase = await self._action_svc.get_by_name("purchase")
        if purchase is None:
            return set()
        async with self._transaction():
            return await self._repo.product_ids_by_user_and_action(
                user_id, purchase.id
            )
