"""
CategoryTreeCache - cache cấu trúc cây category trong RAM.

Phục vụ phân quyền theo nhánh (Phase 7/8): tính chuỗi tổ tiên (lúc check quyền sản phẩm) và mở
rộng con cháu (lúc lọc danh sách) bằng bộ nhớ thay vì truy vấn cây mỗi lần.

Pure storage theo khuôn TrustCertificateResolver: chỉ GIỮ + INVALIDATE, KHÔNG tự truy vấn DB.
CategoryService nạp vào (load) và kích hoạt nạp lại (invalidate sau create/update/delete category).

Một tiến trình, một event loop -> không cần khóa; mỗi lần đổi là dựng dict mới rồi gán.
"""
from __future__ import annotations

from collections.abc import Iterable


class CategoryTreeCache:
    def __init__(self) -> None:
        # _parent is None nghĩa là chưa nạp / đã invalidate (sentinel)
        # _parent is None means not loaded / invalidated (sentinel)
        self._parent: dict[int, int | None] | None = None
        self._children: dict[int, list[int]] = {}

    def is_loaded(self) -> bool:
        return self._parent is not None

    def load(self, rows: Iterable[tuple[int, int | None]]) -> None:
        """Build snapshot from (category_id, parent_id) rows, then assign atomically.
        Dựng snapshot từ các cặp (id, parent_id) rồi gán nguyên khối."""
        parent: dict[int, int | None] = {}
        children: dict[int, list[int]] = {}
        for cid, pid in rows:
            parent[cid] = pid
            children.setdefault(cid, [])
            if pid is not None:
                children.setdefault(pid, []).append(cid)
        self._children = children
        # Gán _parent cuối cùng vì nó là cờ is_loaded
        # Assign _parent last since it is the is_loaded flag
        self._parent = parent

    def ancestor_ids(self, category_id: int) -> list[int]:
        """Self + tổ tiên tới gốc: [category_id, parent, ..., root]. Phòng chu trình.
        Self + ancestors up to the root. Guards against cycles."""
        if self._parent is None or category_id not in self._parent:
            return []
        result: list[int] = []
        seen: set[int] = set()
        cur: int | None = category_id
        while cur is not None and cur in self._parent and cur not in seen:
            result.append(cur)
            seen.add(cur)
            cur = self._parent.get(cur)
        return result

    def descendant_ids(self, category_id: int) -> set[int]:
        """Self + toàn bộ con cháu. Self + all descendants."""
        if self._parent is None or category_id not in self._parent:
            return set()
        result: set[int] = set()
        stack: list[int] = [category_id]
        while stack:
            cur = stack.pop()
            if cur in result:
                continue
            result.add(cur)
            stack.extend(self._children.get(cur, []))
        return result

    def all_ids(self) -> set[int]:
        """Tất cả category id đang có. All category ids currently loaded."""
        if self._parent is None:
            return set()
        return set(self._parent.keys())

    def invalidate(self) -> None:
        self._parent = None
        self._children = {}
