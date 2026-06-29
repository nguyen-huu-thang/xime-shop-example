"""
GroupPermissionService - quản lý quyền của nhóm.
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
        Gán quyền cho nhóm - bulk theo dict {perm_name: {is_active, is_denied, target}}.
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
            to_save: list[GroupPermission] = []
            for perm_id, perm_name, perm_data, target_id in entries:
                # Idempotent: reuse the existing (group, permission, target) entry instead
                # of inserting a duplicate row on repeated assign calls.
                # Idempotent: tái dùng entry (group, permission, target) đã có thay vì chèn
                # bản ghi trùng khi gọi assign nhiều lần.
                gp = await self._repo.find_by_group_permission_target(
                    group_id, perm_id, target_id
                )
                if gp is None:
                    gp = GroupPermission(
                        group_id=group_id, permission_id=perm_id, target_id=target_id
                    )
                gp.is_active = perm_data.get("is_active", True)
                gp.is_denied = perm_data.get("is_denied", False)
                gp.target_id = target_id
                to_save.append(gp)
                assigned.append({"permission": perm_name, "status": "assigned"})
            # Một flush cho cả lô thay vì flush từng quyền
            # One flush for the whole batch instead of per permission
            await self._repo.save_all(to_save)

        return assigned

    async def get_permissions_by_group(self, group: Group) -> list[str]:
        async with self._transaction():
            gps = await self._repo.find_by_group_id(group.id)
        return [gp.permission_id for gp in gps]  # caller resolves names if needed

    async def get_records_by_group_ids(self, group_ids: list[int]) -> list[GroupPermission]:
        """Return all GroupPermission rows for the given groups (bulk effective-permission eval).
        Trả về toàn bộ bản ghi quyền của các nhóm - phục vụ tính quyền hiệu lực hàng loạt
        (nạp một lần thay vì truy vấn lặp từng quyền).
        """
        if not group_ids:
            return []
        async with self._transaction():
            records: list[GroupPermission] = []
            for gid in group_ids:
                records.extend(await self._repo.find_by_group_id(gid))
            return records

    async def update_permission(self, group_id: int, permissions: dict) -> list[dict]:
        """Update existing group permissions (bulk).
        Cập nhật quyền hiện có của nhóm - bulk.
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
            to_save: list[GroupPermission] = []
            for perm_id, perm_name, perm_data, target_id in entries:
                gp = await self._repo.find_by_group_and_permission(group_id, perm_id)
                if not gp:
                    raise AppException("E2023")
                gp.is_active = perm_data.get("is_active", gp.is_active)
                gp.is_denied = perm_data.get("is_denied", gp.is_denied)
                gp.target_id = target_id
                to_save.append(gp)
                updated.append({"permission": perm_name, "status": "updated"})
            # Một flush cho cả lô thay vì flush từng quyền
            # One flush for the whole batch instead of per permission
            await self._repo.save_all(to_save)

        return updated

    async def has_permission(
        self, group_id: int, permission_name: str, scope_ids: set[int]
    ) -> int:
        """Return -1 (denied), 0 (none), or 1 (granted).
        Trả về -1 (từ chối), 0 (không có), hoặc 1 (được cấp).

        scope_ids: tập target_id được coi là khớp. Quyền khớp-đúng-đối-tượng -> {target_id};
        quyền scope theo category -> chuỗi tổ tiên của category; truy vấn global -> tập rỗng.

        Deny-overrides: quét HẾT bản ghi áp dụng được; có deny đang active là -1, không thì xét
        allow; không thoát sớm theo bản ghi đầu tiên (tránh allow che deny tùy thứ tự DB).
        """
        async with self._transaction():
            gps = await self._repo.find_group_permission(group_id, permission_name)

        saw_allow = False
        for gp in gps:
            if not gp.is_active:
                continue
            # Record applies if it is global (target None) or its target is in scope
            # Bản ghi áp dụng nếu là global (target None) hoặc target nằm trong scope
            if gp.target_id is None or gp.target_id in scope_ids:
                if gp.is_denied:
                    return -1
                saw_allow = True

        return 1 if saw_allow else 0

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
