"""
PermissionService - quản lý quyền hệ thống.
Port từ PermissionService.php.

Đọc đi qua PermissionRegistry (cache RAM). Ghi (create/update/delete) đụng DB rồi invalidate
registry để lần đọc kế nạp lại. Xem app/cache/permission_registry.py.
"""
from __future__ import annotations

from xime.core.transaction.manager import TransactionManager

from app.cache.permission_registry import PermissionRegistry
from app.entity.permission import Permission
from app.exception.app_exception import AppException
from app.repository.permission_repository import PermissionRepository


class PermissionService:
    def __init__(
        self,
        transaction: TransactionManager,
        permission_repository: PermissionRepository,
        permission_registry: PermissionRegistry,
    ) -> None:
        self._transaction = transaction
        self._repo = permission_repository
        self._registry = permission_registry

    async def _ensure_loaded(self) -> None:
        # Nạp bảng permissions vào RAM lần đầu (hoặc sau invalidate)
        # Load the permissions table into RAM on first use (or after invalidate)
        if not self._registry.is_loaded():
            async with self._transaction():
                perms = await self._repo.find_all()
            self._registry.load(perms)

    async def get_all_permissions(self) -> list[Permission]:
        await self._ensure_loaded()
        return self._registry.all()

    async def get_permission_names(self) -> list[str]:
        """Return list of all permission names (viewAllPermissions).
        Trả về danh sách tên tất cả quyền.
        """
        await self._ensure_loaded()
        return self._registry.names()

    async def get_permission_by_id(self, perm_id: int) -> Permission | None:
        await self._ensure_loaded()
        return self._registry.get_by_id(perm_id)

    async def get_permission_by_name(self, name: str) -> Permission | None:
        await self._ensure_loaded()
        return self._registry.get_by_name(name)

    async def create_permission(self, name: str, description: str | None = None) -> Permission:
        existing = await self.get_permission_by_name(name)
        if existing:
            raise AppException("E2001")
        async with self._transaction():
            perm = Permission(name=name, description=description)
            await self._repo.save(perm)
        # Invalidate sau khi commit để lần đọc kế nạp lại snapshot mới
        # Invalidate after commit so the next read reloads a fresh snapshot
        self._registry.invalidate()
        return perm

    async def update_permission(self, perm_id: int, data: dict) -> Permission:
        async with self._transaction():
            perm = await self._repo.find(perm_id)
            if not perm:
                raise AppException("E2024")
            if "name" in data:
                perm.name = data["name"]
            if "description" in data:
                perm.description = data["description"]
            await self._repo.save(perm)
        self._registry.invalidate()
        return perm

    async def delete_permission(self, perm_id: int) -> None:
        async with self._transaction():
            perm = await self._repo.find(perm_id)
            if not perm:
                raise AppException("E2024")
            await self._repo.delete(perm)
        self._registry.invalidate()
