"""
GroupService - quản lý nhóm người dùng.
Port từ GroupService.php.
"""
from __future__ import annotations

from xime.core.transaction.manager import TransactionManager

from app.entity.group import Group
from app.exception.app_exception import AppException
from app.repository.group_repository import GroupRepository


class GroupService:
    def __init__(
        self,
        transaction: TransactionManager,
        group_repository: GroupRepository,
    ) -> None:
        self._transaction = transaction
        self._repo = group_repository

    async def get_group_by_id(self, group_id: int) -> Group:
        """Return group; raise E10110 if not found.
        Trả về nhóm; ném E10110 nếu không tìm thấy.
        """
        async with self._transaction():
            group = await self._repo.find(group_id)
        if not group:
            raise AppException("E10110")
        return group

    async def get_paginated_groups(self, page: int, limit: int) -> list[Group]:
        async with self._transaction():
            return await self._repo.find_all_paginated(page, limit)

    async def create_group(self, name: str, description: str | None = None) -> Group:
        async with self._transaction():
            group = Group(name=name, description=description)
            return await self._repo.save(group)

    async def update_group(self, group_id: int, data: dict) -> Group:
        async with self._transaction():
            group = await self._repo.find(group_id)
            if not group:
                raise AppException("E10110")
            if "name" in data:
                group.name = data["name"]
            if "description" in data:
                group.description = data["description"]
            return await self._repo.save(group)

    async def delete_group(self, group_id: int) -> None:
        async with self._transaction():
            group = await self._repo.find(group_id)
            if not group:
                raise AppException("E10110")
            await self._repo.delete(group)
