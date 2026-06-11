from __future__ import annotations

from sqlalchemy import select

from app.entity.permission import Permission
from app.entity.user_permission import UserPermission
from app.repository.base_repository import BaseRepository


class UserPermissionRepository(BaseRepository[UserPermission]):
    model = UserPermission

    async def find_user_permission(
        self, user_id: int, permission_name: str
    ) -> list[UserPermission]:
        # Join with Permission table to filter by name; null target_id sorts first
        # Join với bảng Permission để lọc theo tên; null target_id đứng đầu
        result = await self.session.execute(
            select(UserPermission)
            .join(Permission, UserPermission.permission_id == Permission.id)
            .where(UserPermission.user_id == user_id)
            .where(Permission.name == permission_name)
            .order_by(UserPermission.target_id.asc().nullsfirst())
        )
        return list(result.scalars().all())

    async def find_by_user_id(self, user_id: int) -> list[UserPermission]:
        result = await self.session.execute(
            select(UserPermission).where(UserPermission.user_id == user_id)
        )
        return list(result.scalars().all())

    async def find_by_user_and_permission(
        self, user_id: int, permission_id: int
    ) -> UserPermission | None:
        result = await self.session.execute(
            select(UserPermission)
            .where(UserPermission.user_id == user_id)
            .where(UserPermission.permission_id == permission_id)
        )
        return result.scalar_one_or_none()
