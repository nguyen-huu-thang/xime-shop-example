"""
Test regression cho các lỗ hổng phân quyền đã vá (2026-06-30):
- search_controller: /users, /groups cần quyền admin; /cart, /orders cần đăng nhập.
- review_controller: create gán userId theo user đăng nhập (chống giả mạo); update chỉ chủ sở hữu
  (vá IDOR); detail KHÔNG lộ review chưa duyệt cho khách.
Bổ sung (2026-07-01):
- file_controller: PUT /{id} chỉ chủ file (hoặc admin có delete_file) mới sửa metadata (vá IDOR).
Yêu cầu DB đã seed.
"""
import uuid
from contextlib import asynccontextmanager

import pytest

import app.config.web  # noqa: F401
from app.config.dependency import dependency
from httpx import ASGITransport, AsyncClient
from xime.adapters.web import WebAdapter
from xime.testing import TestApplication

_S = uuid.uuid4().hex[:6]


@asynccontextmanager
async def app_client():
    async with TestApplication(binding=dependency) as test_app:
        fastapi_app = WebAdapter().build_app(test_app)
        async with fastapi_app.router.lifespan_context(fastapi_app):
            transport = ASGITransport(app=fastapi_app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                yield client


async def _admin(client) -> dict:
    r = await client.post("/api/login", json={"username": "admin", "password": "Admin@123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['accessToken']}"}


async def _new_user(client, suffix: str) -> tuple[dict, dict]:
    username = f"u{suffix}"[:20]
    pw = "Pass@123"
    r = await client.post(
        "/api/register",
        json={"username": username, "email": f"{username}@ex.test", "password": pw},
    )
    assert r.status_code == 201, r.text
    r = await client.post("/api/login", json={"username": username, "password": pw})
    assert r.status_code == 200, r.text
    headers = {"Authorization": f"Bearer {r.json()['accessToken']}"}
    me = (await client.get("/api/me", headers=headers)).json()
    return headers, me


# ── search_controller ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_users_requires_view_users():
    async with app_client() as client:
        # Khách ẩn danh -> 401
        r = await client.get("/api/search/users", params={"keywords": "a"})
        assert r.status_code == 401

        # User thường (không có view_users) -> 403
        user_headers, _ = await _new_user(client, _S + "su")
        r = await client.get(
            "/api/search/users", params={"keywords": "a"}, headers=user_headers
        )
        assert r.status_code == 403

        # Admin -> 200
        admin = await _admin(client)
        r = await client.get(
            "/api/search/users", params={"keywords": "a"}, headers=admin
        )
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_search_groups_requires_view_groups():
    async with app_client() as client:
        r = await client.get("/api/search/groups", params={"keywords": "a"})
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_search_cart_and_orders_require_login():
    async with app_client() as client:
        for path in ("/api/search/cart", "/api/search/orders"):
            r = await client.get(path, params={"keywords": "a"})
            assert r.status_code == 401, path


@pytest.mark.asyncio
async def test_search_products_public():
    # Tìm sản phẩm vẫn công khai
    async with app_client() as client:
        r = await client.get("/api/search/products", params={"keywords": "a"})
        assert r.status_code == 200


# ── cart_controller (self-service) ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cart_create_is_self_service_no_admin_permission():
    """Khách hàng thường (không có quyền create_cart) vẫn thêm được vào GIỎ CỦA MÌNH.
    Nhưng danh sách giỏ toàn hệ thống (/all) vẫn cần quyền admin view_carts."""
    async with app_client() as client:
        admin = await _admin(client)
        cat = (await client.post(
            "/api/categories", json={"name": f"cc-{_S}"}, headers=admin
        )).json()
        prod = (await client.post(
            "/api/products",
            json={"name": f"cp-{_S}", "categoryId": cat["id"], "locationAddress": "HN",
                  "price": 1000, "stock": 5},
            headers=admin,
        )).json()
        opt = (await client.get(f"/api/products/{prod['id']}/option-default")).json()

        # Khách ẩn danh -> 401
        r = await client.post(
            "/api/cart", json={"productOptionId": opt["id"], "quantity": 1}
        )
        assert r.status_code == 401

        # User thường KHÔNG có quyền create_cart -> vẫn thêm vào giỏ của mình OK (201)
        user, _ = await _new_user(client, _S + "ca")
        r = await client.post(
            "/api/cart", json={"productOptionId": opt["id"], "quantity": 1}, headers=user
        )
        assert r.status_code == 201, r.text
        cart_id = r.json()["id"]

        # Xem giỏ của mình OK
        r = await client.get("/api/cart", headers=user)
        assert r.status_code == 200
        assert any(it["id"] == cart_id for it in r.json())

        # Nhưng danh sách giỏ toàn hệ thống cần quyền admin -> 403
        r = await client.get("/api/cart/all", headers=user)
        assert r.status_code == 403

        # Dọn dẹp
        await client.delete(f"/api/cart/{cart_id}", headers=user)
        await client.delete(f"/api/products/{prod['id']}", headers=admin)
        await client.delete(f"/api/categories/{cat['id']}", headers=admin)


# ── review_controller ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_review_create_ignores_body_userid_and_update_idor():
    async with app_client() as client:
        admin = await _admin(client)
        # Tạo SP để review
        cat = (await client.post(
            "/api/categories", json={"name": f"rc-{_S}"}, headers=admin
        )).json()
        prod = (await client.post(
            "/api/products",
            json={"name": f"rp-{_S}", "categoryId": cat["id"], "locationAddress": "HN",
                  "price": 1000, "stock": 5},
            headers=admin,
        )).json()

        user_a, me_a = await _new_user(client, _S + "ra")
        user_b, _ = await _new_user(client, _S + "rb")

        # userA tạo review, cố giả mạo userId=1 (admin) trong body -> phải bị bỏ qua
        r = await client.post(
            "/api/reviews",
            json={"userId": 1, "productId": prod["id"], "rating": 5, "comment": "ok"},
            headers=user_a,
        )
        assert r.status_code == 201, r.text
        review = r.json()
        assert review["user_id"] == me_a["id"]  # gán theo user đăng nhập, KHÔNG phải body
        review_id = review["id"]

        # userB (không phải chủ) sửa review của userA -> 403 (IDOR đã vá)
        r = await client.put(
            f"/api/reviews/{review_id}", json={"rating": 1}, headers=user_b
        )
        assert r.status_code == 403

        # Chủ sở hữu sửa được
        r = await client.put(
            f"/api/reviews/{review_id}", json={"rating": 4}, headers=user_a
        )
        assert r.status_code == 200, r.text

        # Review chưa duyệt: khách ẩn danh xem chi tiết -> 401 (không lộ)
        r = await client.get(f"/api/reviews/{review_id}")
        assert r.status_code == 401

        # Chủ sở hữu xem được review chưa duyệt của mình
        r = await client.get(f"/api/reviews/{review_id}", headers=user_a)
        assert r.status_code == 200

        # Dọn dẹp
        await client.delete(f"/api/reviews/{review_id}", headers=admin)
        await client.delete(f"/api/products/{prod['id']}", headers=admin)
        await client.delete(f"/api/categories/{cat['id']}", headers=admin)


# ── file_controller ─────────────────────────────────────────────────────────────

# PNG 1x1 hợp lệ, đủ để upload qua storage starter.
_PNG_1x1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6300010000050001"
    "0d0a2db40000000049454e44ae426082"
)


@pytest.mark.asyncio
async def test_file_update_requires_owner_or_permission():
    """PUT /api/files/{id}: chỉ chủ file (hoặc admin có delete_file) mới sửa metadata (vá IDOR).
    Trước đây user đăng nhập bất kỳ sửa/gán lại file bất kỳ theo id."""
    async with app_client() as client:
        admin = await _admin(client)

        # userA upload file -> file thuộc userA
        user_a, _ = await _new_user(client, _S + "fa")
        r = await client.post(
            "/api/files",
            files={"file": ("pixel.png", _PNG_1x1, "image/png")},
            data={"description": f"sec-{_S}"},
            headers=user_a,
        )
        assert r.status_code == 201, r.text
        file_id = r.json()["id"]

        # userB (không phải chủ, không có delete_file) sửa -> 403 (IDOR đã vá)
        user_b, _ = await _new_user(client, _S + "fb")
        r = await client.put(
            f"/api/files/{file_id}", json={"description": "hacked"}, headers=user_b
        )
        assert r.status_code == 403

        # Khách ẩn danh -> 401
        r = await client.put(f"/api/files/{file_id}", json={"description": "anon"})
        assert r.status_code == 401

        # Chủ file sửa được
        r = await client.put(
            f"/api/files/{file_id}", json={"description": "by-owner"}, headers=user_a
        )
        assert r.status_code == 200, r.text

        # Admin (có delete_file) sửa file của người khác được
        r = await client.put(
            f"/api/files/{file_id}", json={"description": "by-admin"}, headers=admin
        )
        assert r.status_code == 200, r.text

        # Dọn dẹp
        await client.delete(f"/api/files/{file_id}", headers=admin)
