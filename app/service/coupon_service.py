"""
CouponService - quản lý mã giảm giá.
Port từ CouponService.php + nâng cấp cho checkout (loại %/số tiền, đơn tối thiểu,
scope SP/ship, giới hạn lượt dùng, mỗi-user-một-lần).
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from xime.core.transaction.manager import TransactionManager

from app.dto.coupon_application import CouponApplication
from app.utils.money import money, quantize
from app.entity.coupon import Coupon
from app.exception.app_exception import AppException
from app.repository.coupon_repository import CouponRepository
from app.repository.order_repository import OrderRepository


class CouponService:
    def __init__(
        self,
        transaction: TransactionManager,
        coupon_repository: CouponRepository,
        order_repository: OrderRepository,
    ) -> None:
        self._transaction = transaction
        self._repo = coupon_repository
        self._order_repo = order_repository

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
                discount_type=data.get("discount_type", "fixed"),
                max_discount=data.get("max_discount"),
                min_order_amount=data.get("min_order_amount", 0),
                applies_to=data.get("applies_to", "product"),
                usage_limit=data.get("usage_limit"),
                per_user_once=data.get("per_user_once", False),
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
            # Field nâng cấp (chỉ cập nhật khi gửi - controller dùng exclude_unset)
            if "discount_type" in data and data["discount_type"] is not None:
                db.discount_type = data["discount_type"]
            if "max_discount" in data:
                db.max_discount = data["max_discount"]
            if "min_order_amount" in data and data["min_order_amount"] is not None:
                db.min_order_amount = data["min_order_amount"]
            if "applies_to" in data and data["applies_to"] is not None:
                db.applies_to = data["applies_to"]
            if "usage_limit" in data:
                db.usage_limit = data["usage_limit"]
            if "per_user_once" in data and data["per_user_once"] is not None:
                db.per_user_once = data["per_user_once"]
            return await self._repo.save(db)

    async def delete_coupon(self, coupon_id: int) -> None:
        async with self._transaction():
            db = await self._repo.find(coupon_id)
            if not db:
                raise AppException("E10400")
            await self._repo.delete(db)

    # ── Áp coupon cho checkout ──────────────────────────────────────────────────

    @staticmethod
    def compute_discount(
        coupon: Coupon, subtotal, shipping_fee
    ) -> tuple[Decimal, Decimal]:
        """Tính (product_discount, ship_discount) từ coupon. Hàm thuần, không DB. Dùng Decimal.

        base = subtotal nếu applies_to='product', = shipping_fee nếu 'shipping'.
        percent -> base * discount/100 (trần max_discount nếu có); fixed -> discount.
        Giảm không vượt quá base tương ứng. Làm tròn 2 chữ số.
        """
        applies_to = coupon.applies_to or "product"
        sub = money(subtotal)
        ship = money(shipping_fee)
        base = sub if applies_to == "product" else ship

        if (coupon.discount_type or "fixed") == "percent":
            amount = base * money(coupon.discount) / Decimal("100")
            if coupon.max_discount is not None:
                amount = min(amount, money(coupon.max_discount))
        else:
            amount = money(coupon.discount)

        if amount < 0:
            amount = Decimal("0")
        if applies_to == "product":
            return quantize(min(amount, sub)), Decimal("0")
        return Decimal("0"), quantize(min(amount, ship))

    async def resolve(
        self,
        code: str,
        subtotal: float,
        shipping_fee: float,
        user_id: int,
        for_update: bool = False,
    ) -> CouponApplication:
        """Validate + tính giảm cho một mã. CHẠY TRONG transaction của caller (đọc repo).

        for_update=True: khóa dòng coupon (dùng khi thực sự tạo đơn) để tăng used_count an
        toàn dưới truy cập đồng thời; preview để mặc định False (chỉ đọc, không khóa).

        Lỗi: E10400 không tồn tại, E10402 không hợp lệ (vô hiệu), E10401 hết hạn,
        E10404 chưa đạt đơn tối thiểu, E10405 hết lượt, E10406 user đã dùng.
        """
        coupon = await self._repo.find_by_code(code, for_update=for_update)
        if not coupon:
            raise AppException("E10400")

        if not coupon.is_active:
            raise AppException("E10402", "Mã giảm giá đã bị vô hiệu hóa")

        now = datetime.now(timezone.utc)
        start = self._as_aware(coupon.start_date)
        end = self._as_aware(coupon.end_date)
        if not (start <= now <= end):
            raise AppException("E10401")

        if money(subtotal) < money(coupon.min_order_amount):
            raise AppException("E10404")

        if coupon.usage_limit is not None and coupon.used_count >= coupon.usage_limit:
            raise AppException("E10405")

        if coupon.per_user_once:
            used = await self._order_repo.count_by_coupon_and_user(coupon.id, user_id)
            if used > 0:
                raise AppException("E10406")

        product_discount, ship_discount = self.compute_discount(
            coupon, subtotal, shipping_fee
        )
        return CouponApplication(coupon, product_discount, ship_discount)

    async def increment_usage(self, coupon: Coupon) -> None:
        """Tăng used_count cho coupon. CHẠY TRONG transaction của caller (sau khi tạo đơn)."""
        coupon.used_count = (coupon.used_count or 0) + 1
        await self._repo.save(coupon)

    async def decrement_usage(self, coupon: Coupon) -> None:
        """Giảm used_count (không âm) - dùng khi hoàn kho đơn online quá hạn (nhả lại lượt dùng).
        CHẠY TRONG transaction của caller."""
        coupon.used_count = max((coupon.used_count or 0) - 1, 0)
        await self._repo.save(coupon)

    async def get_coupon_for_update(self, coupon_id: int) -> Coupon | None:
        """Lấy coupon kèm khóa dòng để tăng used_count. CHẠY TRONG transaction của caller
        (dùng khi xác nhận thanh toán online - trừ kho + tăng lượt dùng cùng một transaction)."""
        return await self._repo.find_for_update(coupon_id)

    @staticmethod
    def _as_aware(dt: datetime) -> datetime:
        """Coi datetime naive như UTC để so sánh an toàn với now(tz=utc)."""
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
