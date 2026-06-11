from __future__ import annotations

from sqlalchemy import select

from app.entity.group_permission import GroupPermission
from app.entity.permission import Permission
from app.repository.base_repository import BaseRepository


class GroupPermissionRepository(BaseRepository[GroupPermission]):
    model = GroupPermission

    async def find_group_permission(
        self, group_id: int, permission_name: str
    ) -> list[GroupPermission]:
        # Join with Permission table to filter by name; null target_id sorts first
        # Join với bảng Permission để lọc theo tên; null target_id đứng đầu
        result = await self.session.execute(
            select(GroupPermission)
            .join(Permission, GroupPermission.permission_id == Permission.id)
            .where(GroupPermission.group_id == group_id)
            .where(Permission.name == permission_name)
            .order_by(GroupPermission.target_id.asc().nullsfirst())
        )
        return list(result.scalars().all())

    async def find_by_group_id(self, group_id: int) -> list[GroupPermission]:
        result = await self.session.execute(
            select(GroupPermission).where(GroupPermission.group_id == group_id)
        )
        return list(result.scalars().all())

    async def find_by_group_and_permission(
        self, group_id: int, permission_id: int
    ) -> GroupPermission | None:
        result = await self.session.execute(
            select(GroupPermission)
            .where(GroupPermission.group_id == group_id)
            .where(GroupPermission.permission_id == permission_id)
        )
        return result.scalar_one_or_none()
