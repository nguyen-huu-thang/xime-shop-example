"""
Helper kẹp tham số phân trang.

Client có thể gửi page/limit tùy ý (kể cả 0 hoặc âm). Nếu tính thẳng
offset = (page-1)*limit sẽ ra offset ÂM -> PostgreSQL báo lỗi "OFFSET must not be
negative" (HTTP 500). limit quá lớn thì kéo cả bảng (rủi ro DoS). Helper này kẹp
page >= 1 và 1 <= limit <= MAX_PAGE_LIMIT, trả về (offset, limit) an toàn để dùng
trong mọi repository phân trang.

Module này KHÔNG nằm trong package được DI scan (chỉ chứa hàm thuần) nên không sinh
component thừa.
"""
from __future__ import annotations

# Trần số bản ghi mỗi trang (chặn limit khổng lồ gây nặng DB).
# Upper bound on page size (guards against a huge limit hammering the DB).
MAX_PAGE_LIMIT = 100


def paginate(page: int, limit: int) -> tuple[int, int]:
    """Clamp page/limit rồi trả (offset, limit) an toàn (offset không bao giờ âm).

    - page < 1 (hoặc None)      -> 1
    - limit < 1 (hoặc None)     -> 1
    - limit > MAX_PAGE_LIMIT    -> MAX_PAGE_LIMIT
    """
    if not page or page < 1:
        page = 1
    if not limit or limit < 1:
        limit = 1
    elif limit > MAX_PAGE_LIMIT:
        limit = MAX_PAGE_LIMIT
    return (page - 1) * limit, limit
