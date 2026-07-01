"""
RateLimiterService - giới hạn tần suất gọi (chống brute-force / spam) dựa trên CacheService.

Đếm số lần theo key trong một cửa sổ thời gian (TTL giây). Vượt ngưỡng -> AppException (429).
Dùng CacheService (mặc định InMemoryCacheService, đổi Redis được) nên không cần hạ tầng ngoài;
lưu ý deploy nhiều worker cần Redis để đếm chung giữa các tiến trình.

Chống dò mật khẩu / spam email cho: /login, /forgot-password, /otp/request. Khóa theo tài khoản
mục tiêu (username/email/user_id) vì lưu lượng đi qua proxy Next.js nên IP không phân biệt được.
"""
from __future__ import annotations

from xime.starters.cache import CacheService

from app.exception.app_exception import AppException


class RateLimiterService:
    def __init__(self, cache: CacheService) -> None:
        self._cache = cache

    async def _count(self, key: str) -> int:
        raw = await self._cache.get(key)
        if raw is None:
            return 0
        try:
            return int(raw)
        except (ValueError, TypeError):
            # Giá trị hỏng (không phải số) -> coi như chưa đếm.
            # Corrupt (non-numeric) value -> treat as zero.
            return 0

    async def ensure(self, key: str, limit: int, error_key: str = "E1040") -> None:
        """Ném lỗi (429) nếu đã đạt/vượt ngưỡng. KHÔNG tăng bộ đếm."""
        if await self._count(key) >= limit:
            raise AppException(error_key)

    async def hit(self, key: str, window_seconds: int) -> None:
        """Tăng bộ đếm cho key, đặt TTL = window_seconds."""
        count = await self._count(key)
        await self._cache.set(key, str(count + 1).encode(), ttl=window_seconds)

    async def guard(
        self, key: str, limit: int, window_seconds: int, error_key: str = "E1040"
    ) -> None:
        """Kiểm tra ngưỡng rồi tăng bộ đếm - dùng cho endpoint tính MỌI lần gọi (gửi OTP,
        quên mật khẩu). Vượt ngưỡng -> ném trước khi tăng."""
        await self.ensure(key, limit, error_key)
        await self.hit(key, window_seconds)

    async def reset(self, key: str) -> None:
        """Xóa bộ đếm - gọi khi thao tác thành công (vd đăng nhập đúng)."""
        await self._cache.delete(key)
