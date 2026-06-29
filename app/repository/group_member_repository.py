from __future__ import annotations

from sqlalchemy import func, select

from app.entity.group import Group
from app.entity.group_member import GroupMember
from xime.starters.sqlalchemy import CrudRepository


class GroupMemberRepository(CrudRepository[GroupMember]):
    model = GroupMember

    async def find_by_user_id(self, user_id: int) -> list[GroupMember]:
        result = await self.session.execute(
            select(GroupMember).where(GroupMember.user_id == user_id)
        )
        return list(result.scalars().all())

    async def find_by_group_id(self, group_id: int) -> list[GroupMember]:
        result = await self.session.execute(
            select(GroupMember).where(GroupMember.group_id == group_id)
        )
        return list(result.scalars().all())

    async def find_by_user_and_group(
        self, user_id: int, group_id: int
    ) -> GroupMember | None:
        result = await self.session.execute(
            select(GroupMember)
            .where(GroupMember.user_id == user_id)
            .where(GroupMember.group_id == group_id)
        )
        return result.scalar_one_or_none()

    async def find_groups_by_user_id(self, user_id: int) -> list[Group]:
        # Join GroupMember → Group and return Group objects
        # JOIN GroupMember → Group, trả về danh sách Group
        result = await self.session.execute(
            select(Group)
            .join(GroupMember, GroupMember.group_id == Group.id)
            .where(GroupMember.user_id == user_id)
        )
        return list(result.scalars().all())

    async def find_users_by_group_id(self, group_id: int) -> list:
        # Returns User objects in a group (imported lazily to avoid circular)
        # Trả về danh sách User trong nhóm
        from app.entity.user import User
        result = await self.session.execute(
            select(User)
            .join(GroupMember, GroupMember.user_id == User.id)
            .where(GroupMember.group_id == group_id)
        )
        return list(result.scalars().all())

    async def exists_by_user_and_group(self, user_id: int, group_id: int) -> bool:
        result = await self.session.execute(
            select(func.count())
            .select_from(GroupMember)
            .where(GroupMember.user_id == user_id)
            .where(GroupMember.group_id == group_id)
        )
        return result.scalar_one() > 0
