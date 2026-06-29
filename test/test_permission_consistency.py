"""
Phase 1 (kế hoạch nâng cấp phân quyền) - Test nhất quán quyền code <-> seed.

Mọi chuỗi quyền truyền vào require(...) / check_permission(...) trong controller PHẢI tồn tại
trong seed (app.seed.PERMISSIONS). Chống tái diễn bug "dùng quyền nhưng quên seed" (trước đây
thiếu view_files/delete_file -> endpoint luôn 403).

Kiểm tra TĨNH bằng AST - không cần DB, chạy nhanh.
Chi tiết: .claude/docs/phan-quyen-nang-cap.md (Phase 1).

Chạy: pytest test/test_permission_consistency.py -v
"""
from __future__ import annotations

import ast
from pathlib import Path

from app.seed import PERMISSIONS

# Thư mục controller + tên 2 method kiểm quyền (đối số thứ 2 là tên quyền)
# Controller dir + the two permission-check methods (arg index 1 is the permission name)
CONTROLLER_DIR = Path(__file__).resolve().parents[1] / "app" / "controller"
CHECK_METHODS = {"require", "check_permission"}


def _collect_permission_usages() -> tuple[dict[str, list[str]], list[str]]:
    """Quét controller, trả về (quyền dạng literal -> vị trí, các lời gọi tên quyền KHÔNG literal).

    Scan controllers; return (literal permission name -> locations, non-literal call locations).
    """
    used: dict[str, list[str]] = {}
    dynamic: list[str] = []
    for path in sorted(CONTROLLER_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if not isinstance(func, ast.Attribute) or func.attr not in CHECK_METHODS:
                continue
            loc = f"{path.name}:{node.lineno}"
            # Tên quyền là đối số vị trí thứ 2 (đối số 0 là user)
            # Permission name is positional arg #1 (arg #0 is the user)
            if len(node.args) >= 2:
                arg = node.args[1]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    used.setdefault(arg.value, []).append(loc)
                else:
                    dynamic.append(f"{loc} ({func.attr})")
    return used, dynamic


def test_all_controller_permissions_are_seeded() -> None:
    used, _ = _collect_permission_usages()
    assert used, "Không tìm thấy lời gọi require/check_permission nào - test có thể đã hỏng"

    seeded = set(PERMISSIONS)
    missing = {name: locs for name, locs in used.items() if name not in seeded}
    assert not missing, "Quyền dùng trong controller nhưng CHƯA seed:\n" + "\n".join(
        f"  - {name}  ({', '.join(locs)})" for name, locs in sorted(missing.items())
    )


def test_no_dynamic_permission_names_in_controllers() -> None:
    """Cảnh báo nếu có lời gọi require/check_permission với tên quyền không phải hằng chuỗi.

    Tên quyền động làm test nhất quán ở trên không soi được -> nên giữ literal. Nếu sau này cần
    động thật thì cập nhật cả test soi (và bỏ assert này).
    """
    _, dynamic = _collect_permission_usages()
    assert not dynamic, (
        "Có lời gọi kiểm quyền với tên quyền KHÔNG phải hằng chuỗi (test nhất quán không soi được):\n"
        + "\n".join(f"  - {loc}" for loc in dynamic)
    )
