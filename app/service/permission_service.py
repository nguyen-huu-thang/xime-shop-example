"""
PermissionService - quản lý quyền hệ thống.
Port từ PermissionService.php.
"""
from __future__ import annotations

from xime.core.transaction.manager import TransactionManager

from app.entity.permission import Permission
from app.exception.app_exception import AppException
from app.repository.permission_repository import PermissionRepository


class PermissionService:
    def __init__(
        self,
        transaction: TransactionManager,
        permission_repository: PermissionRepository,
    ) -> None:
        self._transaction = transaction
        self._repo = permission_repository

    async def get_all_permissions(self) -> list[Permission]:
        async with self._transaction():
            return await self._repo.find_all()

    async def get_permission_names(self) -> list[str]:
        """Return list of all permission names (viewAllPermissions).
        Trả về danh sách tên tất cả quyền.
        """
        perms = await self.get_all_permissions()
        return [p.name for p in perms]

    async def get_permission_by_id(self, perm_id: int) -> Permission | None:
        async with self._transaction():
            return await self._repo.find(perm_id)

    async def get_permission_by_name(self, name: str) -> Permission | None:
        async with self._transaction():
            return await self._repo.find_by_name(name)

    async def create_permission(self, name: str, description: str | None = None) -> Permission:
        existing = await self.get_permission_by_name(name)
        if existing:
            raise AppException("E2001")
        async with self._transaction():
            perm = Permission(name=name, description=description)
            return await self._repo.save(perm)

    async def update_permission(self, perm_id: int, data: dict) -> Permission:
        async with self._transaction():
            perm = await self._repo.find(perm_id)
            if not perm:
                raise AppException("E2024")
            if "name" in data:
                perm.name = data["name"]
            if "description" in data:
                perm.description = data["description"]
            return await self._repo.save(perm)

    async def delete_permission(self, perm_id: int) -> None:
        async with self._transaction():
            perm = await self._repo.find(perm_id)
            if not perm:
                raise AppException("E2024")
            await self._repo.delete(perm)
