"""
AuthorizationService — kiểm tra và enforce phân quyền.
Port từ AuthorizationService.php.
"""
from __future__ import annotations

from app.entity.user import User
from app.exception.app_exception import AppException
from app.service.group_member_service import GroupMemberService
from app.service.group_permission_service import GroupPermissionService
from app.service.permission_service import PermissionService
from app.service.user_permission_service import UserPermissionService


class AuthorizationService:
    def __init__(
        self,
        user_permission_service: UserPermissionService,
        group_member_service: GroupMemberService,
        group_permission_service: GroupPermissionService,
        permission_service: PermissionService,
    ) -> None:
        self._user_perm_svc = user_permission_service
        self._group_member_svc = group_member_service
        self._group_perm_svc = group_permission_service
        self._perm_svc = permission_service

    async def check_permission(
        self,
        user: User,
        permission_name: str,
        target_id: int | None = None,
        is_user_owned: bool = False,
    ) -> bool:
        """Full permission check: user perms → ownership → group perms → default.
        Kiểm tra toàn bộ: quyền user → ownership → quyền nhóm → giá trị mặc định.
        """
        # 1. User-level permission: -1 denied, 0 none, 1 granted
        # 1. Quyền cấp user: -1 từ chối, 0 không có, 1 cho phép
        user_perm = await self._user_perm_svc.has_permission(
            user.id, permission_name, target_id
        )
        if user_perm < 0:
            return False
        if user_perm > 0:
            return True

        # 2. Ownership shortcut (caller passes True when resource belongs to user)
        # 2. Shortcut ownership — caller truyền True khi tài nguyên thuộc về user
        if is_user_owned:
            return True

        # 3. Group permissions — PHP bug preserved: -1 (denied) is truthy → grants access
        # 3. Quyền nhóm — giữ nguyên PHP bug: -1 (từ chối) vẫn là truthy → cho phép
        groups = await self._group_member_svc.find_groups_by_user(user)
        for group in groups:
            gp = await self._group_perm_svc.has_permission(
                group.id, permission_name, target_id
            )
            if gp:  # non-zero: both 1 (granted) and -1 (denied) pass — PHP bug
                return True

        # 4. Permission default_value fallback
        # 4. Dùng giá trị mặc định của quyền làm fallback
        perm = await self._perm_svc.get_permission_by_name(permission_name)
        if perm:
            return perm.default_value
        return False

    async def require(
        self,
        user: User | None,
        permission_name: str,
        target_id: int | None = None,
        is_user_owned: bool = False,
    ) -> None:
        """Raise E2025 if not logged in, E2021 if not authorized.
        Ném E2025 nếu chưa đăng nhập, E2021 nếu không có quyền.
        """
        if user is None:
            raise AppException("E2025")
        if not await self.check_permission(user, permission_name, target_id, is_user_owned):
            raise AppException("E2021")
