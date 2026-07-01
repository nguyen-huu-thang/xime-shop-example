"""
Quy tắc tính tiền checkout (demo) - hàm thuần, không phụ thuộc DB nên dễ unit test.

Dùng Decimal cho tiền (tránh sai số float khi cộng dồn / tính %). Phí ship để dạng hằng số cấu
hình được; tọa độ KHÔNG dùng để tính phí (chỉ hiển thị bản đồ).
Xem [`.claude/docs/thiet-ke-checkout.md`](../../.claude/docs/thiet-ke-checkout.md).
"""
from __future__ import annotations

from decimal import Decimal

from app.money import money, quantize

# Phí ship phẳng mặc định (đồng)
# Flat default shipping fee (VND)
DEFAULT_SHIPPING_FEE = Decimal("30000")

# Miễn phí ship khi tiền hàng đạt ngưỡng này
# Free shipping when subtotal reaches this threshold
FREE_SHIP_THRESHOLD = Decimal("500000")


def shipping_fee(subtotal) -> Decimal:
    """Phí ship theo tiền hàng: miễn phí nếu đạt ngưỡng, ngược lại phí phẳng."""
    if money(subtotal) >= FREE_SHIP_THRESHOLD:
        return Decimal("0")
    return DEFAULT_SHIPPING_FEE


def order_total(
    subtotal,
    shipping_fee_amount,
    product_discount,
    ship_discount,
) -> Decimal:
    """Tổng tiền cuối: subtotal + phí ship - giảm tiền hàng - giảm phí ship (>= 0)."""
    total = (
        money(subtotal)
        + money(shipping_fee_amount)
        - money(product_discount)
        - money(ship_discount)
    )
    if total < 0:
        total = Decimal("0")
    return quantize(total)
