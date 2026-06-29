"""
UserPermissionService - quản lý quyền trực tiếp của user.
Port từ UserPermissionService.php.
"""
from __future__ import annotations

from xime.core.transaction.manager import TransactionManager

from app.entity.user import User
from app.entity.user_permission import UserPermission
from app.exception.app_exception import AppException
from app.repository.user_permission_repository import UserPermissionRepository
from app.service.permission_service import PermissionService
from app.service.user_service import UserService


class UserPermissionService:
    def __init__(
        self,
        transaction: TransactionManager,
        user_permission_repository: UserPermissionRepository,
        user_service: UserService,
        permission_service: PermissionService,
    ) -> None:
        self._transaction = transaction
        self._repo = user_permission_repository
        self._user_svc = user_service
        self._perm_svc = permission_service

    async def assign_permissions(self, user_id: int, permissions: dict) -> list[dict]:
        """Assign permissions to a user (bulk).
        Gán quyền cho user - bulk theo dict {perm_name: {is_active, is_denied, target}}.
        """
        user = await self._user_svc.get_user_by_id(user_id)
        if not user:
            raise AppException("E1004")

        # Resolve permissions and validate target outside write transaction
        # Resolve và validate quyền trước khi mở transaction ghi
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
                # Idempotent: reuse the existing (user, permission, target) entry instead
                # of inserting a duplicate row on repeated assign calls.
                # Idempotent: tái dùng entry (user, permission, target) đã có thay vì chèn
                # bản ghi trùng khi gọi assign nhiều lần.
                up = await self._repo.find_by_user_permission_target(
                    user_id, perm_id, target_id
                )
                if up is None:
                    up = UserPermission(
                        user_id=user_id, permission_id=perm_id, target_id=target_id
                    )
                up.is_active = perm_data.get("is_active", True)
                up.is_denied = perm_data.get("is_denied", False)
                up.target_id = target_id
                await self._repo.save(up)
                assigned.append({"permission": perm_name, "status": "assigned"})

        return assigned

    async def set_permission(self, user: User, permissions: list) -> list[UserPermission]:
        """Bulk-assign for superadmin seed (all active, not denied, target null).
        Gán quyền hàng loạt khi khởi tạo superadmin.
        """
        result: list[UserPermission] = []
        async with self._transaction():
            for perm in permissions:
                up = UserPermission(
                    user_id=user.id,
                    permission_id=perm.id,
                    is_active=True,
                    is_denied=False,
                    target_id=None,
                )
                result.append(await self._repo.save(up))
        return result

    async def get_permissions_by_user_id(self, user_id: int) -> list[UserPermission]:
        async with self._transaction():
            return await self._repo.find_by_user_id(user_id)

    async def update_permission(self, user_id: int, permissions: dict) -> list[dict]:
        """Update existing user permissions (bulk).
        Cập nhật quyền hiện có của user - bulk.
        """
        user = await self._user_svc.get_user_by_id(user_id)
        if not user:
            raise AppException("E1004")

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
                up = await self._repo.find_by_user_and_permission(user_id, perm_id)
                if not up:
                    raise AppException("E2023")
                up.is_active = perm_data.get("is_active", up.is_active)
                up.is_denied = perm_data.get("is_denied", up.is_denied)
                up.target_id = target_id
                await self._repo.save(up)
                updated.append({"permission": perm_name, "status": "updated"})

        return updated

    async def has_permission(
        self, user_id: int, permission_name: str, scope_ids: set[int]
    ) -> int:
        """Return -1 (denied), 0 (none), or 1 (granted).
        Trả về -1 (từ chối), 0 (không có), hoặc 1 (được cấp).

        scope_ids: tập target_id được coi là khớp. Quyền khớp-đúng-đối-tượng -> {target_id};
        quyền scope theo category -> chuỗi tổ tiên của category; truy vấn global -> tập rỗng.

        Deny-overrides: quét HẾT bản ghi áp dụng được; có deny đang active là -1, không thì xét
        allow; không thoát sớm theo bản ghi đầu tiên (tránh allow che deny tùy thứ tự DB).
        """
        async with self._transaction():
            ups = await self._repo.find_user_permission(user_id, permission_name)

        saw_allow = False
        for up in ups:
            if not up.is_active:
                continue
            # Record applies if it is global (target None) or its target is in scope
            # Bản ghi áp dụng nếu là global (target None) hoặc target nằm trong scope
            if up.target_id is None or up.target_id in scope_ids:
                if up.is_denied:
                    return -1
                saw_allow = True

        return 1 if saw_allow else 0

    async def delete_permissions(self, user_id: int, permissions: list[str]) -> None:
        """Delete named permissions from a user.
        Xoá các quyền theo tên khỏi user.
        """
        user = await self._user_svc.get_user_by_id(user_id)
        if not user:
            raise AppException("E1004")

        perm_ids: list[int] = []
        for perm_name in permissions:
            perm = await self._perm_svc.get_permission_by_name(perm_name)
            if perm:
                perm_ids.append(perm.id)

        async with self._transaction():
            for perm_id in perm_ids:
                up = await self._repo.find_by_user_and_permission(user_id, perm_id)
                if up:
                    await self._repo.delete(up)
