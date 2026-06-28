"""
CouponService - quản lý mã giảm giá.
Port từ CouponService.php.
"""
from __future__ import annotations

from datetime import datetime, timezone

from xime.core.transaction.manager import TransactionManager

from app.entity.coupon import Coupon
from app.exception.app_exception import AppException
from app.repository.coupon_repository import CouponRepository


class CouponService:
    def __init__(
        self,
        transaction: TransactionManager,
        coupon_repository: CouponRepository,
    ) -> None:
        self._transaction = transaction
        self._repo = coupon_repository

    async def get_all_coupons(self) -> list[Coupon]:
        async with self._transaction():
            return await self._repo.find_all()

    async def get_coupon_by_id(self, coupon_id: int) -> Coupon | None:
        async with self._transaction():
            return await self._repo.find(coupon_id)

    async def get_coupon_by_code(self, code: str) -> Coupon | None:
        async with self._transaction():
            return await self._repo.find_by_code(code)

    async def create_coupon(self, data: dict) -> Coupon:
        code = data.get("code") or ""
        if not code:
            raise AppException("E10700")
        if data.get("discount") is None:
            raise AppException("E10700")

        async with self._transaction():
            coupon = Coupon(
                code=code,
                discount=data["discount"],
                start_date=datetime.fromisoformat(data.get("startDate", data.get("start_date", datetime.now(timezone.utc).isoformat()))),
                end_date=datetime.fromisoformat(data.get("endDate", data.get("end_date", datetime.now(timezone.utc).isoformat()))),
                is_active=data.get("isActive", data.get("is_active", True)),
            )
            return await self._repo.save(coupon)

    async def update_coupon(self, coupon_id: int, data: dict) -> Coupon:
        async with self._transaction():
            coupon = await self._repo.find(coupon_id)
        if not coupon:
            raise AppException("E10701")

        async with self._transaction():
            db = await self._repo.find(coupon_id)
            if not db:
                raise AppException("E10701")

            if data.get("code"):
                db.code = data["code"]
            if data.get("discount") is not None:
                db.discount = data["discount"]
            if data.get("startDate") or data.get("start_date"):
                raw = data.get("startDate") or data.get("start_date")
                db.start_date = datetime.fromisoformat(raw)
            if data.get("endDate") or data.get("end_date"):
                raw = data.get("endDate") or data.get("end_date")
                db.end_date = datetime.fromisoformat(raw)
            if "isActive" in data or "is_active" in data:
                db.is_active = data.get("isActive", data.get("is_active", db.is_active))
            return await self._repo.save(db)

    async def delete_coupon(self, coupon_id: int) -> None:
        async with self._transaction():
            coupon = await self._repo.find(coupon_id)
        if not coupon:
            raise AppException("E10701")
        async with self._transaction():
            db = await self._repo.find(coupon_id)
            if db:
                await self._repo.delete(db)
