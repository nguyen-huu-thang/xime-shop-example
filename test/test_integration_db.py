"""
Test tích hợp với DB thật - bao gồm test 4.17, 5.9-5.10, 6.11, 7.12, 8.7.

Chạy: pytest test/test_integration_db.py -v -s

Yêu cầu: DB shop phải đang chạy và đã seed (python -m app.seed).
Test dùng ASGITransport → không cần start server riêng.
"""
import uuid
from contextlib import asynccontextmanager

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import app.config.web  # noqa: F401 - side effect: configure_controllers + openapi
from app.config.dependency import dependency
from app.shop_web_adapter import ShopWebAdapter
from xime.testing import TestApplication

# Unique suffix per run to avoid name collision from previous failed runs
# Hậu tố duy nhất mỗi lần chạy để tránh trùng tên từ lần chạy trước bị lỗi
_S = uuid.uuid4().hex[:6]


# ── Context manager: TestApplication + lifespan + client ─────────────────────
# Routes chỉ được đăng ký khi lifespan_context chạy - phải dùng `async with lifespan_context`.

@asynccontextmanager
async def app_client():
    """Trả về AsyncClient đã qua lifespan (routes đã đăng ký)."""
    async with TestApplication(binding=dependency) as test_app:
        fastapi_app = ShopWebAdapter().build_app(test_app)
        async with fastapi_app.router.lifespan_context(fastapi_app):
            transport = ASGITransport(app=fastapi_app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                yield client


async def _login(client) -> dict:
    resp = await client.post("/api/login", json={"username": "admin", "password": "Admin@123"})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token = resp.json()["accessToken"]
    return {"Authorization": f"Bearer {token}"}


# ─────────────────────────────────────────────────────────────────────────────
# 4.17 - Phân quyền
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_4_17_login_success():
    """Admin login trả access token (body) + refresh token (httpOnly cookie path-scoped)."""
    async with app_client() as client:
        resp = await client.post("/api/login", json={"username": "admin", "password": "Admin@123"})
    assert resp.status_code == 200
    data = resp.json()
    assert "accessToken" in data
    # Refresh token KHÔNG nằm trong body (chỉ trong cookie httpOnly)
    # Refresh token must NOT be in the body (cookie-only)
    assert "refreshToken" not in data
    # Cookie refresh được đặt, httpOnly, path-scoped tới /api/refresh-token
    # Refresh cookie is set, httpOnly, scoped to /api/refresh-token
    set_cookie = resp.headers.get("set-cookie", "")
    assert "refreshToken=" in set_cookie
    assert "httponly" in set_cookie.lower()
    assert "/api/refresh-token" in set_cookie
    print(f"\n[4.17] ✓ Login OK - token[:30]: {data['accessToken'][:30]}...")


@pytest.mark.asyncio
async def test_4_17_refresh_token_rotation():
    """Refresh qua cookie: cấp access mới + xoay refresh cookie mới; thiếu cookie -> E2050."""
    async with app_client() as client:
        login = await client.post("/api/login", json={"username": "admin", "password": "Admin@123"})
        assert login.status_code == 200
        first_cookie = login.headers.get("set-cookie", "")

        # Có cookie (AsyncClient tự giữ cookie) -> refresh thành công, cấp access mới + xoay refresh
        resp = await client.post("/api/refresh-token")
        assert resp.status_code == 200, resp.text
        assert "accessToken" in resp.json()
        rotated_cookie = resp.headers.get("set-cookie", "")
        assert "refreshToken=" in rotated_cookie
        assert "/api/refresh-token" in rotated_cookie
        assert rotated_cookie != first_cookie  # refresh token đã được xoay

    # Không có cookie -> E2050
    async with app_client() as client:
        resp = await client.post("/api/refresh-token")
        assert resp.status_code == 401
        assert resp.json()["errorKey"] == "E2050"
    print("[4.17] ✓ Refresh rotation OK + missing cookie -> E2050")


@pytest.mark.asyncio
async def test_4_17_wrong_password_returns_e1005():
    """Sai mật khẩu → E1005."""
    async with app_client() as client:
        resp = await client.post("/api/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401
    assert resp.json()["errorKey"] == "E1005"
    print("[4.17] ✓ Wrong password → E1005")


@pytest.mark.asyncio
async def test_4_17_no_token_returns_401():
    """Gọi API cần quyền mà không có token → 401."""
    async with app_client() as client:
        resp = await client.get("/api/permission")  # requires require_login()
    assert resp.status_code == 401
    print("[4.17] ✓ No token → 401")


@pytest.mark.asyncio
async def test_4_17_list_permissions():
    """Admin có thể xem danh sách quyền."""
    async with app_client() as client:
        headers = await _login(client)
        resp = await client.get("/api/permission", headers=headers)
    assert resp.status_code == 200
    perms = resp.json()
    assert len(perms) >= 51
    print(f"[4.17] ✓ Permissions: {len(perms)} quyền")


@pytest.mark.asyncio
async def test_4_17_list_groups():
    """Admin có thể xem danh sách nhóm."""
    async with app_client() as client:
        headers = await _login(client)
        resp = await client.get("/api/group", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    print(f"[4.17] ✓ Groups: {data}")


@pytest.mark.asyncio
async def test_4_17_logout():
    """Đăng xuất thành công."""
    async with app_client() as client:
        headers = await _login(client)
        resp = await client.get("/api/logout", headers=headers)
    assert resp.status_code == 200
    print(f"[4.17] ✓ Logout: {resp.json()}")


# ─────────────────────────────────────────────────────────────────────────────
# 5.9 - Category CRUD
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_5_09_category_crud():
    """Tạo, xem, sửa, xóa category."""
    async with app_client() as client:
        headers = await _login(client)

        # Create
        resp = await client.post(
            "/api/categories",
            json={"name": f"Test Category 509 {_S}", "description": "Mô tả test"},
            headers=headers,
        )
        assert resp.status_code == 201, f"Create: {resp.text}"
        cat = resp.json()
        cat_id = cat["id"]
        print(f"\n[5.9] ✓ Create category id={cat_id}, name={cat['name']}")

        # Read
        resp = await client.get(f"/api/categories/{cat_id}", headers=headers)
        assert resp.status_code == 200

        # Update
        resp = await client.put(
            f"/api/categories/{cat_id}",
            json={"name": "Updated Category 509"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Category 509"
        print(f"[5.9] ✓ Update category OK")

        # Delete
        resp = await client.delete(f"/api/categories/{cat_id}", headers=headers)
        assert resp.status_code == 200
        print(f"[5.9] ✓ Delete category OK")

        # Verify deleted
        resp = await client.get(f"/api/categories/{cat_id}", headers=headers)
        assert resp.status_code in (404, 400)
    print("[5.9] ✓ Category CRUD hoàn tất")


@pytest.mark.asyncio
async def test_5_09_category_hierarchy():
    """Tạo category cha-con, kiểm hierarchy_path."""
    async with app_client() as client:
        headers = await _login(client)

        # Parent
        resp = await client.post("/api/categories", json={"name": f"Parent 509 {_S}"}, headers=headers)
        assert resp.status_code == 201
        parent_id = resp.json()["id"]

        # Child
        resp = await client.post(
            "/api/categories",
            json={"name": f"Child 509 {_S}", "parentId": parent_id},
            headers=headers,
        )
        assert resp.status_code == 201
        child = resp.json()
        child_id = child["id"]
        hierarchy = child.get("hierarchy_path", "")
        print(f"\n[5.9] ✓ Hierarchy: '{hierarchy}'")
        assert "Parent 509" in hierarchy

        # Cleanup
        await client.delete(f"/api/categories/{child_id}", headers=headers)
        await client.delete(f"/api/categories/{parent_id}", headers=headers)
    print("[5.9] ✓ Hierarchy test hoàn tất")


# ─────────────────────────────────────────────────────────────────────────────
# 5.10 - Product CRUD
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_5_10_product_crud():
    """Tạo, xem, sửa, soft-delete sản phẩm."""
    async with app_client() as client:
        headers = await _login(client)

        # Tạo category
        resp = await client.post("/api/categories", json={"name": f"Cat for Product 510 {_S}"}, headers=headers)
        assert resp.status_code == 201
        cat_id = resp.json()["id"]

        # Create product
        resp = await client.post(
            "/api/products",
            json={
                "name": f"Test Product 510 {_S}",
                "categoryId": cat_id,
                "locationAddress": "Kho Hà Nội",
                "description": "Mô tả SP test",
                "price": 100000,
                "stock": 50,
                "discountPercentage": 0,
            },
            headers=headers,
        )
        assert resp.status_code == 201, f"Create product: {resp.text}"
        prod = resp.json()
        prod_id = prod["id"]
        print(f"\n[5.10] ✓ Create product id={prod_id}, price={prod.get('price')}, stock={prod.get('stock')}")

        # Read
        resp = await client.get(f"/api/products/{prod_id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == prod_id

        # Update
        resp = await client.put(
            f"/api/products/{prod_id}",
            json={"name": "Updated Product 510", "price": 120000},
            headers=headers,
        )
        assert resp.status_code == 200
        print(f"[5.10] ✓ Update product OK")

        # Soft delete
        resp = await client.delete(f"/api/products/{prod_id}", headers=headers)
        assert resp.status_code == 200
        print(f"[5.10] ✓ Soft delete product OK")

        # Cleanup
        await client.delete(f"/api/categories/{cat_id}", headers=headers)
    print("[5.10] ✓ Product CRUD hoàn tất")


# ─────────────────────────────────────────────────────────────────────────────
# 6.11 - Cart + Order end-to-end
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_6_11_cart_order_flow():
    """Tạo SP → thêm giỏ → đặt hàng → kiểm order + details + tồn kho giảm."""
    async with app_client() as client:
        headers = await _login(client)

        # Tạo category + product
        resp = await client.post("/api/categories", json={"name": f"Cat for Order 611 {_S}"}, headers=headers)
        cat_id = resp.json()["id"]

        resp = await client.post(
            "/api/products",
            json={
                "name": f"Order Test Product 611 {_S}",
                "categoryId": cat_id,
                "locationAddress": "Kho HCM",
                "description": "SP dùng test đặt hàng",
                "price": 200000,
                "stock": 10,
                "discountPercentage": 0,
            },
            headers=headers,
        )
        assert resp.status_code == 201, f"Create product: {resp.text}"
        prod_id = resp.json()["id"]
        print(f"\n[6.11] Product id={prod_id}")

        # Lấy default option
        resp = await client.get(f"/api/products/{prod_id}/option-default", headers=headers)
        assert resp.status_code == 200, f"Get option: {resp.text}"
        opt = resp.json()
        opt_id = opt["id"]
        initial_stock = opt["stock"]
        print(f"[6.11] Option id={opt_id}, stock={initial_stock}")

        # Thêm vào giỏ
        resp = await client.post(
            "/api/cart",
            json={"productOptionId": opt_id, "quantity": 2},
            headers=headers,
        )
        assert resp.status_code == 201, f"Add to cart: {resp.text}"
        cart_id = resp.json()["id"]
        print(f"[6.11] Cart item id={cart_id}")

        # Xem giỏ
        resp = await client.get("/api/cart", headers=headers)
        assert resp.status_code == 200
        cart_items = resp.json()
        assert any(i["id"] == cart_id for i in cart_items)
        print(f"[6.11] ✓ Cart: {len(cart_items)} item(s)")

        # Đặt hàng
        resp = await client.post(
            "/api/orders",
            json={"cartIds": [cart_id], "address": "123 Đường Test, Hà Nội"},
            headers=headers,
        )
        assert resp.status_code == 201, f"Create order: {resp.text}"
        order = resp.json()
        order_id = order["id"]
        print(f"[6.11] ✓ Order id={order_id}, total={order['totalAmount']}")
        assert len(order["details"]) > 0
        print(f"[6.11]   Details: {order['details']}")

        # Kiểm tồn kho giảm
        resp = await client.get(f"/api/products/{prod_id}/option-default", headers=headers)
        assert resp.status_code == 200
        new_stock = resp.json()["stock"]
        assert new_stock == initial_stock - 2, f"Stock: expected {initial_stock-2}, got {new_stock}"
        print(f"[6.11] ✓ Tồn kho: {initial_stock} → {new_stock} (giảm 2)")

        # Kiểm cart bị xóa
        resp = await client.get("/api/cart", headers=headers)
        cart_after = resp.json()
        assert not any(i["id"] == cart_id for i in cart_after)
        print(f"[6.11] ✓ Cart cleared sau order")

        # Xóa order
        resp = await client.delete(f"/api/orders/{order_id}", headers=headers)
        assert resp.status_code == 200

        # Cleanup
        await client.delete(f"/api/products/{prod_id}", headers=headers)
        await client.delete(f"/api/categories/{cat_id}", headers=headers)
    print("[6.11] ✓ Cart+Order end-to-end hoàn tất")


# ─────────────────────────────────────────────────────────────────────────────
# 7.12 - Review, Wishlist, Notification
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_7_12_review_flow():
    """Tạo SP → tạo review → duyệt → liệt kê → xóa."""
    async with app_client() as client:
        headers = await _login(client)

        resp = await client.post("/api/categories", json={"name": f"Cat Review 712 {_S}"}, headers=headers)
        cat_id = resp.json()["id"]
        resp = await client.post(
            "/api/products",
            json={"name": f"Review SP 712 {_S}", "categoryId": cat_id, "locationAddress": "HN",
                  "price": 50000, "stock": 5},
            headers=headers,
        )
        prod_id = resp.json()["id"]

        # Tạo review (userId=1 = admin)
        resp = await client.post(
            "/api/reviews",
            json={"userId": 1, "productId": prod_id, "rating": 5, "comment": "Tuyệt vời!"},
            headers=headers,
        )
        assert resp.status_code == 201, f"Create review: {resp.text}"
        review = resp.json()
        review_id = review["id"]
        assert review["is_approved"] == False
        print(f"\n[7.12] Review id={review_id}, approved={review['is_approved']}")

        # Duyệt
        resp = await client.patch(f"/api/reviews/{review_id}/approve", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["is_approved"] == True
        print(f"[7.12] ✓ Approve review")

        # Liệt kê
        resp = await client.get("/api/reviews", headers=headers)
        assert resp.status_code == 200
        assert any(r["id"] == review_id for r in resp.json())
        print(f"[7.12] ✓ Reviews list: {len(resp.json())} item(s)")

        # Hủy duyệt
        resp = await client.patch(f"/api/reviews/{review_id}/disapprove", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["is_approved"] == False
        print(f"[7.12] ✓ Disapprove review")

        # Xóa
        resp = await client.delete(f"/api/reviews/{review_id}", headers=headers)
        assert resp.status_code == 200

        # Cleanup
        await client.delete(f"/api/products/{prod_id}", headers=headers)
        await client.delete(f"/api/categories/{cat_id}", headers=headers)
    print("[7.12] ✓ Review flow hoàn tất")


@pytest.mark.asyncio
async def test_7_12_wishlist_flow():
    """Tạo SP → thêm wishlist → xem → xóa."""
    async with app_client() as client:
        headers = await _login(client)

        resp = await client.post("/api/categories", json={"name": f"Cat Wishlist 712 {_S}"}, headers=headers)
        cat_id = resp.json()["id"]
        resp = await client.post(
            "/api/products",
            json={"name": f"Wishlist SP 712 {_S}", "categoryId": cat_id, "locationAddress": "HN",
                  "price": 80000, "stock": 3},
            headers=headers,
        )
        prod_id = resp.json()["id"]

        # Thêm wishlist
        resp = await client.post("/api/wishlist", json={"productId": prod_id}, headers=headers)
        assert resp.status_code == 201, f"Add wishlist: {resp.text}"
        wl_id = resp.json()["id"]
        print(f"\n[7.12] Wishlist id={wl_id}")

        # Xem wishlist user (products)
        resp = await client.get("/api/wishlist", headers=headers)
        assert resp.status_code == 200
        items = resp.json()
        assert any(p.get("id") == prod_id for p in items)
        print(f"[7.12] ✓ User wishlist: {len(items)} product(s)")

        # Xóa
        resp = await client.delete(f"/api/wishlist/{wl_id}", headers=headers)
        assert resp.status_code == 200

        # Cleanup
        await client.delete(f"/api/products/{prod_id}", headers=headers)
        await client.delete(f"/api/categories/{cat_id}", headers=headers)
    print("[7.12] ✓ Wishlist flow hoàn tất")


@pytest.mark.asyncio
async def test_7_12_notification_flow():
    """Tạo notification → đánh dấu đã đọc → kiểm unread."""
    async with app_client() as client:
        headers = await _login(client)

        # Tạo
        resp = await client.post(
            "/api/notifications",
            json={"userId": 1, "title": "Test Notif 712", "message": "Nội dung test", "type": "push"},
            headers=headers,
        )
        assert resp.status_code == 201, f"Create: {resp.text}"
        notif = resp.json()
        notif_id = notif["id"]
        assert notif["is_read"] == False
        print(f"\n[7.12] Notification id={notif_id}")

        # Đánh dấu đã đọc
        resp = await client.patch(f"/api/notifications/{notif_id}/read", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["is_read"] == True
        print(f"[7.12] ✓ Mark as read")

        # Kiểm unread không còn
        resp = await client.get("/api/notifications/unread", headers=headers)
        unread = resp.json()
        assert not any(n["id"] == notif_id for n in unread)
        print(f"[7.12] ✓ Unread không còn notification này")

        # Xóa
        await client.delete(f"/api/notifications/{notif_id}", headers=headers)
    print("[7.12] ✓ Notification flow hoàn tất")


# ─────────────────────────────────────────────────────────────────────────────
# 8.7 - Search
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_8_07_search_products():
    """Tìm kiếm sản phẩm theo từ khóa, kiểm kết quả và relevance."""
    async with app_client() as client:
        headers = await _login(client)

        resp = await client.post("/api/categories", json={"name": f"Cat Search 807 {_S}"}, headers=headers)
        cat_id = resp.json()["id"]

        # Tạo SP với từ khóa đặc biệt
        resp = await client.post(
            "/api/products",
            json={
                "name": f"Điện thoại XIMETEST807{_S}",
                "categoryId": cat_id,
                "locationAddress": "Kho HN",
                "description": f"Điện thoại thông minh XIMETEST807{_S} giá rẻ",
                "price": 5000000,
                "stock": 20,
            },
            headers=headers,
        )
        assert resp.status_code == 201
        prod_id = resp.json()["id"]

        # Search khớp
        resp = await client.get(f"/api/search/products?keywords=XIMETEST807{_S}", headers=headers)
        assert resp.status_code == 200, f"Search: {resp.text}"
        result = resp.json()
        print(f"\n[8.7] Search 'XIMETEST807{_S}': total={result['total']}")
        assert result["total"] >= 1
        first = result["results"][0]
        print(f"[8.7] Top result: name='{first['product']['name']}', score={first['relevanceScore']}")
        assert first["relevanceScore"] >= 5  # name match = +5 minimum

        # Search không khớp
        resp = await client.get("/api/search/products?keywords=NORESULT999XYZ", headers=headers)
        assert resp.json()["total"] == 0
        print(f"[8.7] ✓ No-match search trả 0 kết quả")

        # Filter giá
        resp = await client.get(
            f"/api/search/products?keywords=XIMETEST807{_S}&max_price=1000000", headers=headers
        )
        assert resp.json()["total"] == 0  # giá 5000000 > 1000000
        print(f"[8.7] ✓ Price filter loại SP đắt")

        # Keywords rỗng → lỗi
        resp = await client.get("/api/search/products", headers=headers)
        assert resp.status_code in (400, 422)
        print(f"[8.7] ✓ Empty keywords → {resp.status_code}")

        # Cleanup
        await client.delete(f"/api/products/{prod_id}", headers=headers)
        await client.delete(f"/api/categories/{cat_id}", headers=headers)
    print("[8.7] ✓ Search test hoàn tất")


# ─────────────────────────────────────────────────────────────────────────────
# F1 - Storage starter: upload + stream download (HTTP Range)
# ─────────────────────────────────────────────────────────────────────────────

# PNG 1x1 hợp lệ (header + IHDR + IDAT + IEND), đủ để stream/Range.
_PNG_1x1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6300010000050001"
    "0d0a2db40000000049454e44ae426082"
)


@pytest.mark.asyncio
async def test_f1_file_upload_and_stream_download():
    """Upload qua storage starter -> tải lại qua /media (200 + Range 206) -> xóa."""
    async with app_client() as client:
        headers = await _login(client)

        # Upload multipart
        resp = await client.post(
            "/api/files",
            files={"file": ("pixel.png", _PNG_1x1, "image/png")},
            data={"description": f"F1 test {_S}"},
            headers=headers,
        )
        assert resp.status_code == 201, f"Upload: {resp.text}"
        file_id = resp.json()["id"]
        file_path = resp.json()["file"]
        print(f"\n[F1] Uploaded -> id={file_id}, key={file_path}")

        # Tải lại đầy đủ qua /media (public, không cần header)
        resp = await client.get(f"/media/{file_path}")
        assert resp.status_code == 200, f"Download: {resp.status_code}"
        assert resp.content == _PNG_1x1
        assert resp.headers.get("accept-ranges") == "bytes"
        print(f"[F1] ✓ Download 200, {len(resp.content)} bytes, content khớp")

        # HTTP Range -> 206 Partial Content
        resp = await client.get(f"/media/{file_path}", headers={"Range": "bytes=0-3"})
        assert resp.status_code == 206, f"Range: {resp.status_code}"
        assert resp.content == _PNG_1x1[:4]
        assert "content-range" in {k.lower() for k in resp.headers}
        print(f"[F1] ✓ Range bytes=0-3 -> 206, {len(resp.content)} bytes")

        # Xóa file (id lấy thẳng từ response upload)
        resp = await client.delete(f"/api/files/{file_id}", headers=headers)
        assert resp.status_code == 200, f"Delete: {resp.text}"

        # Sau khi xóa: object không còn -> 404
        resp = await client.get(f"/media/{file_path}")
        assert resp.status_code == 404
        print(f"[F1] ✓ Sau khi xóa -> /media trả 404")
    print("[F1] ✓ Storage upload/stream/delete hoàn tất")


# ─────────────────────────────────────────────────────────────────────────────
# F2 - Cache catalog: đọc detail có cache, update -> invalidate
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_f2_product_cache_invalidation():
    """GET detail (cache) -> update tên -> GET lại phải thấy tên mới (cache đã invalidate)."""
    async with app_client() as client:
        headers = await _login(client)

        resp = await client.post("/api/categories", json={"name": f"Cat Cache F2 {_S}"}, headers=headers)
        cat_id = resp.json()["id"]

        old_name = f"Product Cache F2 {_S}"
        resp = await client.post(
            "/api/products",
            json={
                "name": old_name,
                "categoryId": cat_id,
                "locationAddress": "Kho HN",
                "description": "SP test cache",
                "price": 100000,
                "stock": 5,
            },
            headers=headers,
        )
        assert resp.status_code == 201, f"Create: {resp.text}"
        prod_id = resp.json()["id"]

        # Đọc detail 2 lần (lần 2 phục vụ từ cache) - cùng kết quả
        r1 = await client.get(f"/api/products/{prod_id}", headers=headers)
        r2 = await client.get(f"/api/products/{prod_id}", headers=headers)
        assert r1.status_code == 200 and r2.status_code == 200
        assert r1.json()["name"] == old_name == r2.json()["name"]
        print(f"\n[F2] ✓ Đọc detail 2 lần khớp (lần 2 từ cache)")

        # Update tên -> phải invalidate cache
        new_name = f"Product Cache F2 UPDATED {_S}"
        resp = await client.put(
            f"/api/products/{prod_id}", json={"name": new_name}, headers=headers
        )
        assert resp.status_code == 200, f"Update: {resp.text}"

        # Đọc lại: nếu cache không invalidate sẽ vẫn trả tên cũ -> phải là tên mới
        r3 = await client.get(f"/api/products/{prod_id}", headers=headers)
        assert r3.json()["name"] == new_name, "Cache không được invalidate sau update!"
        print(f"[F2] ✓ Sau update, detail trả tên mới (cache invalidated)")

        # Cleanup
        await client.delete(f"/api/products/{prod_id}", headers=headers)
        await client.delete(f"/api/categories/{cat_id}", headers=headers)
    print("[F2] ✓ Cache invalidation hoàn tất")


# ─────────────────────────────────────────────────────────────────────────────
# F3 - Dashboard thống kê
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_f3_dashboard_stats():
    """GET /api/dashboard/stats (cần quyền) trả đủ trường số liệu."""
    async with app_client() as client:
        headers = await _login(client)
        resp = await client.get("/api/dashboard/stats", headers=headers)
        assert resp.status_code == 200, f"Stats: {resp.text}"
        data = resp.json()
        for field in (
            "revenuePaid", "totalOrders", "ordersToday", "unpaidOrders",
            "totalProducts", "lowStockOptions", "totalUsers", "totalReviews",
            "topProducts",
        ):
            assert field in data, f"Thiếu trường {field}"
        assert isinstance(data["topProducts"], list)
        assert data["totalUsers"] >= 1  # ít nhất có admin
        print(f"\n[F3] ✓ Dashboard stats: orders={data['totalOrders']}, "
              f"users={data['totalUsers']}, topProducts={len(data['topProducts'])}")

    # Chưa đăng nhập -> 401
    async with app_client() as client:
        resp = await client.get("/api/dashboard/stats")
        assert resp.status_code == 401
        print("[F3] ✓ Chưa đăng nhập -> 401")
