"""
Test cho phần Checkout + Thông báo (địa chỉ, coupon nâng cấp, tính tiền, thanh toán giả lập,
hộp thư thông báo).

- Unit test: pricing + CouponService.compute_discount (thuần, không cần DB).
- Integration test: dùng DB thật (giống test_integration_db.py). Yêu cầu DB đã seed.
"""
import uuid
from contextlib import asynccontextmanager

import pytest
import pytest_asyncio  # noqa: F401
from httpx import ASGITransport, AsyncClient

import app.config.web  # noqa: F401 - side effect: configure_controllers + openapi
from app.config.dependency import dependency
from app.entity.coupon import Coupon
from app.service import pricing
from app.service.coupon_service import CouponService
from xime.adapters.web import WebAdapter
from xime.testing import TestApplication

_S = uuid.uuid4().hex[:6]


# ─────────────────────────────────────────────────────────────────────────────
# Unit: pricing (không cần DB)
# ─────────────────────────────────────────────────────────────────────────────

def test_shipping_fee_flat_and_freeship():
    assert pricing.shipping_fee(0) == pricing.DEFAULT_SHIPPING_FEE
    assert pricing.shipping_fee(pricing.FREE_SHIP_THRESHOLD - 1) == pricing.DEFAULT_SHIPPING_FEE
    assert pricing.shipping_fee(pricing.FREE_SHIP_THRESHOLD) == 0.0
    assert pricing.shipping_fee(pricing.FREE_SHIP_THRESHOLD + 100000) == 0.0


def test_order_total_basic_and_clamp():
    # subtotal + ship - product_discount - ship_discount
    assert pricing.order_total(100000, 30000, 20000, 0) == 110000
    assert pricing.order_total(300000, 0, 0, 0) == 300000
    # Không âm
    assert pricing.order_total(10, 0, 100, 0) == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Unit: CouponService.compute_discount (thuần)
# ─────────────────────────────────────────────────────────────────────────────

def _coupon(**kw) -> Coupon:
    base = dict(
        code="X",
        discount=0,
        discount_type="fixed",
        max_discount=None,
        min_order_amount=0,
        applies_to="product",
    )
    base.update(kw)
    return Coupon(**base)


def test_compute_fixed_product():
    c = _coupon(discount=50000, discount_type="fixed", applies_to="product")
    assert CouponService.compute_discount(c, 300000, 30000) == (50000.0, 0.0)


def test_compute_fixed_product_clamped_to_subtotal():
    c = _coupon(discount=400000, discount_type="fixed", applies_to="product")
    assert CouponService.compute_discount(c, 300000, 30000) == (300000.0, 0.0)


def test_compute_percent_product_with_cap():
    c = _coupon(discount=20, discount_type="percent", max_discount=100000, applies_to="product")
    # 20% * 1,000,000 = 200,000 -> trần 100,000
    assert CouponService.compute_discount(c, 1000000, 30000) == (100000.0, 0.0)


def test_compute_percent_product_no_cap():
    c = _coupon(discount=10, discount_type="percent", applies_to="product")
    assert CouponService.compute_discount(c, 200000, 30000) == (20000.0, 0.0)


def test_compute_fixed_shipping_clamped():
    c = _coupon(discount=50000, discount_type="fixed", applies_to="shipping")
    # giảm ship không vượt quá phí ship
    assert CouponService.compute_discount(c, 300000, 30000) == (0.0, 30000.0)


def test_compute_percent_shipping():
    c = _coupon(discount=50, discount_type="percent", applies_to="shipping")
    assert CouponService.compute_discount(c, 300000, 30000) == (0.0, 15000.0)


# ─────────────────────────────────────────────────────────────────────────────
# Integration: cần DB (giống test_integration_db.py)
# ─────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def app_client():
    async with TestApplication(binding=dependency) as test_app:
        fastapi_app = WebAdapter().build_app(test_app)
        async with fastapi_app.router.lifespan_context(fastapi_app):
            transport = ASGITransport(app=fastapi_app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                yield client


async def _login(client) -> dict:
    resp = await client.post("/api/login", json={"username": "admin", "password": "Admin@123"})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['accessToken']}"}


@pytest.mark.asyncio
async def test_address_book_crud_and_default():
    async with app_client() as client:
        headers = await _login(client)

        # Tạo địa chỉ a1 (kèm tọa độ) - lưu đúng lat/lng
        r = await client.post(
            "/api/addresses",
            json={
                "recipientName": "A", "recipientPhone": "0900000001",
                "province": "HN", "district": "CG", "ward": "DV", "detail": "1 Test",
                "lat": 21.0285, "lng": 105.8542,
            },
            headers=headers,
        )
        assert r.status_code == 201, r.text
        a1 = r.json()
        assert a1["lat"] == 21.0285
        assert a1["lng"] == 105.8542

        # Địa chỉ a2
        r = await client.post(
            "/api/addresses",
            json={
                "recipientName": "B", "recipientPhone": "0900000002",
                "province": "HN", "district": "BD", "ward": "X", "detail": "2 Test",
            },
            headers=headers,
        )
        a2 = r.json()

        # Đặt a1 làm mặc định -> chỉ a1 mặc định (không phụ thuộc địa chỉ tồn trước đó)
        await client.put(f"/api/addresses/{a1['id']}/default", headers=headers)
        by_id = {a["id"]: a for a in (await client.get("/api/addresses", headers=headers)).json()}
        assert by_id[a1["id"]]["isDefault"] is True
        assert by_id[a2["id"]]["isDefault"] is False

        # Đặt a2 làm mặc định -> a1 hết mặc định (chỉ 1 mặc định tại một thời điểm)
        r = await client.put(f"/api/addresses/{a2['id']}/default", headers=headers)
        assert r.status_code == 200
        by_id = {a["id"]: a for a in (await client.get("/api/addresses", headers=headers)).json()}
        assert by_id[a2["id"]]["isDefault"] is True
        assert by_id[a1["id"]]["isDefault"] is False

        # Dọn dẹp
        await client.delete(f"/api/addresses/{a1['id']}", headers=headers)
        await client.delete(f"/api/addresses/{a2['id']}", headers=headers)


@pytest.mark.asyncio
async def test_address_not_owned_returns_404():
    async with app_client() as client:
        headers = await _login(client)
        # Id không tồn tại -> E10320
        r = await client.put("/api/addresses/99999999/default", headers=headers)
        assert r.status_code == 404
        assert r.json()["errorKey"] == "E10320"


@pytest.mark.asyncio
async def test_order_preview_with_percent_coupon():
    async with app_client() as client:
        headers = await _login(client)

        # Tạo danh mục + sản phẩm có tồn kho
        cat = (await client.post(
            "/api/categories", json={"name": f"cat-{_S}"}, headers=headers
        )).json()
        prod = (await client.post(
            "/api/products",
            json={"name": f"prod-{_S}", "categoryId": cat["id"], "locationAddress": "HN",
                  "price": 100000, "stock": 10},
            headers=headers,
        )).json()
        opt = (await client.get(f"/api/products/{prod['id']}/option-default", headers=headers)).json()
        cart_id = (await client.post(
            "/api/cart", json={"productOptionId": opt["id"], "quantity": 2}, headers=headers
        )).json()["id"]

        # Coupon percent 10% trên tiền hàng
        code = f"P10-{_S}"
        await client.post(
            "/api/coupons",
            json={
                "code": code, "discount": 10, "discountType": "percent",
                "appliesTo": "product",
                "startDate": "2020-01-01T00:00:00+00:00",
                "endDate": "2099-01-01T00:00:00+00:00",
            },
            headers=headers,
        )

        # Preview: subtotal = 200,000 -> ship freeship? 200k < 500k nên ship = 30k.
        # product_discount = 10% * 200,000 = 20,000. total = 200000 + 30000 - 20000 = 210000.
        r = await client.post(
            "/api/orders/preview",
            json={"cartIds": [cart_id], "couponCode": code},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["subtotal"] == 200000
        assert body["shippingFee"] == 30000
        assert body["productDiscount"] == 20000
        assert body["total"] == 210000
        assert body["couponApplied"] is True

        # Dọn dẹp
        await client.delete(f"/api/cart/{cart_id}", headers=headers)
        await client.delete(f"/api/products/{prod['id']}", headers=headers)
        await client.delete(f"/api/categories/{cat['id']}", headers=headers)


@pytest.mark.asyncio
async def test_create_order_mock_online_payment_flow():
    async with app_client() as client:
        headers = await _login(client)

        cat = (await client.post(
            "/api/categories", json={"name": f"cat2-{_S}"}, headers=headers
        )).json()
        prod = (await client.post(
            "/api/products",
            json={"name": f"prod2-{_S}", "categoryId": cat["id"], "locationAddress": "HN",
                  "price": 250000, "stock": 5},
            headers=headers,
        )).json()
        opt = (await client.get(f"/api/products/{prod['id']}/option-default", headers=headers)).json()
        cart_id = (await client.post(
            "/api/cart", json={"productOptionId": opt["id"], "quantity": 1}, headers=headers
        )).json()["id"]
        addr_id = (await client.post(
            "/api/addresses",
            json={
                "recipientName": "A", "recipientPhone": "0900000003",
                "province": "HN", "district": "CG", "ward": "DV", "detail": "1 Test",
            },
            headers=headers,
        )).json()["id"]

        # Đặt đơn online giả lập -> chưa thanh toán
        r = await client.post(
            "/api/orders",
            json={"cartIds": [cart_id], "addressId": addr_id, "paymentProvider": "mock_online"},
            headers=headers,
        )
        assert r.status_code == 201, r.text
        order = r.json()
        assert order["paymentStatus"] is False

        # Bắt đầu thanh toán -> nhận payment_ref
        r = await client.post(f"/api/orders/{order['id']}/pay", headers=headers)
        assert r.status_code == 200, r.text
        ref = r.json()["paymentRef"]
        assert ref

        # Callback giả lập thành công -> đã thanh toán
        r = await client.post(
            "/api/payments/mock/callback", json={"paymentRef": ref, "success": True}
        )
        assert r.status_code == 200, r.text
        assert r.json()["paymentStatus"] is True

        # Callback lần 2 -> E10509 (đã xử lý)
        r = await client.post(
            "/api/payments/mock/callback", json={"paymentRef": ref, "success": True}
        )
        assert r.status_code == 400
        assert r.json()["errorKey"] == "E10509"

        # Dọn dẹp
        await client.delete(f"/api/orders/{order['id']}", headers=headers)
        await client.delete(f"/api/addresses/{addr_id}", headers=headers)
        await client.delete(f"/api/products/{prod['id']}", headers=headers)
        await client.delete(f"/api/categories/{cat['id']}", headers=headers)


@pytest.mark.asyncio
async def test_notification_inbox_and_order_event():
    async with app_client() as client:
        headers = await _login(client)

        # Đếm chưa đọc ban đầu
        before = (await client.get("/api/notifications/me/unread-count", headers=headers)).json()["count"]

        # Tạo đơn COD -> sinh 1 thông báo "Đặt hàng thành công"
        cat = (await client.post(
            "/api/categories", json={"name": f"cat3-{_S}"}, headers=headers
        )).json()
        prod = (await client.post(
            "/api/products",
            json={"name": f"prod3-{_S}", "categoryId": cat["id"], "locationAddress": "HN",
                  "price": 100000, "stock": 5},
            headers=headers,
        )).json()
        opt = (await client.get(f"/api/products/{prod['id']}/option-default", headers=headers)).json()
        cart_id = (await client.post(
            "/api/cart", json={"productOptionId": opt["id"], "quantity": 1}, headers=headers
        )).json()["id"]
        addr_id = (await client.post(
            "/api/addresses",
            json={
                "recipientName": "A", "recipientPhone": "0900000004",
                "province": "HN", "district": "CG", "ward": "DV", "detail": "1 Test",
            },
            headers=headers,
        )).json()["id"]
        order = (await client.post(
            "/api/orders",
            json={"cartIds": [cart_id], "addressId": addr_id},
            headers=headers,
        )).json()

        # Hộp thư của tôi có thông báo mới, đếm chưa đọc tăng
        after = (await client.get("/api/notifications/me/unread-count", headers=headers)).json()["count"]
        assert after >= before + 1
        mine = (await client.get("/api/notifications/me", headers=headers)).json()
        assert any(str(order["id"]) in (n.get("message") or "") for n in mine)

        # Phase B: đổi trạng thái giao -> thông báo in-app + nhánh also_email (email tắt -> bỏ qua an toàn)
        r = await client.put(
            f"/api/orders/{order['id']}/shipping-status",
            json={"status": "Đang giao"},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        mine2 = (await client.get("/api/notifications/me", headers=headers)).json()
        assert any("Đang giao" in (n.get("message") or "") for n in mine2)

        # Dọn dẹp
        await client.delete(f"/api/orders/{order['id']}", headers=headers)
        await client.delete(f"/api/addresses/{addr_id}", headers=headers)
        await client.delete(f"/api/products/{prod['id']}", headers=headers)
        await client.delete(f"/api/categories/{cat['id']}", headers=headers)
