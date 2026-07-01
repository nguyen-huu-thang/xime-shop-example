"""
Regression cho các bản vá nghiêm trọng + trung bình (2026-07-01):

- #2 Phân trang: page <= 0 / limit khổng lồ KHÔNG gây 500 (đã kẹp về offset an toàn).
- #3 Đơn thanh toán online (mock) chỉ trừ kho khi thanh toán THÀNH CÔNG (COD trừ ngay).
- #4 Cập nhật số lượng giỏ vượt tồn kho -> 400 E10201.
- #5 Giỏ hàng không tồn tại -> 404 E10300 (trước trả 403 E10601).
- #6 Rate limit: quá nhiều lần đăng nhập sai -> 429 E2003; spam /forgot-password -> 429.

Yêu cầu DB đã seed (giống test_checkout.py / test_security.py).
"""
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

import pytest

import app.config.web  # noqa: F401 - side effect: configure_controllers + openapi
from app.config.dependency import dependency
from app.service.order_service import OrderService
from httpx import ASGITransport, AsyncClient
from xime.adapters.web import WebAdapter
from xime.testing import TestApplication

_S = uuid.uuid4().hex[:6]


@asynccontextmanager
async def app_ctx():
    """Trả (client, test_app) - test_app để lấy service từ container (gọi job hết hạn)."""
    async with TestApplication(binding=dependency) as test_app:
        fastapi_app = WebAdapter().build_app(test_app)
        async with fastapi_app.router.lifespan_context(fastapi_app):
            transport = ASGITransport(app=fastapi_app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                yield client, test_app


@asynccontextmanager
async def app_client():
    async with app_ctx() as (client, _):
        yield client


async def _admin(client) -> dict:
    r = await client.post("/api/login", json={"username": "admin", "password": "Admin@123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['accessToken']}"}


async def _new_user(client, suffix: str) -> dict:
    username = f"u{suffix}"[:20]
    r = await client.post(
        "/api/register",
        json={"username": username, "email": f"{username}@ex.test", "password": "Pass@123"},
    )
    assert r.status_code == 201, r.text
    r = await client.post("/api/login", json={"username": username, "password": "Pass@123"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['accessToken']}"}


async def _make_product(client, admin, stock: int):
    cat = (await client.post(
        "/api/categories", json={"name": f"h-{_S}-{uuid.uuid4().hex[:4]}"}, headers=admin
    )).json()
    prod = (await client.post(
        "/api/products",
        json={"name": f"hp-{uuid.uuid4().hex[:5]}", "categoryId": cat["id"],
              "locationAddress": "HN", "price": 100000, "stock": stock},
        headers=admin,
    )).json()
    opt = (await client.get(f"/api/products/{prod['id']}/option-default", headers=admin)).json()
    return cat, prod, opt


async def _stock(client, product_id: int) -> int:
    # option-default đọc thẳng DB (không cache) -> tồn kho thời gian thực.
    r = await client.get(f"/api/products/{product_id}/option-default")
    assert r.status_code == 200, r.text
    return r.json()["stock"]


# ── #2 Phân trang ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pagination_non_positive_page_and_huge_limit_no_500():
    async with app_client() as client:
        for page in (0, -1, -100):
            r = await client.get("/api/products", params={"page": page, "limit": 10})
            assert r.status_code == 200, f"page={page}: {r.text}"
        # limit khổng lồ / âm cũng không lỗi (được kẹp)
        for limit in (1000000, 0, -5):
            r = await client.get("/api/products", params={"page": 1, "limit": limit})
            assert r.status_code == 200, f"limit={limit}: {r.text}"


# ── #5 Giỏ hàng không tồn tại -> 404 E10300 ───────────────────────────────────

@pytest.mark.asyncio
async def test_cart_detail_not_found_returns_404_e10300():
    async with app_client() as client:
        user = await _new_user(client, _S + "cd")
        r = await client.get("/api/cart/99999999", headers=user)
        assert r.status_code == 404
        assert r.json()["errorKey"] == "E10300"


# ── #4 Cập nhật giỏ vượt tồn kho -> 400 E10201 ────────────────────────────────

@pytest.mark.asyncio
async def test_cart_update_quantity_exceeding_stock_rejected():
    async with app_client() as client:
        admin = await _admin(client)
        cat, prod, opt = await _make_product(client, admin, stock=2)
        user = await _new_user(client, _S + "cu")

        cart_id = (await client.post(
            "/api/cart", json={"productOptionId": opt["id"], "quantity": 1}, headers=user
        )).json()["id"]

        # Vượt tồn kho (2) -> 400 E10201
        r = await client.put(f"/api/cart/{cart_id}", json={"quantity": 5}, headers=user)
        assert r.status_code == 400
        assert r.json()["errorKey"] == "E10201"

        # Trong tồn kho -> OK
        r = await client.put(f"/api/cart/{cart_id}", json={"quantity": 2}, headers=user)
        assert r.status_code == 200, r.text

        await client.delete(f"/api/cart/{cart_id}", headers=user)
        await client.delete(f"/api/products/{prod['id']}", headers=admin)
        await client.delete(f"/api/categories/{cat['id']}", headers=admin)


# ── #3 Giữ chỗ tồn kho kiểu Shopee: trừ ngay khi đặt, quá hạn hoàn kho ─────────

@pytest.mark.asyncio
async def test_online_order_reserves_stock_at_creation():
    async with app_client() as client:
        admin = await _admin(client)
        cat, prod, opt = await _make_product(client, admin, stock=5)
        user = await _new_user(client, _S + "on")

        cart_id = (await client.post(
            "/api/cart", json={"productOptionId": opt["id"], "quantity": 2}, headers=user
        )).json()["id"]
        addr_id = (await client.post(
            "/api/addresses",
            json={"recipientName": "A", "recipientPhone": "0900000009",
                  "province": "HN", "district": "CG", "ward": "DV", "detail": "1 Test"},
            headers=user,
        )).json()["id"]

        # Đặt đơn online -> chưa thanh toán nhưng KHO ĐÃ TRỪ NGAY (giữ chỗ): 5 - 2 = 3
        order = (await client.post(
            "/api/orders",
            json={"cartIds": [cart_id], "addressId": addr_id, "paymentProvider": "mock_online"},
            headers=user,
        )).json()
        assert order["paymentStatus"] is False
        assert await _stock(client, prod["id"]) == 3  # đã giữ chỗ

        # Thanh toán thành công -> vẫn 3 (không trừ thêm)
        ref = (await client.post(f"/api/orders/{order['id']}/pay", headers=user)).json()["paymentRef"]
        r = await client.post("/api/payments/mock/callback", json={"paymentRef": ref, "success": True})
        assert r.status_code == 200, r.text
        assert r.json()["paymentStatus"] is True
        assert await _stock(client, prod["id"]) == 3

        await client.delete(f"/api/orders/{order['id']}", headers=admin)
        await client.delete(f"/api/addresses/{addr_id}", headers=user)
        await client.delete(f"/api/products/{prod['id']}", headers=admin)
        await client.delete(f"/api/categories/{cat['id']}", headers=admin)


@pytest.mark.asyncio
async def test_online_order_overdue_restores_stock_and_cancels():
    async with app_ctx() as (client, test_app):
        admin = await _admin(client)
        cat, prod, opt = await _make_product(client, admin, stock=5)
        user = await _new_user(client, _S + "ex")

        cart_id = (await client.post(
            "/api/cart", json={"productOptionId": opt["id"], "quantity": 2}, headers=user
        )).json()["id"]
        addr_id = (await client.post(
            "/api/addresses",
            json={"recipientName": "A", "recipientPhone": "0900000011",
                  "province": "HN", "district": "CG", "ward": "DV", "detail": "1 Test"},
            headers=user,
        )).json()["id"]

        order = (await client.post(
            "/api/orders",
            json={"cartIds": [cart_id], "addressId": addr_id, "paymentProvider": "mock_online"},
            headers=user,
        )).json()
        assert await _stock(client, prod["id"]) == 3  # giữ chỗ

        # Lấy ref (chưa thanh toán) rồi mô phỏng quá hạn: gọi job hết hạn với cutoff tương lai
        ref = (await client.post(f"/api/orders/{order['id']}/pay", headers=user)).json()["paymentRef"]
        svc = test_app.get(OrderService)
        n = await svc.expire_overdue_online_orders(
            cutoff=datetime.now(timezone.utc) + timedelta(days=2)
        )
        assert n >= 1

        # Kho được HOÀN LẠI: 5
        assert await _stock(client, prod["id"]) == 5

        # Thanh toán muộn bị từ chối (đơn đã hủy) -> E10509
        r = await client.post("/api/payments/mock/callback", json={"paymentRef": ref, "success": True})
        assert r.status_code == 400
        assert r.json()["errorKey"] == "E10509"
        # Không thể bắt đầu thanh toán lại đơn đã hủy
        r = await client.post(f"/api/orders/{order['id']}/pay", headers=user)
        assert r.status_code == 400

        await client.delete(f"/api/orders/{order['id']}", headers=admin)
        await client.delete(f"/api/addresses/{addr_id}", headers=user)
        await client.delete(f"/api/products/{prod['id']}", headers=admin)
        await client.delete(f"/api/categories/{cat['id']}", headers=admin)


@pytest.mark.asyncio
async def test_cod_order_decrements_stock_immediately():
    async with app_client() as client:
        admin = await _admin(client)
        cat, prod, opt = await _make_product(client, admin, stock=4)
        user = await _new_user(client, _S + "cod")

        cart_id = (await client.post(
            "/api/cart", json={"productOptionId": opt["id"], "quantity": 1}, headers=user
        )).json()["id"]
        addr_id = (await client.post(
            "/api/addresses",
            json={"recipientName": "A", "recipientPhone": "0900000010",
                  "province": "HN", "district": "CG", "ward": "DV", "detail": "1 Test"},
            headers=user,
        )).json()["id"]

        order = (await client.post(
            "/api/orders",
            json={"cartIds": [cart_id], "addressId": addr_id},  # mặc định COD
            headers=user,
        )).json()
        assert await _stock(client, prod["id"]) == 3  # COD trừ ngay

        await client.delete(f"/api/orders/{order['id']}", headers=admin)
        await client.delete(f"/api/addresses/{addr_id}", headers=user)
        await client.delete(f"/api/products/{prod['id']}", headers=admin)
        await client.delete(f"/api/categories/{cat['id']}", headers=admin)


# ── #6 Rate limit ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_login_rate_limited_after_failures():
    async with app_client() as client:
        uname = f"url{_S}"[:20]
        r = await client.post(
            "/api/register",
            json={"username": uname, "email": f"{uname}@ex.test", "password": "Pass@123"},
        )
        assert r.status_code == 201, r.text

        # 5 lần sai -> 401
        for _ in range(5):
            r = await client.post("/api/login", json={"username": uname, "password": "WRONG"})
            assert r.status_code == 401

        # Lần thứ 6 -> 429 (bị chặn), kể cả mật khẩu đúng cũng bị chặn khi đang khóa
        r = await client.post("/api/login", json={"username": uname, "password": "WRONG"})
        assert r.status_code == 429
        assert r.json()["errorKey"] == "E2003"
        r = await client.post("/api/login", json={"username": uname, "password": "Pass@123"})
        assert r.status_code == 429


@pytest.mark.asyncio
async def test_forgot_password_rate_limited():
    async with app_client() as client:
        email = f"rl-{_S}@ex.test"
        for _ in range(3):
            r = await client.post("/api/forgot-password", json={"email": email})
            assert r.status_code == 200, r.text
        r = await client.post("/api/forgot-password", json={"email": email})
        assert r.status_code == 429


# ── Đổi mật khẩu + đăng xuất các phiên khác (giữ phiên hiện tại) ───────────────

@pytest.mark.asyncio
async def test_change_password_logout_other_sessions_keeps_current():
    from app.security.cookies import REFRESH_COOKIE_NAME

    async with app_client() as client:
        uname = f"cp{_S}"[:20]
        r = await client.post(
            "/api/register",
            json={"username": uname, "email": f"{uname}@ex.test", "password": "Pass@123"},
        )
        assert r.status_code == 201, r.text

        # Hai phiên đăng nhập (2 refresh token trong DB)
        r1 = await client.post("/api/login", json={"username": uname, "password": "Pass@123"})
        refresh1 = r1.cookies.get(REFRESH_COOKIE_NAME)
        r2 = await client.post("/api/login", json={"username": uname, "password": "Pass@123"})
        refresh2 = r2.cookies.get(REFRESH_COOKIE_NAME)
        access2 = r2.json()["accessToken"]
        assert refresh1 and refresh2 and refresh1 != refresh2

        # Xóa jar để kiểm soát cookie gửi thủ công cho từng phiên
        client.cookies.clear()

        # Đổi mật khẩu từ PHIÊN 2, tích "đăng xuất các phiên khác"
        r = await client.post(
            "/api/change-password",
            json={"currentPassword": "Pass@123", "newPassword": "NewPass@9",
                  "logoutOtherSessions": True},
            headers={"Authorization": f"Bearer {access2}"},
        )
        assert r.status_code == 200, r.text

        # Phiên 1 bị thu hồi -> refresh thất bại
        client.cookies.clear()
        client.cookies.set(REFRESH_COOKIE_NAME, refresh1)
        r = await client.post("/api/refresh-token")
        assert r.status_code in (400, 401)

        # Phiên hiện tại (phiên 2) vẫn dùng được -> refresh thành công
        client.cookies.clear()
        client.cookies.set(REFRESH_COOKIE_NAME, refresh2)
        r = await client.post("/api/refresh-token")
        assert r.status_code == 200, r.text


# ── #8 Đăng nhập không lộ tài khoản (unknown username -> E1005 như sai mật khẩu) ──

@pytest.mark.asyncio
async def test_login_unknown_username_returns_generic_e1005():
    async with app_client() as client:
        r = await client.post(
            "/api/login", json={"username": f"nouser-{_S}", "password": "whatever"}
        )
        assert r.status_code == 401
        assert r.json()["errorKey"] == "E1005"  # không phải E1004 (không lộ username tồn tại)


# ── #10 Logout hỗ trợ POST (chuẩn REST), vẫn giữ GET ─────────────────────────

@pytest.mark.asyncio
async def test_logout_supports_post():
    async with app_client() as client:
        admin = await _admin(client)
        r = await client.post("/api/logout", headers=admin)
        assert r.status_code == 200, r.text


# ── #12 Đổi tồn kho (đặt đơn) làm mới cache DTO sản phẩm ──────────────────────

@pytest.mark.asyncio
async def test_stock_change_invalidates_product_cache():
    async with app_client() as client:
        admin = await _admin(client)
        cat, prod, opt = await _make_product(client, admin, stock=5)
        user = await _new_user(client, _S + "ci")

        # Nạp cache DTO qua GET /products/{id} (công khai) -> stock 5
        d = (await client.get(f"/api/products/{prod['id']}")).json()
        assert d["stock"] == 5

        cart_id = (await client.post(
            "/api/cart", json={"productOptionId": opt["id"], "quantity": 1}, headers=user
        )).json()["id"]
        addr_id = (await client.post(
            "/api/addresses",
            json={"recipientName": "A", "recipientPhone": "0900000012",
                  "province": "HN", "district": "CG", "ward": "DV", "detail": "1 Test"},
            headers=user,
        )).json()["id"]
        order = (await client.post(
            "/api/orders", json={"cartIds": [cart_id], "addressId": addr_id}, headers=user
        )).json()

        # Cache đã được làm mới -> GET /products/{id} phản ánh tồn kho mới (4), không còn 5 cũ
        d2 = (await client.get(f"/api/products/{prod['id']}")).json()
        assert d2["stock"] == 4

        await client.delete(f"/api/orders/{order['id']}", headers=admin)
        await client.delete(f"/api/addresses/{addr_id}", headers=user)
        await client.delete(f"/api/products/{prod['id']}", headers=admin)
        await client.delete(f"/api/categories/{cat['id']}", headers=admin)


# ── #9 Tính tiền dùng Decimal (không sai số float) ───────────────────────────

def test_compute_discount_uses_decimal_precision():
    from decimal import Decimal

    from app.entity.coupon import Coupon
    from app.service.coupon_service import CouponService

    c = Coupon(
        code="X", discount=15, discount_type="percent",
        max_discount=None, min_order_amount=0, applies_to="product",
    )
    # 15% * 12345 = 1851.75 (đúng 2 chữ số, kiểu Decimal)
    product_discount, ship_discount = CouponService.compute_discount(c, 12345, 30000)
    assert product_discount == Decimal("1851.75")
    assert isinstance(product_discount, Decimal)
    assert ship_discount == Decimal("0")
