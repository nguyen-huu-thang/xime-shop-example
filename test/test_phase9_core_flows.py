"""
Phase 9 - Test các luồng cốt lõi: auth, phân quyền, service layer.

Dùng TestApplication + DI overrides để test mà không cần DB thật.
Unit test cho logic không phụ thuộc DB.
"""
import pytest

import app.config.web  # noqa: F401 - side effect: configure_controllers + openapi
from app.exception.app_exception import AppException
from app.exception.error_code import ERROR_CODES, get_error
from app.service.search_service import SearchService
from app.service.user_service import UserService


# ── Unit: error codes ──────────────────────────────────────────────────────────

def test_all_critical_error_codes_present():
    """Các mã lỗi cốt lõi phải tồn tại trong ERROR_CODES."""
    critical_keys = [
        "E1004",   # user not found
        "E1005",   # wrong password
        "E1024",   # wrong current password
        "E2021",   # forbidden
        "E2025",   # login required
        "E2050",   # invalid refresh token
        "E10200",  # product/resource not found
        "E10600",  # out of stock
        "E10711",  # validation error
        "E5001",   # no file
        "E5010",   # upload error
    ]
    for key in critical_keys:
        assert key in ERROR_CODES, f"Thiếu error code: {key}"


def test_get_error_fallback_for_unknown_key():
    err = get_error("UNKNOWN_KEY_XYZ")
    assert err.code == 0  # E0000 fallback
    assert err.http_status == 500


def test_app_exception_maps_to_http_status():
    cases = [
        ("E2021", 403),
        ("E2025", 401),
        ("E1004", 404),
        ("E10711", 400),
    ]
    for key, expected_status in cases:
        exc = AppException(key)
        assert exc.http_status == expected_status, f"{key}: expected {expected_status}, got {exc.http_status}"


# ── Unit: UserService.hash_password ───────────────────────────────────────────

def test_hash_password_is_bcrypt():
    hashed = UserService.hash_password("TestPass@123")
    assert hashed.startswith("$2b$") or hashed.startswith("$2a$")
    assert hashed != "TestPass@123"


def test_hash_password_different_each_call():
    h1 = UserService.hash_password("same")
    h2 = UserService.hash_password("same")
    # bcrypt generates unique salt each time
    # bcrypt tạo salt ngẫu nhiên mỗi lần
    assert h1 != h2


# ── Unit: SearchService relevance scoring ─────────────────────────────────────

class _StubProductService:
    """Stub trả về danh sách sản phẩm cố định."""
    async def search_products_by_keywords(self, keywords: str) -> list[dict]:
        return [
            {"id": 1, "name": "Áo đỏ", "description": "Áo cotton đỏ", "price": 150000.0},
            {"id": 2, "name": "Quần xanh", "description": "Quần jean xanh lá", "price": 250000.0},
            {"id": 3, "name": "Giày thể thao", "description": "Giày đỏ nhẹ", "price": 500000.0},
        ]


@pytest.mark.asyncio
async def test_search_product_relevance_ordering():
    svc = SearchService(_StubProductService())
    result = await svc.search_product("đỏ")
    # "Áo đỏ" có tên chứa "đỏ" (+5) AND mô tả chứa "đỏ" (+2) = 7 points
    # "Giày thể thao" có mô tả "Giày đỏ nhẹ" (+2) = 2 points
    results = result["results"]
    assert len(results) == 2
    assert results[0]["product"]["id"] == 1   # score 7 (name+desc)
    assert results[1]["product"]["id"] == 3   # score 2 (desc only)
    assert result["total"] == 2


@pytest.mark.asyncio
async def test_search_product_price_filter():
    svc = SearchService(_StubProductService())
    result = await svc.search_product("đỏ", max_price=200000.0)
    # Only "Áo đỏ" (150000) passes the price filter; "Giày thể thao" (500000) is excluded
    results = result["results"]
    assert len(results) == 1
    assert results[0]["product"]["id"] == 1


@pytest.mark.asyncio
async def test_search_product_pagination():
    svc = SearchService(_StubProductService())
    result = await svc.search_product("đỏ", page=1, limit=1)
    assert len(result["results"]) == 1
    assert result["total"] == 2
    assert result["page"] == 1
    assert result["limit"] == 1


@pytest.mark.asyncio
async def test_search_all_returns_empty():
    svc = SearchService(_StubProductService())
    assert await svc.search_all("anything") == []


# ── Unit: FileService path building ───────────────────────────────────────────

def test_file_path_structure():
    from app.service.file_service import FileService

    class _FakeService:
        pass

    # Instantiate without real DI - just call the private methods
    # Kiểm tra logic tạo đường dẫn file mà không cần DB
    svc = object.__new__(FileService)

    random_name = "abcd1234567890ef1234567890abcdef"  # 32 chars
    folder1, folder2, relative = svc._build_file_path(random_name, "jpg")

    assert folder1 == "ab"
    assert folder2 == "cd"
    assert relative == "ab/cd/1234567890ef1234567890abcdef.jpg"


def test_generate_random_name_length():
    from app.service.file_service import FileService

    svc = object.__new__(FileService)
    name = svc._generate_random_name()
    assert len(name) == 32
    # Should be hex (lowercase)
    assert all(c in "0123456789abcdef" for c in name)
