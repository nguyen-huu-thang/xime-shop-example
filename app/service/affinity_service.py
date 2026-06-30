"""
AffinityService - hồ sơ sở thích user theo category, materialized + decay-on-write.

Công thức (xem ca-nhan-hoa-nguoi-dung.md):
  - Ghi: decay điểm cũ về hiện tại rồi cộng điểm mới
        score_new = score_old * 0.5 ^ (elapsed / HALF_LIFE) + add_score; updated_at = now
  - Đọc: decay tiếp tới read-time để so sánh công bằng giữa các category
        current = score * 0.5 ^ ((read_now - updated_at) / HALF_LIFE)

`apply()` là TRANSACTION-AGNOSTIC: chạy trong transaction do InteractionService.record() mở
(ghi interaction + cập nhật affinity atomic). `get_top_category_ids()` tự mở transaction (đọc độc lập).
"""
from __future__ import annotations

from datetime import datetime, timezone

from xime.core.transaction.manager import TransactionManager

from app.entity.user_category_affinity import UserCategoryAffinity
from app.repository.user_category_affinity_repository import (
    UserCategoryAffinityRepository,
)

# Chu kỳ bán rã (giây). 30 ngày: sau 30 ngày, một đóng góp còn nửa điểm.
# Half-life (seconds). 30 days.
HALF_LIFE_SECONDS = 30 * 24 * 3600


class AffinityService:
    def __init__(
        self,
        transaction: TransactionManager,
        user_category_affinity_repository: UserCategoryAffinityRepository,
    ) -> None:
        self._transaction = transaction
        self._repo = user_category_affinity_repository

    @staticmethod
    def _decay_factor(elapsed_seconds: float) -> float:
        # 0.5 ^ (elapsed / half_life); elapsed âm (lệch giờ) coi như 0 -> factor 1.0
        if elapsed_seconds <= 0:
            return 1.0
        return 0.5 ** (elapsed_seconds / HALF_LIFE_SECONDS)

    async def apply(
        self,
        user_id: int,
        category_id: int,
        add_score: float,
        now: datetime | None = None,
    ) -> None:
        """Decay-on-write: cộng add_score vào affinity (user, category). TRANSACTION-AGNOSTIC.

        Phải chạy bên trong transaction đang mở (do record() mở). Không tự mở transaction.
        """
        now = now or datetime.now(timezone.utc)
        row = await self._repo.get_one(user_id, category_id)
        if row is None:
            await self._repo.save(
                UserCategoryAffinity(
                    user_id=user_id,
                    category_id=category_id,
                    score=float(add_score),
                    updated_at=now,
                )
            )
            return
        elapsed = (now - row.updated_at).total_seconds()
        row.score = row.score * self._decay_factor(elapsed) + float(add_score)
        row.updated_at = now
        await self._repo.save(row)

    async def get_top_category_ids(
        self, user_id: int, now: datetime | None = None, limit: int | None = None
    ) -> list[int]:
        """Id category user thích nhất (đã decay tới read-time), giảm dần. Tự mở transaction."""
        now = now or datetime.now(timezone.utc)
        async with self._transaction():
            rows = await self._repo.find_by_user(user_id)
        scored: list[tuple[int, float]] = []
        for r in rows:
            elapsed = (now - r.updated_at).total_seconds()
            current = r.score * self._decay_factor(elapsed)
            scored.append((r.category_id, current))
        scored.sort(key=lambda x: x[1], reverse=True)
        ids = [cid for cid, _ in scored]
        return ids[:limit] if limit is not None else ids
