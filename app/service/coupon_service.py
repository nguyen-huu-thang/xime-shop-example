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

    @staticmethod
    def _parse_date(raw: str) -> datetime:
        """Parse an ISO date string; invalid format -> clean 4xx instead of an
        unhandled ValueError (500).
        Parse chuỗi ngày ISO; sai định dạng -> lỗi 4xx sạch thay vì ValueError (500).
        """
        try:
            return datetime.fromisoformat(raw)
        except (ValueError, TypeError):
            raise AppException("E10402", "Ngày không đúng định dạng ISO")

    async def create_coupon(self, data: dict) -> Coupon:
        code = data.get("code") or ""
        if not code:
            raise AppException("E10402", "Mã giảm giá là bắt buộc")
        if data.get("discount") is None:
            raise AppException("E10402", "Giá trị giảm là bắt buộc")

        now_iso = datetime.now(timezone.utc).isoformat()
        start_date = self._parse_date(data.get("startDate") or data.get("start_date") or now_iso)
        end_date = self._parse_date(data.get("endDate") or data.get("end_date") or now_iso)

        async with self._transaction():
            # Reject duplicate code up-front -> clean 4xx instead of leaking the DB
            # UniqueViolation as a 500 (coupons.code has a UNIQUE constraint).
            # Chặn trùng code -> lỗi 4xx sạch thay vì để IntegrityError thành 500.
            if await self._repo.find_by_code(code):
                raise AppException("E10402", "Mã giảm giá đã tồn tại")
            coupon = Coupon(
                code=code,
                discount=data["discount"],
                start_date=start_date,
                end_date=end_date,
                is_active=data.get("isActive", data.get("is_active", True)),
            )
            return await self._repo.save(coupon)

    async def update_coupon(self, coupon_id: int, data: dict) -> Coupon:
        # Single transaction: read + modify together (no double-fetch).
        # Một transaction: đọc + sửa cùng nhau (không double-fetch).
        async with self._transaction():
            db = await self._repo.find(coupon_id)
            if not db:
                raise AppException("E10400")

            if data.get("code"):
                db.code = data["code"]
            if data.get("discount") is not None:
                db.discount = data["discount"]
            if data.get("startDate") or data.get("start_date"):
                db.start_date = self._parse_date(data.get("startDate") or data.get("start_date"))
            if data.get("endDate") or data.get("end_date"):
                db.end_date = self._parse_date(data.get("endDate") or data.get("end_date"))
            if "isActive" in data or "is_active" in data:
                db.is_active = data.get("isActive", data.get("is_active", db.is_active))
            return await self._repo.save(db)

    async def delete_coupon(self, coupon_id: int) -> None:
        async with self._transaction():
            db = await self._repo.find(coupon_id)
            if not db:
                raise AppException("E10400")
            await self._repo.delete(db)
