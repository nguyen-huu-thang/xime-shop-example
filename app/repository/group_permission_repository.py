from __future__ import annotations

from sqlalchemy import select

from app.entity.group_permission import GroupPermission
from app.entity.permission import Permission
from xime.starters.sqlalchemy import CrudRepository


class GroupPermissionRepository(CrudRepository[GroupPermission]):
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

    async def find_by_group_permission_target(
        self, group_id: int, permission_id: int, target_id: int | None
    ) -> GroupPermission | None:
        # Exact-match an entry (same group + permission + target) so assign is
        # idempotent and never inserts duplicate rows. Uses .first() to tolerate any
        # pre-existing duplicates without raising MultipleResultsFound.
        # Tìm đúng entry (cùng group + permission + target) để assign idempotent,
        # không bao giờ chèn bản ghi trùng.
        stmt = (
            select(GroupPermission)
            .where(GroupPermission.group_id == group_id)
            .where(GroupPermission.permission_id == permission_id)
        )
        if target_id is None:
            stmt = stmt.where(GroupPermission.target_id.is_(None))
        else:
            stmt = stmt.where(GroupPermission.target_id == target_id)
        result = await self.session.execute(stmt.limit(1))
        return result.scalars().first()
