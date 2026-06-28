"""
GroupMemberService - quản lý thành viên nhóm.
Port từ GroupMemberService.php.
"""
from __future__ import annotations

from xime.core.transaction.manager import TransactionManager

from app.entity.group import Group
from app.entity.group_member import GroupMember
from app.exception.app_exception import AppException
from app.repository.group_member_repository import GroupMemberRepository
from app.service.group_service import GroupService
from app.service.user_service import UserService


class GroupMemberService:
    def __init__(
        self,
        transaction: TransactionManager,
        group_member_repository: GroupMemberRepository,
        user_service: UserService,
        group_service: GroupService,
    ) -> None:
        self._transaction = transaction
        self._repo = group_member_repository
        self._user_svc = user_service
        self._group_svc = group_service

    async def add_user_to_group(self, user_id: int, group_id: int) -> GroupMember:
        # Validate existence; each service opens its own transaction
        # Xác thực tồn tại; mỗi service tự mở transaction riêng
        user = await self._user_svc.get_user_by_id(user_id)
        if not user:
            raise AppException("E1004")
        await self._group_svc.get_group_by_id(group_id)  # raises E10110 if missing
        async with self._transaction():
            member = GroupMember(user_id=user_id, group_id=group_id)
            return await self._repo.save(member)

    async def remove_user_from_group(self, user_id: int, group_id: int) -> None:
        user = await self._user_svc.get_user_by_id(user_id)
        if not user:
            raise AppException("E1004")
        await self._group_svc.get_group_by_id(group_id)
        async with self._transaction():
            member = await self._repo.find_by_user_and_group(user_id, group_id)
            if member:
                await self._repo.delete(member)

    async def find_groups_by_user(self, user: "object") -> list[Group]:
        """Return groups the user belongs to.
        Trả về danh sách nhóm mà user thuộc về.
        """
        async with self._transaction():
            return await self._repo.find_groups_by_user_id(user.id)

    async def get_groups_by_user(self, user_id: int) -> list[Group]:
        user = await self._user_svc.get_user_by_id(user_id)
        if not user:
            raise AppException("E1004")
        async with self._transaction():
            return await self._repo.find_groups_by_user_id(user_id)

    async def get_users_in_group(self, group_id: int) -> list:
        await self._group_svc.get_group_by_id(group_id)
        async with self._transaction():
            return await self._repo.find_users_by_group_id(group_id)

    async def is_user_in_group(self, user_id: int, group_id: int) -> bool:
        user = await self._user_svc.get_user_by_id(user_id)
        if not user:
            raise AppException("E1004")
        await self._group_svc.get_group_by_id(group_id)
        async with self._transaction():
            return await self._repo.exists_by_user_and_group(user_id, group_id)
