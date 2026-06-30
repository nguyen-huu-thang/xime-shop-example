from __future__ import annotations

from dataclasses import dataclass

from app.entity.coupon import Coupon


@dataclass(frozen=True)
class CouponApplication:
    """Kết quả áp coupon: mã + số tiền giảm phân bổ vào tiền hàng / phí ship.

    Đặt trong app/dto (không nằm trong package được DI quét) để scanner không coi đây là
    một service cần inject `Coupon`.
    """

    coupon: Coupon
    product_discount: float
    ship_discount: float
