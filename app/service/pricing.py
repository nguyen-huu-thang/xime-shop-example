"""
Quy tắc tính tiền checkout (demo) - hàm thuần, không phụ thuộc DB nên dễ unit test.

Phí ship để dạng hằng số cấu hình được; tọa độ KHÔNG dùng để tính phí (chỉ hiển thị bản đồ).
Xem [`.claude/docs/thiet-ke-checkout.md`](../../.claude/docs/thiet-ke-checkout.md).
"""
from __future__ import annotations

# Phí ship phẳng mặc định (đồng)
# Flat default shipping fee (VND)
DEFAULT_SHIPPING_FEE = 30000.0

# Miễn phí ship khi tiền hàng đạt ngưỡng này
# Free shipping when subtotal reaches this threshold
FREE_SHIP_THRESHOLD = 500000.0


def shipping_fee(subtotal: float) -> float:
    """Phí ship theo tiền hàng: miễn phí nếu đạt ngưỡng, ngược lại phí phẳng."""
    if subtotal >= FREE_SHIP_THRESHOLD:
        return 0.0
    return DEFAULT_SHIPPING_FEE


def order_total(
    subtotal: float,
    shipping_fee_amount: float,
    product_discount: float,
    ship_discount: float,
) -> float:
    """Tổng tiền cuối: subtotal + phí ship - giảm tiền hàng - giảm phí ship (>= 0)."""
    total = subtotal + shipping_fee_amount - product_discount - ship_discount
    return round(max(total, 0.0), 2)
