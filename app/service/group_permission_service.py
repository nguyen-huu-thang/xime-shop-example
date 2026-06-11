"""
GroupPermissionService — quản lý quyền của nhóm.
Port từ GroupPermissionService.php.
"""
from __future__ import annotations

from xime.core.transaction.manager import TransactionManager

from app.entity.group import Group
from app.entity.group_permission import GroupPermission
from app.exception.app_exception import AppException
from app.repository.group_permission_repository import GroupPermissionRepository
from app.service.group_service import GroupService
from app.service.permission_service import PermissionService


class GroupPermissionService:
    def __init__(
        self,
        transaction: TransactionManager,
        group_permission_repository: GroupPermissionRepository,
        group_service: GroupService,
        permission_service: PermissionService,
    ) -> None:
        self._transaction = transaction
        self._repo = group_permission_repository
        self._group_svc = group_service
        self._perm_svc = permission_service

    async def assign_permissions(self, group_id: int, permissions: dict) -> list[dict]:
        """Assign permissions to a group (bulk).
        Gán quyền cho nhóm — bulk theo dict {perm_name: {is_active, is_denied, target}}.
        """
        await self._group_svc.get_group_by_id(group_id)  # raises E10110 if missing

        entries: list[tuple] = []
        for perm_name, perm_data in permissions.items():
            perm = await self._perm_svc.get_permission_by_name(perm_name)
            if not perm:
                continue
            if "target" not in perm_data:
                raise AppException("E1004")
            target_raw = perm_data["target"]
            target_id: int | None = None if target_raw == "all" else target_raw
            entries.append((perm.id, perm_name, perm_data, target_id))

        assigned: list[dict] = []
        async with self._transaction():
            for perm_id, perm_name, perm_data, target_id in entries:
                gp = GroupPermission(
                    group_id=group_id,
                    permission_id=perm_id,
                    is_active=perm_data.get("is_active", True),
                    is_denied=perm_data.get("is_denied", False),
                    target_id=target_id,
                )
                await self._repo.save(gp)
                assigned.append({"permission": perm_name, "status": "assigned"})

        return assigned

    async def get_permissions_by_group(self, group: Group) -> list[str]:
        async with self._transaction():
            gps = await self._repo.find_by_group_id(group.id)
        return [gp.permission_id for gp in gps]  # caller resolves names if needed

    async def update_permission(self, group_id: int, permissions: dict) -> list[dict]:
        """Update existing group permissions (bulk).
        Cập nhật quyền hiện có của nhóm — bulk.
        """
        await self._group_svc.get_group_by_id(group_id)

        entries: list[tuple] = []
        for perm_name, perm_data in permissions.items():
            perm = await self._perm_svc.get_permission_by_name(perm_name)
            if not perm:
                continue
            if "target" not in perm_data:
                raise AppException("E1004")
            target_raw = perm_data["target"]
            target_id: int | None = None if target_raw == "all" else target_raw
            entries.append((perm.id, perm_name, perm_data, target_id))

        updated: list[dict] = []
        async with self._transaction():
            for perm_id, perm_name, perm_data, target_id in entries:
                gp = await self._repo.find_by_group_and_permission(group_id, perm_id)
                if not gp:
                    raise AppException("E2023")
                gp.is_active = perm_data.get("is_active", gp.is_active)
                gp.is_denied = perm_data.get("is_denied", gp.is_denied)
                gp.target_id = target_id
                await self._repo.save(gp)
                updated.append({"permission": perm_name, "status": "updated"})

        return updated

    async def has_permission(
        self, group_id: int, permission_name: str, target_id: int | None = None
    ) -> int:
        """Return -1 (denied), 0 (none), or 1 (granted).
        Trả về -1 (từ chối), 0 (không có), hoặc 1 (được cấp).
        """
        async with self._transaction():
            gps = await self._repo.find_group_permission(group_id, permission_name)

        for gp in gps:
            if not gp.is_active:
                continue
            if gp.target_id is None:
                return -1 if gp.is_denied else 1
            if gp.target_id == target_id:
                return -1 if gp.is_denied else 1

        return 0

    async def delete_permissions(self, group_id: int, permissions: list[str]) -> None:
        """Delete named permissions from a group.
        Xoá các quyền theo tên khỏi nhóm.
        """
        await self._group_svc.get_group_by_id(group_id)

        perm_ids: list[int] = []
        for perm_name in permissions:
            perm = await self._perm_svc.get_permission_by_name(perm_name)
            if perm:
                perm_ids.append(perm.id)

        async with self._transaction():
            for perm_id in perm_ids:
                gp = await self._repo.find_by_group_and_permission(group_id, perm_id)
                if gp:
                    await self._repo.delete(gp)
