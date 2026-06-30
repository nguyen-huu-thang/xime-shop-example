"""
ActionService - tra loại hành động (view/add_to_cart/purchase...) và trọng số điểm.

Đọc đi qua ActionRegistry (cache RAM). Bảng actions được seed sẵn (xem app/seed.py), gần như
không đổi lúc chạy nên không có create/update/delete ở đây; nếu sửa score trong DB thì gọi
invalidate() để nạp lại. Xem app/cache/action_registry.py.
"""
from __future__ import annotations

from xime.core.transaction.manager import TransactionManager

from app.cache.action_registry import ActionRegistry
from app.entity.action import Action
from app.repository.action_repository import ActionRepository


class ActionService:
    def __init__(
        self,
        transaction: TransactionManager,
        action_repository: ActionRepository,
        action_registry: ActionRegistry,
    ) -> None:
        self._transaction = transaction
        self._repo = action_repository
        self._registry = action_registry

    async def _ensure_loaded(self) -> None:
        # Nạp bảng actions vào RAM lần đầu (hoặc sau invalidate)
        # Load the actions table into RAM on first use (or after invalidate)
        if not self._registry.is_loaded():
            async with self._transaction():
                actions = await self._repo.find_all()
            self._registry.load(actions)

    async def get_all_actions(self) -> list[Action]:
        await self._ensure_loaded()
        return self._registry.all()

    async def get_by_name(self, name: str) -> Action | None:
        await self._ensure_loaded()
        return self._registry.get_by_name(name)

    async def get_by_id(self, action_id: int) -> Action | None:
        await self._ensure_loaded()
        return self._registry.get_by_id(action_id)

    async def get_score(self, name: str) -> int:
        """Trọng số điểm của một loại hành động; 0 nếu không có (an toàn cho tính điểm)."""
        action = await self.get_by_name(name)
        return action.score if action is not None else 0

    def invalidate(self) -> None:
        self._registry.invalidate()
