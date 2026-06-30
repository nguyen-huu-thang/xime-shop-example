"""
ActionRegistry - cache bảng actions trong RAM (đọc là chính).

Bảng actions chỉ vài dòng (loại hành động + trọng số điểm), gần như không đổi nhưng được tra rất
nhiều khi ghi interaction / tính điểm cá nhân hóa -> cache RAM cắt được mọi truy vấn lặp.

Pure storage theo khuôn PermissionRegistry / TrustCertificateResolver: chỉ GIỮ + INVALIDATE,
KHÔNG tự truy vấn DB. ActionService chịu trách nhiệm nạp (gọi load) và nạp lại (gọi invalidate).

An toàn detached: starter SQLAlchemy đặt expire_on_commit=False, Action chỉ có cột vô hướng
(không quan hệ lazy) nên giữ thẳng entity đã nạp là an toàn - đọc thuộc tính không cần session.
"""
from __future__ import annotations

from app.entity.action import Action


class ActionRegistry:
    def __init__(self) -> None:
        # _by_name is None nghĩa là chưa nạp / đã invalidate (sentinel)
        # _by_name is None means not loaded / invalidated (sentinel)
        self._by_name: dict[str, Action] | None = None
        self._by_id: dict[int, Action] | None = None
        self._all: tuple[Action, ...] = ()

    def is_loaded(self) -> bool:
        return self._by_name is not None

    def load(self, actions: list[Action]) -> None:
        """Replace the whole snapshot atomically (build new dicts, then assign).
        Thay toàn bộ snapshot một cách nguyên khối (dựng dict mới rồi gán)."""
        by_name = {a.name: a for a in actions}
        by_id = {a.id: a for a in actions}
        self._all = tuple(actions)
        self._by_id = by_id
        # Gán _by_name cuối cùng vì nó là cờ is_loaded
        # Assign _by_name last since it is the is_loaded flag
        self._by_name = by_name

    def get_by_name(self, name: str) -> Action | None:
        return (self._by_name or {}).get(name)

    def get_by_id(self, action_id: int) -> Action | None:
        return (self._by_id or {}).get(action_id)

    def all(self) -> list[Action]:
        return list(self._all)

    def invalidate(self) -> None:
        self._by_name = None
        self._by_id = None
        self._all = ()
