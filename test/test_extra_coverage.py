"""
Test bổ sung độ phủ - các controller/endpoint chưa được test_integration_db.py phủ:

  - Coupon CRUD + validation
  - User management (register, /me, /me/permissions, admin CRUD, bảo vệ admin)
  - Group CRUD
  - Group member flow (add/check/list/remove)
  - Group permission flow (assign/get/update/check/delete)
  - User permission flow (assign/get/update/delete)
  - Security (change-password, verify-password)
  - Product phụ (count, by-category, attribute/option, find-option)
  - Authorization: user thường bị 403 khi gọi endpoint admin
  - Hành vi user bị khóa (deactivated)

Chạy: pytest test/test_extra_coverage.py -v -s
Yêu cầu: DB shop đang chạy + đã seed (python -m app.seed).

Test dùng ASGITransport -> không cần start server riêng. Mỗi resource tạo ra đều được dọn.
"""
import uuid
from contextlib import asynccontextmanager

import pytest

import app.config.web  # noqa: F401 - side effect: configure_controllers + openapi
from app.config.dependency import dependency
from httpx import ASGITransport, AsyncClient
from xime.adapters.web import WebAdapter
from xime.testing import TestApplication

# Hậu tố duy nhất mỗi lần chạy để tránh trùng tên (username/coupon code...)
_S = uuid.uuid4().hex[:6]


@asynccontextmanager
async def app_client():
    """Trả về AsyncClient đã qua lifespan (routes đã đăng ký)."""
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


async def _create_user(client, admin_headers, *, password="Passw0rd!", is_active=True) -> dict:
    """Admin tạo 1 user tạm, trả về dict user (kèm 'password' plaintext để login)."""
    uname = f"tu_{_S}_{uuid.uuid4().hex[:6]}"
    resp = await client.post(
        "/api/users",
        json={
            "username": uname,
            "email": f"{uname}@test.local",
            "password": password,
            "isActive": is_active,
        },
        headers=admin_headers,
    )
    assert resp.status_code == 201, f"Create user: {resp.text}"
    data = resp.json()
    data["password"] = password
    return data


# ─────────────────────────────────────────────────────────────────────────────
# Coupon CRUD
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_coupon_crud():
    async with app_client() as client:
        headers = await _login(client)

        code = f"SALE{_S}"
        # Create
        resp = await client.post(
            "/api/coupons",
            json={
                "code": code,
                "discount": 15.0,
                "startDate": "2026-01-01T00:00:00",
                "endDate": "2026-12-31T23:59:59",
                "isActive": True,
            },
            headers=headers,
        )
        assert resp.status_code == 201, f"Create coupon: {resp.text}"
        c = resp.json()
        cid = c["id"]
        assert c["code"] == code and c["discount"] == 15.0
        print(f"\n[coupon] ✓ Create id={cid}")

        # List
        resp = await client.get("/api/coupons", headers=headers)
        assert resp.status_code == 200
        assert any(x["id"] == cid for x in resp.json())

        # Detail
        resp = await client.get(f"/api/coupons/{cid}", headers=headers)
        assert resp.status_code == 200

        # Update
        resp = await client.put(
            f"/api/coupons/{cid}", json={"discount": 25.0, "isActive": False}, headers=headers
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["discount"] == 25.0
        assert resp.json()["is_active"] is False
        print("[coupon] ✓ Update OK")

        # Delete
        resp = await client.delete(f"/api/coupons/{cid}", headers=headers)
        assert resp.status_code == 200

        # Detail sau khi xóa -> E10701 (404)
        resp = await client.get(f"/api/coupons/{cid}", headers=headers)
        assert resp.status_code in (400, 404)
        print("[coupon] ✓ CRUD hoàn tất")


@pytest.mark.asyncio
async def test_coupon_detail_not_found():
    async with app_client() as client:
        headers = await _login(client)
        resp = await client.get("/api/coupons/99999999", headers=headers)
        assert resp.status_code in (400, 404)
        # E10400 = "Phiếu giảm giá không tồn tại" (đã sửa từ E10701 "Tên file là bắt buộc")
        assert resp.json()["errorKey"] == "E10400"
        print("\n[coupon] ✓ Detail không tồn tại -> E10400")


# ─────────────────────────────────────────────────────────────────────────────
# User management
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_user_register_and_me():
    async with app_client() as client:
        admin = await _login(client)

        uname = f"reg_{_S}_{uuid.uuid4().hex[:6]}"
        # Register (public)
        resp = await client.post(
            "/api/register",
            json={"username": uname, "email": f"{uname}@test.local", "password": "Passw0rd!"},
        )
        assert resp.status_code == 201, f"Register: {resp.text}"
        print(f"\n[user] ✓ Register {uname}")

        # Login as new user, GET /me
        u_headers = await _login(client, uname, "Passw0rd!")
        resp = await client.get("/api/me", headers=u_headers)
        assert resp.status_code == 200
        me = resp.json()
        assert me["username"] == uname
        uid = me["id"]

        # /me/permissions - user thường không có quyền nào -> list rỗng
        resp = await client.get("/api/me/permissions", headers=u_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        print(f"[user] ✓ /me/permissions = {resp.json()}")

        # update_me
        resp = await client.put("/api/me", json={"phone": "0900000001"}, headers=u_headers)
        assert resp.status_code == 200
        assert resp.json()["phone"] == "0900000001"

        # cleanup
        await client.delete(f"/api/users/{uid}", headers=admin)
        print("[user] ✓ register/me/update hoàn tất")


@pytest.mark.asyncio
async def test_user_register_duplicate_username():
    async with app_client() as client:
        admin = await _login(client)
        u = await _create_user(client, admin)
        # Đăng ký lại trùng username -> E1006
        resp = await client.post(
            "/api/register",
            json={"username": u["username"], "email": f"x{_S}@test.local", "password": "Passw0rd!"},
        )
        assert resp.status_code in (400, 409), resp.text
        assert resp.json()["errorKey"] == "E1006"
        await client.delete(f"/api/users/{u['id']}", headers=admin)
        print("\n[user] ✓ Trùng username -> E1006")


@pytest.mark.asyncio
async def test_user_admin_crud():
    async with app_client() as client:
        admin = await _login(client)

        # count trước
        resp = await client.get("/api/users/count", headers=admin)
        assert resp.status_code == 200
        before = resp.json()["total"]

        # create
        u = await _create_user(client, admin)
        uid = u["id"]

        # count tăng
        resp = await client.get("/api/users/count", headers=admin)
        assert resp.json()["total"] == before + 1

        # list
        resp = await client.get("/api/users?page=1&limit=100", headers=admin)
        assert resp.status_code == 200
        assert any(x["id"] == uid for x in resp.json())

        # detail
        resp = await client.get(f"/api/users/{uid}", headers=admin)
        assert resp.status_code == 200

        # update
        resp = await client.put(f"/api/users/{uid}", json={"address": "HN test"}, headers=admin)
        assert resp.status_code == 200
        assert resp.json()["address"] == "HN test"

        # set active false
        resp = await client.patch(f"/api/users/{uid}/active", json={"isActive": False}, headers=admin)
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

        # delete
        resp = await client.delete(f"/api/users/{uid}", headers=admin)
        assert resp.status_code == 200

        # count trở lại
        resp = await client.get("/api/users/count", headers=admin)
        assert resp.json()["total"] == before
        print("\n[user] ✓ Admin CRUD hoàn tất")


@pytest.mark.asyncio
async def test_user_delete_admin_protected():
    """Không được xóa tài khoản admin seed -> E10101."""
    async with app_client() as client:
        admin = await _login(client)
        # admin user id
        resp = await client.get("/api/me", headers=admin)
        admin_id = resp.json()["id"]
        resp = await client.delete(f"/api/users/{admin_id}", headers=admin)
        assert resp.status_code in (400, 403, 409), resp.text
        assert resp.json()["errorKey"] == "E10101"
        print("\n[user] ✓ Xóa admin bị chặn -> E10101")


# ─────────────────────────────────────────────────────────────────────────────
# Authorization: user thường bị 403
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_authorization_denied_for_plain_user():
    async with app_client() as client:
        admin = await _login(client)
        u = await _create_user(client, admin)
        u_headers = await _login(client, u["username"], u["password"])

        # User thường gọi endpoint cần quyền admin -> 403 E2021
        resp = await client.get("/api/users", headers=u_headers)
        assert resp.status_code == 403, resp.text
        assert resp.json()["errorKey"] == "E2021"
        print("\n[authz] ✓ User thường gọi /api/users -> 403 E2021")

        resp = await client.post(
            "/api/coupons",
            json={"code": f"X{_S}", "discount": 1, "startDate": "2026-01-01", "endDate": "2026-02-01"},
            headers=u_headers,
        )
        assert resp.status_code == 403
        assert resp.json()["errorKey"] == "E2021"
        print("[authz] ✓ User thường tạo coupon -> 403 E2021")

        await client.delete(f"/api/users/{u['id']}", headers=admin)


@pytest.mark.asyncio
async def test_deactivated_user_cannot_access():
    """User bị khóa: token (nếu có) không truy cập được tài nguyên cần đăng nhập."""
    async with app_client() as client:
        admin = await _login(client)
        u = await _create_user(client, admin)
        # login khi còn active
        u_headers = await _login(client, u["username"], u["password"])
        # admin khóa user
        resp = await client.patch(f"/api/users/{u['id']}/active", json={"isActive": False}, headers=admin)
        assert resp.status_code == 200

        # token cũ giờ phải bị từ chối (middleware kiểm tra is_active)
        resp = await client.get("/api/me", headers=u_headers)
        assert resp.status_code == 401, f"Token user bị khóa vẫn dùng được: {resp.text}"
        print("\n[authz] ✓ Token của user bị khóa -> 401")

        # login lại khi đã khóa: ghi nhận hành vi hiện tại (xem review doc)
        relogin = await client.post(
            "/api/login", json={"username": u["username"], "password": u["password"]}
        )
        print(f"[authz] (ghi nhận) login khi đã khóa -> status={relogin.status_code}")

        await client.delete(f"/api/users/{u['id']}", headers=admin)


# ─────────────────────────────────────────────────────────────────────────────
# Group CRUD
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_group_crud():
    async with app_client() as client:
        admin = await _login(client)

        resp = await client.post(
            "/api/group", json={"name": f"Grp {_S}", "description": "test"}, headers=admin
        )
        assert resp.status_code == 201, resp.text
        gid = resp.json()["id"]
        print(f"\n[group] ✓ Create id={gid}")

        resp = await client.get(f"/api/group/{gid}", headers=admin)
        assert resp.status_code == 200

        resp = await client.put(f"/api/group/{gid}", json={"description": "updated"}, headers=admin)
        assert resp.status_code == 200
        assert resp.json()["description"] == "updated"

        resp = await client.delete(f"/api/group/{gid}", headers=admin)
        assert resp.status_code == 200
        print("[group] ✓ CRUD hoàn tất")


# ─────────────────────────────────────────────────────────────────────────────
# Group member flow
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_group_member_flow():
    async with app_client() as client:
        admin = await _login(client)
        u = await _create_user(client, admin)
        uid = u["id"]
        resp = await client.post("/api/group", json={"name": f"GM {_S}"}, headers=admin)
        gid = resp.json()["id"]

        # add
        resp = await client.post(
            "/api/group-member/add", json={"user_id": uid, "group_id": gid}, headers=admin
        )
        assert resp.status_code == 201, resp.text
        print(f"\n[group-member] ✓ Add user {uid} -> group {gid}")

        # check
        resp = await client.post(
            "/api/group-member/check", json={"user_id": uid, "group_id": gid}, headers=admin
        )
        assert resp.status_code == 200
        assert resp.json()["is_in_group"] is True

        # users in group
        resp = await client.get(f"/api/group-member/group_{gid}/users", headers=admin)
        assert resp.status_code == 200
        assert any(x["id"] == uid for x in resp.json())

        # groups for user
        resp = await client.get(f"/api/group-member/user_{uid}/groups", headers=admin)
        assert resp.status_code == 200
        assert any(g["id"] == gid for g in resp.json())

        # remove
        resp = await client.post(
            "/api/group-member/remove", json={"user_id": uid, "group_id": gid}, headers=admin
        )
        assert resp.status_code == 200

        # check lại -> false
        resp = await client.post(
            "/api/group-member/check", json={"user_id": uid, "group_id": gid}, headers=admin
        )
        assert resp.json()["is_in_group"] is False
        print("[group-member] ✓ Flow hoàn tất")

        # cleanup
        await client.delete(f"/api/group/{gid}", headers=admin)
        await client.delete(f"/api/users/{uid}", headers=admin)


# ─────────────────────────────────────────────────────────────────────────────
# Group permission flow
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_group_permission_flow():
    async with app_client() as client:
        admin = await _login(client)
        resp = await client.post("/api/group", json={"name": f"GP {_S}"}, headers=admin)
        gid = resp.json()["id"]

        # assign
        resp = await client.post(
            "/api/group-permissions",
            json={
                "group_id": gid,
                "permissions": {
                    "view_products": {"is_active": True, "is_denied": False, "target": "all"}
                },
            },
            headers=admin,
        )
        assert resp.status_code == 201, resp.text
        assert any(e["permission"] == "view_products" for e in resp.json())
        print(f"\n[group-perm] ✓ Assign view_products -> group {gid}")

        # get
        resp = await client.get(f"/api/group-permissions/{gid}", headers=admin)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

        # update
        resp = await client.put(
            "/api/group-permissions",
            json={
                "group_id": gid,
                "permissions": {
                    "view_products": {"is_active": True, "is_denied": True, "target": "all"}
                },
            },
            headers=admin,
        )
        assert resp.status_code == 200, resp.text

        # check
        resp = await client.post(
            "/api/group-permissions/check",
            json={"group_id": gid, "permission_name": "view_products"},
            headers=admin,
        )
        assert resp.status_code == 200
        print(f"[group-perm] check has_permission = {resp.json()}")

        # delete
        resp = await client.request(
            "DELETE",
            "/api/group-permissions",
            json={"group_id": gid, "permissions": ["view_products"]},
            headers=admin,
        )
        assert resp.status_code == 200, resp.text

        # cleanup
        await client.delete(f"/api/group/{gid}", headers=admin)
        print("[group-perm] ✓ Flow hoàn tất")


# ─────────────────────────────────────────────────────────────────────────────
# User permission flow
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_user_permission_flow():
    async with app_client() as client:
        admin = await _login(client)
        u = await _create_user(client, admin)
        uid = u["id"]

        # assign view_products trực tiếp cho user
        resp = await client.post(
            "/api/user-permissions",
            json={
                "user_id": uid,
                "permissions": {
                    "view_products": {"is_active": True, "is_denied": False, "target": "all"}
                },
            },
            headers=admin,
        )
        assert resp.status_code == 201, resp.text
        print(f"\n[user-perm] ✓ Assign view_products -> user {uid}")

        # get
        resp = await client.get(f"/api/user-permissions/{uid}", headers=admin)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

        # user giờ có quyền -> /me/permissions chứa view_products
        u_headers = await _login(client, u["username"], u["password"])
        resp = await client.get("/api/me/permissions", headers=u_headers)
        assert "view_products" in resp.json(), resp.text
        print("[user-perm] ✓ /me/permissions có view_products")

        # update -> denied
        resp = await client.put(
            "/api/user-permissions",
            json={
                "user_id": uid,
                "permissions": {
                    "view_products": {"is_active": True, "is_denied": True, "target": "all"}
                },
            },
            headers=admin,
        )
        assert resp.status_code == 200, resp.text

        # delete
        resp = await client.request(
            "DELETE",
            "/api/user-permissions",
            json={"user_id": uid, "permissions": ["view_products"]},
            headers=admin,
        )
        assert resp.status_code == 200, resp.text

        await client.delete(f"/api/users/{uid}", headers=admin)
        print("[user-perm] ✓ Flow hoàn tất")


# ─────────────────────────────────────────────────────────────────────────────
# Security: change-password / verify-password
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_change_and_verify_password():
    async with app_client() as client:
        admin = await _login(client)
        u = await _create_user(client, admin, password="OldPass1!")
        uid = u["id"]
        u_headers = await _login(client, u["username"], "OldPass1!")

        # verify-password đúng
        resp = await client.post(
            "/api/verify-password", json={"password": "OldPass1!"}, headers=u_headers
        )
        assert resp.status_code == 200, resp.text

        # verify-password sai -> E1024
        resp = await client.post(
            "/api/verify-password", json={"password": "WRONG"}, headers=u_headers
        )
        assert resp.status_code in (400, 401), resp.text
        assert resp.json()["errorKey"] == "E1024"

        # change-password
        resp = await client.post(
            "/api/change-password",
            json={"currentPassword": "OldPass1!", "newPassword": "NewPass2@"},
            headers=u_headers,
        )
        assert resp.status_code == 200, resp.text
        print("\n[security] ✓ change-password OK")

        # login bằng mật khẩu mới
        new_headers = await _login(client, u["username"], "NewPass2@")
        assert "Authorization" in new_headers

        # mật khẩu cũ không còn login được -> E1005
        resp = await client.post(
            "/api/login", json={"username": u["username"], "password": "OldPass1!"}
        )
        assert resp.status_code == 401
        assert resp.json()["errorKey"] == "E1005"
        print("[security] ✓ Mật khẩu cũ bị từ chối -> E1005")

        await client.delete(f"/api/users/{uid}", headers=admin)


@pytest.mark.asyncio
async def test_change_password_wrong_current():
    async with app_client() as client:
        admin = await _login(client)
        u = await _create_user(client, admin, password="OldPass1!")
        u_headers = await _login(client, u["username"], "OldPass1!")
        resp = await client.post(
            "/api/change-password",
            json={"currentPassword": "WRONG", "newPassword": "NewPass2@"},
            headers=u_headers,
        )
        assert resp.status_code in (400, 401)
        assert resp.json()["errorKey"] == "E1024"
        await client.delete(f"/api/users/{u['id']}", headers=admin)
        print("\n[security] ✓ change-password sai current -> E1024")


# ─────────────────────────────────────────────────────────────────────────────
# Product phụ: count, by-category, attribute/option, find-option
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_product_count_and_by_category():
    async with app_client() as client:
        admin = await _login(client)
        resp = await client.post("/api/categories", json={"name": f"Cat PC {_S}"}, headers=admin)
        cat_id = resp.json()["id"]
        resp = await client.post(
            "/api/products",
            json={"name": f"PC Prod {_S}", "categoryId": cat_id, "locationAddress": "HN",
                  "price": 1000, "stock": 5},
            headers=admin,
        )
        assert resp.status_code == 201, resp.text
        prod_id = resp.json()["id"]

        # count (public)
        resp = await client.get("/api/products/count")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

        # by-category
        resp = await client.get(f"/api/products/by-category/{cat_id}", headers=admin)
        assert resp.status_code == 200
        assert any(p.get("id") == prod_id for p in resp.json())
        print(f"\n[product] ✓ count + by-category OK")

        # by-category rỗng -> E10200
        resp = await client.get("/api/products/by-category/99999999", headers=admin)
        assert resp.status_code in (400, 404)
        assert resp.json()["errorKey"] == "E10200"

        await client.delete(f"/api/products/{prod_id}", headers=admin)
        await client.delete(f"/api/categories/{cat_id}", headers=admin)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 7 - phân quyền scope theo nhánh category (edit_product)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_category_scoped_edit_product_subtree():
    """Cấp edit_product trên category CHA -> sửa được sản phẩm ở nhánh CON; nhánh khác bị 403."""
    async with app_client() as client:
        admin = await _login(client)

        # Cây: P (cha) -> C (con); sản phẩm pr_in thuộc C. Nhánh khác D chứa pr_out.
        p_id = (await client.post(
            "/api/categories", json={"name": f"P {_S}"}, headers=admin
        )).json()["id"]
        c_id = (await client.post(
            "/api/categories", json={"name": f"C {_S}", "parentId": p_id}, headers=admin
        )).json()["id"]
        d_id = (await client.post(
            "/api/categories", json={"name": f"D {_S}"}, headers=admin
        )).json()["id"]
        pr_in = (await client.post(
            "/api/products",
            json={"name": f"In {_S}", "categoryId": c_id, "locationAddress": "HN",
                  "price": 1000, "stock": 5},
            headers=admin,
        )).json()["id"]
        pr_out = (await client.post(
            "/api/products",
            json={"name": f"Out {_S}", "categoryId": d_id, "locationAddress": "HN",
                  "price": 1000, "stock": 5},
            headers=admin,
        )).json()["id"]

        u = await _create_user(client, admin)
        uid = u["id"]
        # Cấp edit_product cho user với target = category CHA (P)
        resp = await client.post(
            "/api/user-permissions",
            json={"user_id": uid, "permissions": {
                "edit_product": {"is_active": True, "is_denied": False, "target": p_id}
            }},
            headers=admin,
        )
        assert resp.status_code == 201, resp.text
        u_headers = await _login(client, u["username"], u["password"])

        try:
            # Sản phẩm trong nhánh con C -> được phép (scope cấp ở P phủ cả subtree)
            r_in = await client.put(f"/api/products/{pr_in}", json={"price": 1500}, headers=u_headers)
            assert r_in.status_code == 200, f"Sửa trong nhánh phải được phép: {r_in.text}"
            # Sản phẩm nhánh khác D -> 403
            r_out = await client.put(f"/api/products/{pr_out}", json={"price": 1500}, headers=u_headers)
            assert r_out.status_code == 403, f"Sửa ngoài nhánh phải bị chặn: {r_out.text}"
            assert r_out.json()["errorKey"] == "E2021"
            print("\n[scope] ✓ edit_product cấp ở category cha phủ nhánh con; nhánh khác 403")
        finally:
            await client.request(
                "DELETE", "/api/user-permissions",
                json={"user_id": uid, "permissions": ["edit_product"]}, headers=admin,
            )
            await client.delete(f"/api/products/{pr_in}", headers=admin)
            await client.delete(f"/api/products/{pr_out}", headers=admin)
            await client.delete(f"/api/users/{uid}", headers=admin)
            await client.delete(f"/api/categories/{c_id}", headers=admin)
            await client.delete(f"/api/categories/{p_id}", headers=admin)
            await client.delete(f"/api/categories/{d_id}", headers=admin)


@pytest.mark.asyncio
async def test_managed_product_list_filtered_by_scope():
    """GET /products/managed: nhân viên chỉ thấy sản phẩm thuộc mảng category mình phụ trách."""
    async with app_client() as client:
        admin = await _login(client)

        p_id = (await client.post(
            "/api/categories", json={"name": f"MP {_S}"}, headers=admin
        )).json()["id"]
        c_id = (await client.post(
            "/api/categories", json={"name": f"MC {_S}", "parentId": p_id}, headers=admin
        )).json()["id"]
        d_id = (await client.post(
            "/api/categories", json={"name": f"MD {_S}"}, headers=admin
        )).json()["id"]
        pr_c = (await client.post(
            "/api/products",
            json={"name": f"InC {_S}", "categoryId": c_id, "locationAddress": "HN",
                  "price": 1000, "stock": 5},
            headers=admin,
        )).json()["id"]
        pr_d = (await client.post(
            "/api/products",
            json={"name": f"InD {_S}", "categoryId": d_id, "locationAddress": "HN",
                  "price": 1000, "stock": 5},
            headers=admin,
        )).json()["id"]

        u = await _create_user(client, admin)
        uid = u["id"]
        # Cấp view_products cho user với target = category CHA (P)
        await client.post(
            "/api/user-permissions",
            json={"user_id": uid, "permissions": {
                "view_products": {"is_active": True, "is_denied": False, "target": p_id}
            }},
            headers=admin,
        )
        u_headers = await _login(client, u["username"], u["password"])

        try:
            resp = await client.get("/api/products/managed?page=1&limit=200", headers=u_headers)
            assert resp.status_code == 200, resp.text
            ids = {p["id"] for p in resp.json()}
            assert pr_c in ids, "Nhân viên phải thấy sản phẩm trong mảng (nhánh con C)"
            assert pr_d not in ids, "Nhân viên KHÔNG được thấy sản phẩm ngoài mảng (nhánh D)"
            print("\n[scope] ✓ /managed lọc đúng theo mảng nhân viên")

            # Superadmin gọi được và trả về danh sách (không bị lọc)
            admin_resp = await client.get("/api/products/managed?page=1&limit=200", headers=admin)
            assert admin_resp.status_code == 200
            assert isinstance(admin_resp.json(), list)
        finally:
            await client.request(
                "DELETE", "/api/user-permissions",
                json={"user_id": uid, "permissions": ["view_products"]}, headers=admin,
            )
            await client.delete(f"/api/products/{pr_c}", headers=admin)
            await client.delete(f"/api/products/{pr_d}", headers=admin)
            await client.delete(f"/api/users/{uid}", headers=admin)
            await client.delete(f"/api/categories/{c_id}", headers=admin)
            await client.delete(f"/api/categories/{p_id}", headers=admin)
            await client.delete(f"/api/categories/{d_id}", headers=admin)


@pytest.mark.asyncio
async def test_product_attribute_and_find_option():
    async with app_client() as client:
        admin = await _login(client)
        resp = await client.post("/api/categories", json={"name": f"Cat Attr {_S}"}, headers=admin)
        cat_id = resp.json()["id"]
        resp = await client.post(
            "/api/products",
            json={"name": f"Attr Prod {_S}", "categoryId": cat_id, "locationAddress": "HN",
                  "price": 1000, "stock": 0},
            headers=admin,
        )
        prod_id = resp.json()["id"]

        # set attribute: 1 thuộc tính "Màu" có giá trị "Đỏ" -> price 1200, stock 7
        resp = await client.post(
            f"/api/products/{prod_id}/attribute",
            json={"attribute": ["Màu"], "value": [[["Đỏ"], [1200, 7]]]},
            headers=admin,
        )
        assert resp.status_code == 200, f"Set attribute: {resp.text}"
        print(f"\n[product] ✓ Set attribute/option OK")

        # find-option theo json {"Màu": "Đỏ"}
        resp = await client.post(
            f"/api/products/{prod_id}/find-option",
            json={"Màu": "Đỏ"},
            headers=admin,
        )
        assert resp.status_code == 200, f"Find option: {resp.text}"
        opt = resp.json()
        assert opt["price"] == 1200 and opt["stock"] == 7
        print(f"[product] ✓ find-option -> id={opt['id']}, price={opt['price']}, stock={opt['stock']}")

        await client.delete(f"/api/products/{prod_id}", headers=admin)
        await client.delete(f"/api/categories/{cat_id}", headers=admin)
