"""
Test cho các phase nâng cấp phân quyền (.claude/docs/phan-quyen-nang-cap.md).
Gom dần test theo từng phase.

Chạy: pytest test/test_authz_upgrade.py -v
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.cache.category_tree_cache import CategoryTreeCache
from app.cache.permission_registry import PermissionRegistry
from app.entity.permission import Permission
from app.exception.app_exception import AppException
from app.service.authorization_service import AuthorizationService


class _FakeUser:
    """User giả tối thiểu - chỉ cần thuộc tính dùng trong short-circuit."""

    def __init__(self, *, is_superadmin: bool) -> None:
        self.id = 999
        self.is_superadmin = is_superadmin


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2 - Superadmin bypass
# ─────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_superadmin_bypasses_check_without_touching_dependencies():
    # Superadmin trả True ngay, trước khi đụng tới bất kỳ service phụ thuộc nào
    # -> dựng với deps None vẫn chạy được, chứng minh short-circuit đứng đầu.
    authz = AuthorizationService(None, None, None, None, None)  # type: ignore[arg-type]
    user = _FakeUser(is_superadmin=True)

    assert await authz.check_permission(user, "any_nonexistent_permission") is True
    # require cũng phải đi qua mà không raise
    await authz.require(user, "any_nonexistent_permission")


@pytest.mark.asyncio
async def test_non_superadmin_does_not_short_circuit():
    # User thường KHÔNG được short-circuit: với deps None, check sẽ cố gọi service
    # phụ thuộc -> AttributeError. Đây là bằng chứng nhánh superadmin không kích hoạt nhầm.
    authz = AuthorizationService(None, None, None, None, None)  # type: ignore[arg-type]
    user = _FakeUser(is_superadmin=False)

    with pytest.raises(AttributeError):
        await authz.check_permission(user, "view_products")


# ─────────────────────────────────────────────────────────────────────────────
# Phase 3 - PermissionRegistry (pure storage, không cần DB)
# ─────────────────────────────────────────────────────────────────────────────


def test_permission_registry_load_get_and_invalidate():
    reg = PermissionRegistry()
    assert reg.is_loaded() is False
    assert reg.get_by_name("view_products") is None  # an toàn khi chưa nạp

    perms = [
        Permission(id=1, name="view_products", description="x", default_value=False),
        Permission(id=2, name="edit_product", description="y", default_value=True),
    ]
    reg.load(perms)

    assert reg.is_loaded() is True
    assert reg.get_by_name("edit_product").id == 2
    assert reg.get_by_id(1).name == "view_products"
    assert set(reg.names()) == {"view_products", "edit_product"}
    assert len(reg.all()) == 2

    reg.invalidate()
    assert reg.is_loaded() is False
    assert reg.get_by_name("view_products") is None
    assert reg.names() == []


# ─────────────────────────────────────────────────────────────────────────────
# Phase 4 - get_effective_permissions: helper _is_effective (deny-overrides, target=None)
# ─────────────────────────────────────────────────────────────────────────────


def _grant(permission_id, *, is_denied=False, is_active=True, target_id=None):
    return SimpleNamespace(
        permission_id=permission_id,
        is_denied=is_denied,
        is_active=is_active,
        target_id=target_id,
    )


_is_effective = AuthorizationService._is_effective


def test_is_effective_user_allow():
    assert _is_effective(1, False, [_grant(1)], []) is True


def test_is_effective_user_deny_overrides_user_allow():
    # Có cả allow lẫn deny ở cấp user -> deny thắng
    assert _is_effective(1, False, [_grant(1), _grant(1, is_denied=True)], []) is False


def test_is_effective_group_allow_when_no_user_record():
    assert _is_effective(1, False, [], [_grant(1)]) is True


def test_is_effective_group_deny_overrides_other_group_allow():
    # Một nhóm cấp, một nhóm deny -> deny thắng (deny-overrides trên tất cả nhóm)
    assert _is_effective(1, False, [], [_grant(1), _grant(1, is_denied=True)]) is False


def test_is_effective_user_allow_overrides_group_deny():
    # Ưu tiên cấp: user cấp -> True bất kể nhóm deny
    assert _is_effective(1, False, [_grant(1)], [_grant(1, is_denied=True)]) is True


def test_is_effective_falls_back_to_default():
    assert _is_effective(1, True, [], []) is True
    assert _is_effective(1, False, [], []) is False


def test_is_effective_ignores_inactive_and_targeted_records():
    # Bản ghi inactive hoặc gắn target cụ thể -> bỏ qua khi xét quyền không-target
    assert _is_effective(1, False, [_grant(1, is_active=False)], []) is False
    assert _is_effective(1, False, [_grant(1, target_id=5)], []) is False
    # Quyền khác id -> không tính
    assert _is_effective(1, False, [_grant(2)], [_grant(3)]) is False


# ─────────────────────────────────────────────────────────────────────────────
# Phase 5 - ownership helper (require_owner_or_permission)
# ─────────────────────────────────────────────────────────────────────────────


def test_is_owner():
    user = SimpleNamespace(id=7)
    assert AuthorizationService._is_owner(user, SimpleNamespace(user_id=7)) is True
    assert AuthorizationService._is_owner(user, SimpleNamespace(user_id=9)) is False
    # Tài nguyên không có user_id -> không sở hữu
    assert AuthorizationService._is_owner(user, SimpleNamespace()) is False


@pytest.mark.asyncio
async def test_require_owner_or_permission_owner_passes_without_deps():
    # Chủ sở hữu đi qua trước khi đụng tới check_permission -> deps None vẫn chạy.
    authz = AuthorizationService(None, None, None, None, None)  # type: ignore[arg-type]
    user = SimpleNamespace(id=7, is_superadmin=False)
    await authz.require_owner_or_permission(user, "view_orders", SimpleNamespace(user_id=7))


@pytest.mark.asyncio
async def test_require_owner_or_permission_non_owner_superadmin_passes():
    # Không sở hữu nhưng superadmin -> check_permission short-circuit True, qua được.
    authz = AuthorizationService(None, None, None, None, None)  # type: ignore[arg-type]
    user = SimpleNamespace(id=7, is_superadmin=True)
    await authz.require_owner_or_permission(user, "view_orders", SimpleNamespace(user_id=99))


@pytest.mark.asyncio
async def test_require_owner_or_permission_anonymous_raises_e2025():
    authz = AuthorizationService(None, None, None, None, None)  # type: ignore[arg-type]
    with pytest.raises(AppException) as ei:
        await authz.require_owner_or_permission(None, "view_orders", SimpleNamespace(user_id=7))
    assert ei.value.error_key == "E2025"


# ─────────────────────────────────────────────────────────────────────────────
# Phase 6 - CategoryTreeCache (pure storage, không cần DB)
#   Cây mẫu:  1 (root) -> {2 -> {4}, 3}
# ─────────────────────────────────────────────────────────────────────────────


def _sample_tree() -> CategoryTreeCache:
    cache = CategoryTreeCache()
    cache.load([(1, None), (2, 1), (3, 1), (4, 2)])
    return cache


def test_category_tree_ancestor_ids():
    cache = _sample_tree()
    assert cache.ancestor_ids(4) == [4, 2, 1]
    assert cache.ancestor_ids(2) == [2, 1]
    assert cache.ancestor_ids(1) == [1]
    assert cache.ancestor_ids(99) == []  # id không tồn tại


def test_category_tree_descendant_ids():
    cache = _sample_tree()
    assert cache.descendant_ids(1) == {1, 2, 3, 4}
    assert cache.descendant_ids(2) == {2, 4}
    assert cache.descendant_ids(3) == {3}
    assert cache.descendant_ids(99) == set()


def test_category_tree_invalidate():
    cache = _sample_tree()
    assert cache.is_loaded() is True
    cache.invalidate()
    assert cache.is_loaded() is False
    assert cache.ancestor_ids(4) == []
    assert cache.descendant_ids(1) == set()


# ─────────────────────────────────────────────────────────────────────────────
# Phase 7 - giải scope_ids theo scope_type (resolve resource/target -> tập)
# ─────────────────────────────────────────────────────────────────────────────


class _FakeCatSvc:
    def __init__(self, ancestors: list[int]) -> None:
        self._ancestors = ancestors

    async def get_ancestor_ids(self, category_id: int) -> list[int]:
        return self._ancestors


def test_resolve_category_id():
    rc = AuthorizationService._resolve_category_id
    # resource có category_id (vd Product) -> dùng nó
    assert rc(SimpleNamespace(category_id=5), None) == 5
    # resource không có category_id (vd Category) -> dùng id của nó
    assert rc(SimpleNamespace(id=9), None) == 9
    # không có resource -> target_id (truyền thẳng là category id)
    assert rc(None, 3) == 3
    assert rc(None, None) is None


@pytest.mark.asyncio
async def test_resolve_scope_ids_non_scoped_is_exact_match():
    # Quyền thường (scope_type None hoặc perm None) -> khớp đúng {target_id}, global -> rỗng
    authz = AuthorizationService(None, None, None, None, None)  # type: ignore[arg-type]
    perm = SimpleNamespace(scope_type=None)
    assert await authz._resolve_scope_ids(perm, 7, None) == {7}
    assert await authz._resolve_scope_ids(perm, None, None) == set()
    assert await authz._resolve_scope_ids(None, 7, None) == {7}


@pytest.mark.asyncio
async def test_resolve_scope_ids_category_uses_ancestor_chain():
    # Quyền scope category -> tập = chuỗi tổ tiên của category resource
    authz = AuthorizationService(None, None, None, None, _FakeCatSvc([5, 3, 1]))  # type: ignore[arg-type]
    perm = SimpleNamespace(scope_type="category")
    ids = await authz._resolve_scope_ids(perm, None, SimpleNamespace(category_id=5))
    assert ids == {5, 3, 1}


@pytest.mark.asyncio
async def test_resolve_scope_ids_category_no_category_returns_empty():
    authz = AuthorizationService(None, None, None, None, _FakeCatSvc([5]))  # type: ignore[arg-type]
    perm = SimpleNamespace(scope_type="category")
    # resource None + target None -> không xác định được category -> rỗng (không khớp target nào)
    assert await authz._resolve_scope_ids(perm, None, None) == set()


# ─────────────────────────────────────────────────────────────────────────────
# Phase 8 - _decide_in_memory (deny subtree chính xác) + allowed_category_scope
# ─────────────────────────────────────────────────────────────────────────────


def test_decide_in_memory_precise_subtree_deny():
    decide = AuthorizationService._decide_in_memory
    # Cấp ở P(10), deny ở C(20). scope_ids mô phỏng chuỗi tổ tiên của từng category.
    grants = [_grant(1, target_id=10), _grant(1, is_denied=True, target_id=20)]
    assert decide(1, False, grants, [], {10}) is True            # P: được phép
    assert decide(1, False, grants, [], {20, 10}) is False        # C (con P, bị deny): chặn
    assert decide(1, False, grants, [], {30, 20, 10}) is False    # cháu của C: chặn
    assert decide(1, False, grants, [], {40}) is False            # nhánh khác: default False


def test_decide_in_memory_global_allow_covers_all():
    decide = AuthorizationService._decide_in_memory
    assert decide(1, False, [_grant(1)], [], set()) is True       # grant global (target None)
    assert decide(1, False, [_grant(1)], [], {99}) is True


class _FakePermSvc:
    def __init__(self, perm):
        self._p = perm

    async def get_permission_by_name(self, name):
        return self._p


class _FakeGroupMemberSvc:
    async def find_groups_by_user(self, user):
        return []


class _FakeUserPermSvc:
    def __init__(self, ups):
        self._ups = ups

    async def get_permissions_by_user_id(self, uid):
        return self._ups


class _FakeGroupPermSvc:
    async def get_records_by_group_ids(self, ids):
        return []


class _FakeCatSvcTree:
    def __init__(self, tree: CategoryTreeCache):
        self._t = tree

    async def get_all_category_ids(self):
        return self._t.all_ids()

    async def get_ancestor_ids(self, cid):
        return self._t.ancestor_ids(cid)


@pytest.mark.asyncio
async def test_allowed_category_scope_subtree_minus_deny():
    # Cây: 10 -> {20 -> {30}}, nhánh khác 40. Cấp ở 10, deny ở 20.
    tree = CategoryTreeCache()
    tree.load([(10, None), (20, 10), (30, 20), (40, None)])
    perm = SimpleNamespace(id=1, default_value=False, scope_type="category")
    user_perms = [_grant(1, target_id=10), _grant(1, is_denied=True, target_id=20)]
    authz = AuthorizationService(
        _FakeUserPermSvc(user_perms),
        _FakeGroupMemberSvc(),
        _FakeGroupPermSvc(),
        _FakePermSvc(perm),
        _FakeCatSvcTree(tree),
    )  # type: ignore[arg-type]
    user = SimpleNamespace(id=7, is_superadmin=False)

    allowed = await authz.allowed_category_scope(user, "view_products")
    # 10 cho phép; 20 + 30 (subtree của 20) bị deny; 40 nhánh khác -> default False
    assert allowed == {10}


@pytest.mark.asyncio
async def test_allowed_category_scope_superadmin_returns_none():
    authz = AuthorizationService(None, None, None, None, None)  # type: ignore[arg-type]
    user = SimpleNamespace(is_superadmin=True)
    assert await authz.allowed_category_scope(user, "view_products") is None
