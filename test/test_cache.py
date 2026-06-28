"""
Unit test cho InMemoryCacheService (không cần DB).

Chạy: pytest test/test_cache.py -v
"""
import pytest

from app.cache.in_memory_cache_service import InMemoryCacheService


@pytest.mark.asyncio
async def test_set_get_roundtrip():
    cache = InMemoryCacheService()
    await cache.set("k", b"value")
    assert await cache.get("k") == b"value"
    assert await cache.exists("k") is True


@pytest.mark.asyncio
async def test_get_absent_returns_none():
    cache = InMemoryCacheService()
    assert await cache.get("missing") is None
    assert await cache.exists("missing") is False


@pytest.mark.asyncio
async def test_delete_removes_key():
    cache = InMemoryCacheService()
    await cache.set("k", b"v")
    await cache.delete("k")
    assert await cache.get("k") is None
    # delete key không tồn tại là no-op, không lỗi
    await cache.delete("k")


@pytest.mark.asyncio
async def test_ttl_zero_expires_immediately():
    cache = InMemoryCacheService()
    # ttl=0 -> expires_at = now -> đọc sau đó coi như đã hết hạn
    await cache.set("k", b"v", ttl=0)
    assert await cache.get("k") is None


@pytest.mark.asyncio
async def test_ttl_none_persists():
    cache = InMemoryCacheService()
    await cache.set("k", b"v", ttl=None)
    assert await cache.get("k") == b"v"
