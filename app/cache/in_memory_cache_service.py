"""
InMemoryCacheService - cài đặt CacheService (Protocol framework) bằng dict trong RAM.

Vì framework chỉ kèm backend Redis (cần Redis chạy + cài extra), bản in-memory này cho phép bật
cache mà không phụ thuộc hạ tầng ngoài - phù hợp dev/đơn tiến trình. Khi cần scale nhiều tiến
trình, đổi sang RedisCacheService chỉ bằng cách sửa bind trong config/dependency.py (tầng service
inject CacheService không phải thay đổi).

Lưu ý: cache nằm trong RAM của tiến trình -> không chia sẻ giữa nhiều worker. Với deploy nhiều
worker, dùng Redis để tránh dữ liệu cache lệch nhau.
"""
from __future__ import annotations

import time


class InMemoryCacheService:
    """Cache key/value bytes trong RAM, hỗ trợ TTL theo giây (None = không hết hạn)."""

    def __init__(self) -> None:
        # key -> (value, expires_at_epoch | None)
        self._store: dict[str, tuple[bytes, float | None]] = {}

    def _is_expired(self, expires_at: float | None) -> bool:
        return expires_at is not None and time.monotonic() >= expires_at

    async def get(self, key: str) -> bytes | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if self._is_expired(expires_at):
            # Lazy eviction khi đọc trúng key đã hết hạn.
            # Lazy eviction on read of an expired key.
            self._store.pop(key, None)
            return None
        return value

    async def set(self, key: str, value: bytes, ttl: int | None = None) -> None:
        expires_at = time.monotonic() + ttl if ttl is not None else None
        self._store[key] = (value, expires_at)

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)

    async def exists(self, key: str) -> bool:
        return (await self.get(key)) is not None
