"""
PermissionRegistry - cache bảng permissions trong RAM (đọc là chính).

Bảng permissions ~57 dòng, gần như không đổi; mọi check_permission đều tra permission nên cache
trong RAM cắt được rất nhiều truy vấn DB.

Pure storage theo khuôn TrustCertificateResolver: chỉ GIỮ + INVALIDATE, KHÔNG tự truy vấn DB.
PermissionService chịu trách nhiệm nạp vào (gọi load) và kích hoạt nạp lại (gọi invalidate sau
khi create/update/delete permission).

An toàn detached: starter SQLAlchemy đặt expire_on_commit=False, và Permission chỉ có cột vô
hướng (không quan hệ lazy), nên giữ thẳng entity đã nạp là an toàn - đọc thuộc tính không cần session.

Một tiến trình, một event loop -> không cần khóa; mỗi lần đổi snapshot là dựng dict mới rồi gán
(thay nguyên tham chiếu, không sửa tại chỗ).
"""
from __future__ import annotations

from app.entity.permission import Permission


class PermissionRegistry:
    def __init__(self) -> None:
        # _by_name is None nghĩa là chưa nạp / đã invalidate (sentinel)
        # _by_name is None means not loaded / invalidated (sentinel)
        self._by_name: dict[str, Permission] | None = None
        self._by_id: dict[int, Permission] | None = None
        self._all: tuple[Permission, ...] = ()

    def is_loaded(self) -> bool:
        return self._by_name is not None

    def load(self, permissions: list[Permission]) -> None:
        """Replace the whole snapshot atomically (build new dicts, then assign).
        Thay toàn bộ snapshot một cách nguyên khối (dựng dict mới rồi gán)."""
        by_name = {p.name: p for p in permissions}
        by_id = {p.id: p for p in permissions}
        self._all = tuple(permissions)
        self._by_id = by_id
        # Gán _by_name cuối cùng vì nó là cờ is_loaded
        # Assign _by_name last since it is the is_loaded flag
        self._by_name = by_name

    def get_by_name(self, name: str) -> Permission | None:
        return (self._by_name or {}).get(name)

    def get_by_id(self, perm_id: int) -> Permission | None:
        return (self._by_id or {}).get(perm_id)

    def all(self) -> list[Permission]:
        return list(self._all)

    def names(self) -> list[str]:
        return [p.name for p in self._all]

    def invalidate(self) -> None:
        self._by_name = None
        self._by_id = None
        self._all = ()
