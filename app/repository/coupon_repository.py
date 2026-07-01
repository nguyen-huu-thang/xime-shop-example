from __future__ import annotations

from sqlalchemy import select

from app.entity.coupon import Coupon
from xime.starters.sqlalchemy import CrudRepository


class CouponRepository(CrudRepository[Coupon]):
    model = Coupon

    async def find_by_code(self, code: str, for_update: bool = False) -> Coupon | None:
        # for_update=True: khóa dòng coupon để tăng used_count an toàn khi đặt đơn đồng thời
        # (chống vượt usage_limit / dùng lại per_user_once do race).
        # for_update=True: row-lock the coupon so used_count increments atomically.
        stmt = select(Coupon).where(Coupon.code == code)
        if for_update:
            stmt = stmt.with_for_update()
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def find_for_update(self, coupon_id: int) -> Coupon | None:
        # Khóa dòng coupon theo id (dùng lúc xác nhận thanh toán online để tăng used_count).
        # Row-lock a coupon by id (used at online payment confirmation to bump used_count).
        result = await self.session.execute(
            select(Coupon).where(Coupon.id == coupon_id).with_for_update()
        )
        return result.scalar_one_or_none()
