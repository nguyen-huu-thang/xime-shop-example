"""
Test tích hợp cá nhân hóa (cần DB shop đã seed).

Phase 2: xác nhận ghi interaction không phá hành động chính + FK ON DELETE CASCADE hoạt động:
user đã đăng nhập xem sản phẩm (ghi 1 view) rồi bị xóa -> xóa thành công, interaction đi theo,
KHÔNG bị FK chặn. Đây là tính chất an toàn cốt lõi để recording không làm vỡ luồng khác.

Chạy: pytest test/test_personalization_integration.py -v -s
"""
import uuid
from contextlib import asynccontextmanager

import pytest

import app.config.web  # noqa: F401 - side effect: configure_controllers + openapi
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


@pytest.mark.asyncio
async def test_view_recorded_and_user_delete_cascades():
    async with app_client() as client:
        admin = await _login(client)

        # Tạo category + product để xem
        cat_id = (await client.post(
            "/api/categories", json={"name": f"Pers {_S}"}, headers=admin
        )).json()["id"]
        prod_id = (await client.post(
            "/api/products",
            json={"name": f"Pers Prod {_S}", "categoryId": cat_id, "locationAddress": "HN",
                  "price": 1000, "stock": 5},
            headers=admin,
        )).json()["id"]

        # Tạo user thường, đăng nhập, xem sản phẩm (ghi 1 view interaction)
        uname = f"pv_{_S}_{uuid.uuid4().hex[:6]}"
        u = (await client.post(
            "/api/users",
            json={"username": uname, "email": f"{uname}@test.local",
                  "password": "Passw0rd!", "isActive": True},
            headers=admin,
        )).json()
        u_headers = await _login(client, uname, "Passw0rd!")

        # GET detail (public) khi đã đăng nhập -> InteractionService.record("view")
        r = await client.get(f"/api/products/{prod_id}", headers=u_headers)
        assert r.status_code == 200, r.text

        # Xóa user: phải thành công dù đã có interaction (FK ON DELETE CASCADE)
        r = await client.delete(f"/api/users/{u['id']}", headers=admin)
        assert r.status_code == 200, f"Xóa user có interaction phải cascade, không bị chặn: {r.text}"
        print("\n[pers] ✓ Ghi view OK + xóa user cascade interaction không bị FK chặn")

        # cleanup
        await client.delete(f"/api/products/{prod_id}", headers=admin)
        await client.delete(f"/api/categories/{cat_id}", headers=admin)


@pytest.mark.asyncio
async def test_recommendation_endpoints():
    """Sau khi xem 1 sản phẩm: recently-viewed chứa nó, for-you gợi ý theo category, trending trả list."""
    async with app_client() as client:
        admin = await _login(client)

        cat_id = (await client.post(
            "/api/categories", json={"name": f"Rec {_S}"}, headers=admin
        )).json()["id"]
        p1 = (await client.post(
            "/api/products",
            json={"name": f"Rec P1 {_S}", "categoryId": cat_id, "locationAddress": "HN",
                  "price": 1000, "stock": 5},
            headers=admin,
        )).json()["id"]
        p2 = (await client.post(
            "/api/products",
            json={"name": f"Rec P2 {_S}", "categoryId": cat_id, "locationAddress": "HN",
                  "price": 1000, "stock": 5},
            headers=admin,
        )).json()["id"]

        try:
            # Admin xem P1 -> ghi view + dựng affinity cho category
            r = await client.get(f"/api/products/{p1}", headers=admin)
            assert r.status_code == 200, r.text

            # recently-viewed chứa P1
            r = await client.get("/api/recommendations/recently-viewed", headers=admin)
            assert r.status_code == 200, r.text
            rv_ids = {p["id"] for p in r.json()}
            assert p1 in rv_ids, f"recently-viewed phải chứa P1: {rv_ids}"

            # for-you: gợi ý theo affinity category -> chứa sản phẩm trong category (P1 và/hoặc P2)
            r = await client.get("/api/recommendations/for-you", headers=admin)
            assert r.status_code == 200, r.text
            fy_ids = {p["id"] for p in r.json()}
            assert fy_ids & {p1, p2}, f"for-you phải gợi ý sản phẩm trong category: {fy_ids}"

            # trending: trả về list (P1 có tín hiệu view trong cửa sổ)
            r = await client.get("/api/recommendations/trending")
            assert r.status_code == 200, r.text
            assert isinstance(r.json(), list)
            print("\n[pers] ✓ recently-viewed / for-you / trending hoạt động")
        finally:
            await client.delete(f"/api/products/{p1}", headers=admin)
            await client.delete(f"/api/products/{p2}", headers=admin)
            await client.delete(f"/api/categories/{cat_id}", headers=admin)


@pytest.mark.asyncio
async def test_cooccurrence_rebuild_and_related():
    """Mua 2 sản phẩm trong cùng đơn -> rebuild -> related của sp này chứa sp kia."""
    async with app_client() as client:
        admin = await _login(client)

        cat_id = (await client.post(
            "/api/categories", json={"name": f"Co {_S}"}, headers=admin
        )).json()["id"]
        p1 = (await client.post(
            "/api/products",
            json={"name": f"Co P1 {_S}", "categoryId": cat_id, "locationAddress": "HN",
                  "price": 1000, "stock": 10},
            headers=admin,
        )).json()["id"]
        p2 = (await client.post(
            "/api/products",
            json={"name": f"Co P2 {_S}", "categoryId": cat_id, "locationAddress": "HN",
                  "price": 2000, "stock": 10},
            headers=admin,
        )).json()["id"]

        order_id = None
        addr_id = None
        try:
            # Lấy default option của 2 sản phẩm, thêm vào giỏ, đặt 1 đơn chứa cả hai
            opt1 = (await client.get(f"/api/products/{p1}/option-default", headers=admin)).json()["id"]
            opt2 = (await client.get(f"/api/products/{p2}/option-default", headers=admin)).json()["id"]
            c1 = (await client.post(
                "/api/cart", json={"productOptionId": opt1, "quantity": 1}, headers=admin
            )).json()["id"]
            c2 = (await client.post(
                "/api/cart", json={"productOptionId": opt2, "quantity": 1}, headers=admin
            )).json()["id"]
            addr_id = (await client.post(
                "/api/addresses",
                json={
                    "recipientName": "Người Nhận",
                    "recipientPhone": "0900000000",
                    "province": "Hà Nội",
                    "district": "Cầu Giấy",
                    "ward": "Dịch Vọng",
                    "detail": "HN test",
                },
                headers=admin,
            )).json()["id"]
            order = await client.post(
                "/api/orders", json={"cartIds": [c1, c2], "addressId": addr_id}, headers=admin
            )
            assert order.status_code == 201, order.text
            order_id = order.json()["id"]

            # Dựng lại co-occurrence (endpoint admin thủ công)
            r = await client.post("/api/recommendations/admin/rebuild-cooccurrence", headers=admin)
            assert r.status_code == 200, r.text

            # related của P1 phải chứa P2 (mua cùng đơn)
            r = await client.get(f"/api/products/{p1}/related")
            assert r.status_code == 200, r.text
            ids = {p["id"] for p in r.json()}
            assert p2 in ids, f"related của P1 phải chứa P2: {ids}"
            print("\n[pers] ✓ co-occurrence rebuild + related hoạt động")
        finally:
            if order_id is not None:
                await client.delete(f"/api/orders/{order_id}", headers=admin)
            if addr_id is not None:
                await client.delete(f"/api/addresses/{addr_id}", headers=admin)
            await client.delete(f"/api/products/{p1}", headers=admin)
            await client.delete(f"/api/products/{p2}", headers=admin)
            await client.delete(f"/api/categories/{cat_id}", headers=admin)


@pytest.mark.asyncio
async def test_rebuild_cooccurrence_requires_permission():
    """User thường (không có manage_recommendations) gọi rebuild -> 403."""
    async with app_client() as client:
        admin = await _login(client)
        uname = f"np_{_S}_{uuid.uuid4().hex[:6]}"
        u = (await client.post(
            "/api/users",
            json={"username": uname, "email": f"{uname}@test.local",
                  "password": "Passw0rd!", "isActive": True},
            headers=admin,
        )).json()
        u_headers = await _login(client, uname, "Passw0rd!")
        try:
            r = await client.post(
                "/api/recommendations/admin/rebuild-cooccurrence", headers=u_headers
            )
            assert r.status_code == 403, r.text
            assert r.json()["errorKey"] == "E2021"
            print("\n[pers] ✓ rebuild cooccurrence cần quyền manage_recommendations")
        finally:
            await client.delete(f"/api/users/{u['id']}", headers=admin)
