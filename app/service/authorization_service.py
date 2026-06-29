"""
AuthorizationService - kiểm tra và enforce phân quyền.
Port từ AuthorizationService.php.
"""
from __future__ import annotations

from app.entity.user import User
from app.exception.app_exception import AppException
from app.service.category_service import CategoryService
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
        category_service: CategoryService,
    ) -> None:
        self._user_perm_svc = user_permission_service
        self._group_member_svc = group_member_service
        self._group_perm_svc = group_permission_service
        self._perm_svc = permission_service
        self._category_svc = category_service

    async def check_permission(
        self,
        user: User,
        permission_name: str,
        target_id: int | None = None,
        is_user_owned: bool = False,
        resource: object | None = None,
    ) -> bool:
        """Full permission check: superadmin → user perms → ownership → group perms → default.
        Kiểm tra toàn bộ: superadmin → quyền user → ownership → quyền nhóm → giá trị mặc định.

        resource: đối tượng đang thao tác (vd Product) để giải scope theo category cho quyền
        scope_type='category'. target_id: với quyền thường là id đối tượng khớp đúng; với quyền
        category-scope là category id (khi không truyền resource).
        """
        # 0. Superadmin bypasses every check (trusted owner / initial admin)
        # 0. Superadmin vượt qua mọi kiểm tra (chủ hệ thống tin cậy / admin khởi tạo)
        if getattr(user, "is_superadmin", False):
            return True

        # Resolve permission once (cần scope_type + default_value); rồi dựng tập scope.
        # Resolve the permission once (need scope_type + default_value); then build the scope set.
        perm = await self._perm_svc.get_permission_by_name(permission_name)
        scope_ids = await self._resolve_scope_ids(perm, target_id, resource)

        # 1. User-level permission: -1 denied, 0 none, 1 granted
        # 1. Quyền cấp user: -1 từ chối, 0 không có, 1 cho phép
        user_perm = await self._user_perm_svc.has_permission(
            user.id, permission_name, scope_ids
        )
        if user_perm < 0:
            return False
        if user_perm > 0:
            return True

        # 2. Ownership shortcut (caller passes True when resource belongs to user)
        # 2. Shortcut ownership - caller truyền True khi tài nguyên thuộc về user
        if is_user_owned:
            return True

        # 3. Group permissions (deny-overrides across ALL groups): any group deny
        #    blocks immediately; only grant if at least one group grants and none denies.
        # 3. Quyền nhóm (deny thắng trên TẤT CẢ nhóm): bất kỳ nhóm nào deny là chặn ngay;
        #    chỉ cho phép nếu có ít nhất một nhóm cấp và không nhóm nào deny.
        groups = await self._group_member_svc.find_groups_by_user(user)
        saw_group_allow = False
        for group in groups:
            gp = await self._group_perm_svc.has_permission(
                group.id, permission_name, scope_ids
            )
            if gp < 0:
                return False
            if gp > 0:
                saw_group_allow = True
        if saw_group_allow:
            return True

        # 4. Permission default_value fallback (dùng lại perm đã resolve ở trên)
        # 4. Dùng giá trị mặc định của quyền làm fallback
        if perm:
            return perm.default_value
        return False

    async def _resolve_scope_ids(
        self, perm, target_id: int | None, resource: object | None
    ) -> set[int]:
        """Build the set of target ids that count as a match for this check.
        Dựng tập target_id được coi là khớp cho lần kiểm tra này.

        - Quyền scope_type='category': chuỗi tổ tiên của category liên quan (từ resource hoặc
          target_id) - cấp ở category cha áp cho cả nhánh con.
        - Quyền thường: khớp đúng đối tượng {target_id}, hoặc rỗng nếu truy vấn global.
        """
        if perm is not None and perm.scope_type == "category":
            category_id = self._resolve_category_id(resource, target_id)
            if category_id is None:
                return set()
            return set(await self._category_svc.get_ancestor_ids(category_id))
        return {target_id} if target_id is not None else set()

    @staticmethod
    def _resolve_category_id(resource: object | None, target_id: int | None) -> int | None:
        """Xác định category để xét scope: ưu tiên resource (product.category_id hoặc category.id),
        sau đó target_id (được truyền thẳng là category id)."""
        if resource is not None:
            cat = getattr(resource, "category_id", None)
            if cat is not None:
                return cat
            return getattr(resource, "id", None)
        return target_id

    async def get_effective_permissions(self, user: User) -> list[str]:
        """Return permission names the user effectively has (for FE menu gating).
        Trả về tên các quyền mà user thực sự có (để FE ẩn/hiện menu admin).

        Nạp MỘT lần (quyền + nhóm + grant user + grant nhóm) rồi đánh giá tất cả quyền trong
        bộ nhớ - bỏ N+1 của bản cũ (trước đây gọi check_permission cho từng quyền, mỗi lần lại
        truy vấn nhóm + grant). Ngữ nghĩa giữ y hệt check_permission với target=None,
        is_user_owned=False (deny-overrides theo cấp, ưu tiên user > group).
        """
        # Superadmin có mọi quyền
        # Superadmin has every permission
        if getattr(user, "is_superadmin", False):
            return await self._perm_svc.get_permission_names()

        all_perms = await self._perm_svc.get_all_permissions()
        groups = await self._group_member_svc.find_groups_by_user(user)
        group_ids = [g.id for g in groups]
        user_perms = await self._user_perm_svc.get_permissions_by_user_id(user.id)
        group_perms = await self._group_perm_svc.get_records_by_group_ids(group_ids)

        granted: list[str] = []
        for perm in all_perms:
            if self._is_effective(perm.id, perm.default_value, user_perms, group_perms):
                granted.append(perm.name)
        return granted

    @staticmethod
    def _decide_in_memory(
        perm_id: int | None,
        default_value: bool,
        user_perms: list,
        group_perms: list,
        scope_ids: set[int],
    ) -> bool:
        """In-memory permission decision mirroring check_permission (deny-overrides, user > group).
        Quyết định trong bộ nhớ phản chiếu check_permission (deny thắng theo cấp, ưu tiên user > group).

        Bản ghi "áp dụng" = target_id is None HOẶC target_id in scope_ids. Cho target=None thì
        scope_ids rỗng (chỉ grant global). Cho category thì scope_ids là chuỗi tổ tiên của category
        đang xét - nhờ đó deny ở một nhánh con chỉ chặn đúng nhánh đó (chính xác).
        """
        # 1. User level: deny thắng, có allow -> cho (ưu tiên trên group)
        user_allow = False
        for up in user_perms:
            if up.permission_id != perm_id or not up.is_active:
                continue
            if up.target_id is None or up.target_id in scope_ids:
                if up.is_denied:
                    return False
                user_allow = True
        if user_allow:
            return True

        # 2. Group level: bất kỳ nhóm nào deny -> chặn; có nhóm cấp -> cho
        saw_group_allow = False
        for gp in group_perms:
            if gp.permission_id != perm_id or not gp.is_active:
                continue
            if gp.target_id is None or gp.target_id in scope_ids:
                if gp.is_denied:
                    return False
                saw_group_allow = True
        if saw_group_allow:
            return True

        # 3. Mặc định của permission
        return default_value

    @classmethod
    def _is_effective(
        cls, perm_id: int, default_value: bool, user_perms: list, group_perms: list
    ) -> bool:
        """Quyền hiệu lực không gắn target (chỉ xét grant global) = _decide_in_memory với scope rỗng."""
        return cls._decide_in_memory(perm_id, default_value, user_perms, group_perms, set())

    async def allowed_category_scope(
        self, user: User, permission_name: str
    ) -> set[int] | None:
        """Tập category id user được phép thao tác với quyền này; None = TẤT CẢ (không lọc).

        Dùng để lọc danh sách theo nhánh nhân viên phụ trách. Mỗi category xét bằng cùng logic
        check_permission (deny subtree chính xác nhờ scope_ids = chuỗi tổ tiên của category đó).
        """
        # Superadmin / global-allow -> không lọc
        if getattr(user, "is_superadmin", False):
            return None

        perm = await self._perm_svc.get_permission_by_name(permission_name)
        perm_id = perm.id if perm else None
        default_value = perm.default_value if perm else False

        groups = await self._group_member_svc.find_groups_by_user(user)
        group_ids = [g.id for g in groups]
        user_perms = await self._user_perm_svc.get_permissions_by_user_id(user.id)
        group_perms = await self._group_perm_svc.get_records_by_group_ids(group_ids)

        all_ids = await self._category_svc.get_all_category_ids()
        allowed: set[int] = set()
        for cid in all_ids:
            scope_ids = set(await self._category_svc.get_ancestor_ids(cid))
            if self._decide_in_memory(
                perm_id, default_value, user_perms, group_perms, scope_ids
            ):
                allowed.add(cid)
        return allowed

    async def require(
        self,
        user: User | None,
        permission_name: str,
        target_id: int | None = None,
        is_user_owned: bool = False,
        resource: object | None = None,
    ) -> None:
        """Raise E2025 if not logged in, E2021 if not authorized.
        Ném E2025 nếu chưa đăng nhập, E2021 nếu không có quyền.

        resource: chuyển tiếp cho check_permission để giải scope theo category (quyền sản phẩm).
        """
        if user is None:
            raise AppException("E2025")
        if not await self.check_permission(
            user, permission_name, target_id, is_user_owned, resource
        ):
            raise AppException("E2021")

    @staticmethod
    def _is_owner(user: User, resource: object) -> bool:
        """True if the resource belongs to the user (resource.user_id == user.id).
        Đúng nếu tài nguyên thuộc về user (resource.user_id == user.id).

        Dùng cho tài nguyên của người mua (giỏ hàng, wishlist, đơn hàng). Tài nguyên không có
        cột user_id -> coi như không sở hữu (trả False).
        """
        owner_id = getattr(resource, "user_id", None)
        return owner_id is not None and owner_id == user.id

    async def require_owner_or_permission(
        self,
        user: User | None,
        permission_name: str,
        resource: object,
        target_id: int | None = None,
    ) -> None:
        """Allow if the user owns the resource, otherwise require the permission.
        Cho phép nếu user sở hữu tài nguyên; nếu không thì yêu cầu quyền (ném E2021).

        Gom logic ownership rải rác ở controller về một chỗ. Chủ sở hữu luôn truy cập được tài
        nguyên của mình; người khác phải có quyền tương ứng (vd nhân viên có view_orders).
        Ném E2025 nếu chưa đăng nhập.
        """
        if user is None:
            raise AppException("E2025")
        if self._is_owner(user, resource):
            return
        if not await self.check_permission(user, permission_name, target_id):
            raise AppException("E2021")
