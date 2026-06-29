from __future__ import annotations

from sqlalchemy import select

from app.entity.coupon import Coupon
from xime.starters.sqlalchemy import CrudRepository


class CouponRepository(CrudRepository[Coupon]):
    model = Coupon

    async def find_by_code(self, code: str) -> Coupon | None:
        result = await self.session.execute(
            select(Coupon).where(Coupon.code == code)
        )
        return result.scalar_one_or_none()
