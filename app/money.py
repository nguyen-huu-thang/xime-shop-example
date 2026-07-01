"""
Helper tiền tệ dùng Decimal (tránh sai số nhị phân của float khi cộng dồn / tính %).

Dùng cho pipeline tính tiền checkout: pricing + coupon + order. Cột DB đã là Numeric(10,2) nên
gán Decimal vào entity là khớp kiểu (không qua float). DTO trả JSON vẫn để kiểu số (float) - convert
ở biên bằng float(...) khi cần.

Module này KHÔNG nằm trong package được DI scan (chỉ hàm thuần).
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

# Đơn vị làm tròn tiền: 2 chữ số thập phân.
# Money rounding unit: 2 decimal places.
_CENTS = Decimal("0.01")


def money(value) -> Decimal:
    """Ép giá trị về Decimal an toàn (nhận int/float/str/Decimal/None -> Decimal).

    Với float dùng str(value) trước để tránh lấy đúng biểu diễn nhị phân dài dòng
    (Decimal(0.1) != Decimal('0.1')).
    """
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    return Decimal(value)


def quantize(value) -> Decimal:
    """Làm tròn tiền về 2 chữ số thập phân (ROUND_HALF_UP)."""
    return money(value).quantize(_CENTS, rounding=ROUND_HALF_UP)
