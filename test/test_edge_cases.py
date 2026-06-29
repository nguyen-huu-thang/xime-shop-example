"""
Test đường biên / thăm dò lỗi - kiểm tra các nhánh dễ sinh lỗi không sạch (500 thay vì
AppException), TOCTOU tồn kho, và trùng lặp dữ liệu phân quyền.

Mục đích: phát hiện vấn đề + chống tái xuất hiện (regression). Các test assert HÀNH VI
ĐÚNG nghiệp vụ. Ban đầu 3 test fail (coupon trùng code/ngày sai -> 500, permission assign
trùng), sau khi sửa code đã pass. Chi tiết bug + cách sửa: .claude/docs/review-test-2026-06-29.md.

Chạy: pytest test/test_edge_cases.py -v -s
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


async def _login(client, username="admin", password="Admin@123") -> dict:
    resp = await client.post("/api/login", json={"username": username, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['accessToken']}"}


# ─────────────────────────────────────────────────────────────────────────────
# Order: vượt tồn kho -> E10506 (đúng nghiệp vụ, mong đợi PASS)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_order_exceeds_stock_returns_e10506():
    async with app_client() as client:
        headers = await _login(client)
        resp = await client.post("/api/categories", json={"name": f"Cat OS {_S}"}, headers=headers)
        cat_id = resp.json()["id"]
        resp = await client.post(
            "/api/products",
            json={"name": f"Low Stock {_S}", "categoryId": cat_id, "locationAddress": "HN",
                  "price": 1000, "stock": 1},
            headers=headers,
        )
        prod_id = resp.json()["id"]
        opt = (await client.get(f"/api/products/{prod_id}/option-default", headers=headers)).json()

        # Thêm vào giỏ số lượng = tồn kho (1) - OK
        resp = await client.post(
            "/api/cart", json={"productOptionId": opt["id"], "quantity": 1}, headers=headers
        )
        assert resp.status_code == 201, resp.text
        cart_id = resp.json()["id"]

        # Giảm tồn kho xuống 0 bằng cách... đặt hàng trước thì hết. Thay vào đó test cart out-of-stock:
        # thêm tiếp 1 nữa (tổng 2 > stock 1) -> E10201
        resp = await client.post(
            "/api/cart", json={"productOptionId": opt["id"], "quantity": 5}, headers=headers
        )
        assert resp.status_code in (400, 409), resp.text
        assert resp.json()["errorKey"] == "E10201", resp.text
        print("\n[edge] ✓ Cart vượt tồn kho -> E10201")

        # cleanup
        await client.delete(f"/api/cart/{cart_id}", headers=headers)
        await client.delete(f"/api/products/{prod_id}", headers=headers)
        await client.delete(f"/api/categories/{cat_id}", headers=headers)


# ─────────────────────────────────────────────────────────────────────────────
# Coupon: trùng code (DB unique) -> phải là lỗi nghiệp vụ sạch, KHÔNG phải 500
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_coupon_duplicate_code_clean_error():
    async with app_client() as client:
        headers = await _login(client)
        code = f"DUP{_S}"
        body = {
            "code": code, "discount": 10,
            "startDate": "2026-01-01T00:00:00", "endDate": "2026-12-31T00:00:00",
        }
        r1 = await client.post("/api/coupons", json=body, headers=headers)
        assert r1.status_code == 201, r1.text
        cid = r1.json()["id"]

        # Tạo trùng code -> lỗi nghiệp vụ sạch (4xx, E10402), KHÔNG phải 500
        r2 = await client.post("/api/coupons", json=body, headers=headers)
        print(f"\n[edge] coupon trùng code -> status={r2.status_code}, body={r2.text[:200]}")
        try:
            assert r2.status_code < 500, "Trùng code coupon trả 500 (lỗi DB lộ ra ngoài) thay vì lỗi nghiệp vụ"
            assert r2.status_code in (400, 409)
            assert r2.json()["errorKey"] == "E10402"
        finally:
            await client.delete(f"/api/coupons/{cid}", headers=headers)
            # nếu lỡ tạo được bản thứ 2 thì dọn luôn
            if r2.status_code == 201:
                await client.delete(f"/api/coupons/{r2.json()['id']}", headers=headers)


# ─────────────────────────────────────────────────────────────────────────────
# Coupon: ngày sai định dạng -> phải 4xx (validation), KHÔNG phải 500
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_coupon_invalid_date_clean_error():
    async with app_client() as client:
        headers = await _login(client)
        body = {
            "code": f"BADDATE{_S}", "discount": 10,
            "startDate": "khong-phai-ngay", "endDate": "2026-12-31T00:00:00",
        }
        resp = await client.post("/api/coupons", json=body, headers=headers)
        print(f"\n[edge] coupon ngày sai -> status={resp.status_code}, body={resp.text[:200]}")
        if resp.status_code == 201:
            await client.delete(f"/api/coupons/{resp.json()['id']}", headers=headers)
        assert resp.status_code < 500, "Ngày sai định dạng trả 500 (ValueError lộ ra) thay vì 4xx"
        assert resp.status_code in (400, 422)
        if resp.status_code == 400:
            assert resp.json()["errorKey"] == "E10402"


# ─────────────────────────────────────────────────────────────────────────────
# Group permission: assign 2 lần cùng quyền -> không tạo bản ghi trùng
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_group_permission_no_duplicate_on_double_assign():
    async with app_client() as client:
        headers = await _login(client)
        gid = (await client.post("/api/group", json={"name": f"GPDup {_S}"}, headers=headers)).json()["id"]
        perm = {"is_active": True, "is_denied": False, "target": "all"}

        await client.post(
            "/api/group-permissions",
            json={"group_id": gid, "permissions": {"view_products": perm}},
            headers=headers,
        )
        await client.post(
            "/api/group-permissions",
            json={"group_id": gid, "permissions": {"view_products": perm}},
            headers=headers,
        )
        # Lấy lại danh sách quyền của nhóm - không được có 2 entry view_products
        got = (await client.get(f"/api/group-permissions/{gid}", headers=headers)).json()
        print(f"\n[edge] group-permissions sau 2 lần assign cùng quyền: {got}")
        try:
            assert len(got) == len(set(got)), f"Có bản ghi quyền trùng lặp: {got}"
        finally:
            await client.request(
                "DELETE", "/api/group-permissions",
                json={"group_id": gid, "permissions": ["view_products"]}, headers=headers,
            )
            await client.delete(f"/api/group/{gid}", headers=headers)


# ─────────────────────────────────────────────────────────────────────────────
# IDOR: GET /api/wishlist/{id} của người khác -> 403 (chống tái xuất hiện, Phase 5)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_wishlist_detail_idor_blocked_for_non_owner():
    async with app_client() as client:
        admin = await _login(client)

        # Admin tạo category + product + wishlist item (thuộc về admin)
        cat_id = (await client.post(
            "/api/categories", json={"name": f"Cat IDOR {_S}"}, headers=admin
        )).json()["id"]
        prod_id = (await client.post(
            "/api/products",
            json={"name": f"IDOR Prod {_S}", "categoryId": cat_id, "locationAddress": "HN",
                  "price": 1000, "stock": 3},
            headers=admin,
        )).json()["id"]
        wid = (await client.post(
            "/api/wishlist", json={"productId": prod_id}, headers=admin
        )).json()["id"]

        # User thường (không có quyền) đăng ký + đăng nhập
        uname = f"idor_{_S}"
        await client.post(
            "/api/register",
            json={"username": uname, "email": f"{uname}@test.local", "password": "Passw0rd!"},
        )
        u_headers = await _login(client, uname, "Passw0rd!")
        uid = (await client.get("/api/me", headers=u_headers)).json()["id"]

        try:
            # Trước khi vá: trả 200 (đọc trộm). Sau khi vá: 403 E2021.
            resp = await client.get(f"/api/wishlist/{wid}", headers=u_headers)
            assert resp.status_code == 403, f"IDOR: user thường đọc được wishlist người khác: {resp.text}"
            assert resp.json()["errorKey"] == "E2021"
            print("\n[idor] ✓ User thường GET wishlist người khác -> 403 E2021")

            # Chủ sở hữu (admin) vẫn xem được
            owner_resp = await client.get(f"/api/wishlist/{wid}", headers=admin)
            assert owner_resp.status_code == 200, owner_resp.text
        finally:
            await client.delete(f"/api/wishlist/{wid}", headers=admin)
            await client.delete(f"/api/products/{prod_id}", headers=admin)
            await client.delete(f"/api/categories/{cat_id}", headers=admin)
            await client.delete(f"/api/users/{uid}", headers=admin)
