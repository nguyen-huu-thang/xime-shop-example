"""
Điểm khai báo cấu hình của app - `main.py` chỉ vào đây bằng `app.add_config(config)`.

⭐ Khai tường minh chứ không để framework đi dò, vì đó là ĐIỀU KIỆN CẦN cho đa tiến trình:
cơ chế dò cũ tìm package config qua `__main__.__spec__.parent`, mà giá trị đó KHÁC ở tiến
trình con - framework tìm sai chỗ rồi im lặng rơi xuống một DI rỗng. Tiến trình con vẫn khởi
động, không route nào, và không gì báo.

Thứ tự dưới đây là thứ tự chạy.

Explicit config wiring; required for multi-process (the old discovery breaks in child processes).
"""
from app.config import scheduler, web  # noqa: F401 - side effect: configure_* lúc import
from app.config.dependency import dependency

__all__ = ["dependency"]
