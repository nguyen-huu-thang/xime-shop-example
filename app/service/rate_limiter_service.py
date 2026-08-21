"""
RateLimiterService - giới hạn tần suất gọi (chống brute-force / spam) trên kho Xime Store (LMDB).

Đếm số lần theo key trong một cửa sổ thời gian (TTL giây). Vượt ngưỡng -> AppException (429).

Từ 2026-08-21 dùng RateLimitStore (CounterStore của xime.starters.lmdb) thay CacheService:
bộ đếm dùng chung giữa các tiến trình của cùng một máy, và `incr()` nguyên tử nên không mất
lượt đếm khi backend có I/O thật (bản cũ get+set đo được 1/20 lượt qua một cache kiểu Redis).
Lý do đầy đủ: app/store/rate_limit_store.py.

Chống dò mật khẩu / spam email cho: /login, /forgot-password, /otp/request. Khóa theo tài khoản
mục tiêu (username/email/user_id) vì lưu lượng đi qua proxy Next.js nên IP không phân biệt được.
"""
from __future__ import annotations

from app.exception.app_exception import AppException
from app.store.rate_limit_store import RateLimitStore


class RateLimiterService:
    def __init__(self, rate_limit_store: RateLimitStore) -> None:
        self._store = rate_limit_store

    async def _count(self, key: str) -> int:
        # Bản ghi chưa có hoặc đã hết hạn -> 0. Store trả int nên không phải tự parse như
        # thời còn lưu bytes trong cache.
        # A missing or expired entry counts as zero.
        return await self._store.get(key) or 0

    async def ensure(self, key: str, limit: int, error_key: str = "E1040") -> None:
        """Ném lỗi (429) nếu đã đạt/vượt ngưỡng. KHÔNG tăng bộ đếm.

        Việc KHÔNG đếm khi đang bị chặn là bắt buộc, không phải tiết kiệm: mọi lần ghi đặt lại
        hạn, nên đếm tiếp thì mỗi lần người dùng bấm lại sẽ đẩy hạn ra xa và khóa kéo dài vô hạn.
        Never count while already locked out: a write resets the expiry, so the lock would never
        end.
        """
        if await self._count(key) >= limit:
            raise AppException(error_key)

    async def hit(self, key: str, window_seconds: int) -> None:
        """Tăng bộ đếm cho key (nguyên tử), đặt lại TTL = window_seconds."""
        await self._store.incr(key, ttl=window_seconds)

    async def guard(
        self, key: str, limit: int, window_seconds: int, error_key: str = "E1040"
    ) -> None:
        """Kiểm tra ngưỡng rồi tăng bộ đếm - dùng cho endpoint tính MỌI lần gọi (gửi OTP,
        quên mật khẩu). Vượt ngưỡng -> ném trước khi tăng."""
        await self.ensure(key, limit, error_key)
        await self.hit(key, window_seconds)

    async def reset(self, key: str) -> None:
        """Xóa bộ đếm - gọi khi thao tác thành công (vd đăng nhập đúng)."""
        await self._store.delete(key)
