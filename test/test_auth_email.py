"""
Integration test cho email bảo mật: xác minh email, quên/đặt lại mật khẩu, OTP.

Email bị TẮT khi chạy test (chưa cấu hình SMTP) nên không gửi mạng. Token/mã được mint trực tiếp
qua AuthTokenService lấy từ DI container (test_app.get(...)) để kiểm happy-path mà không cần đọc email.
Yêu cầu DB đã seed.
"""
import uuid
from contextlib import asynccontextmanager

import pytest

import app.config.web  # noqa: F401 - side effect: configure_controllers + openapi
from app.config.dependency import dependency
from app.service.auth_token_service import AuthTokenService
from httpx import ASGITransport, AsyncClient
from xime.adapters.web import WebAdapter
from xime.testing import TestApplication

_S = uuid.uuid4().hex[:6]


@asynccontextmanager
async def app_ctx():
    """Trả về (client, test_app) - test_app để lấy service từ container (mint token)."""
    async with TestApplication(binding=dependency) as test_app:
        fastapi_app = WebAdapter().build_app(test_app)
        async with fastapi_app.router.lifespan_context(fastapi_app):
            transport = ASGITransport(app=fastapi_app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                yield client, test_app


async def _register_and_login(client, suffix: str):
    username = f"u{suffix}"[:20]
    email = f"{username}@ex.test"
    pw = "Pass@123"
    r = await client.post(
        "/api/register", json={"username": username, "email": email, "password": pw}
    )
    assert r.status_code == 201, r.text
    r = await client.post("/api/login", json={"username": username, "password": pw})
    assert r.status_code == 200, r.text
    headers = {"Authorization": f"Bearer {r.json()['accessToken']}"}
    me = (await client.get("/api/me", headers=headers)).json()
    return me, headers, pw


# ── Negative cases (không cần token thật) ────────────────────────────────────

@pytest.mark.asyncio
async def test_forgot_password_unknown_email_returns_200():
    async with app_ctx() as (client, _):
        r = await client.post(
            "/api/forgot-password", json={"email": f"none-{_S}@nowhere.test"}
        )
        assert r.status_code == 200  # không lộ email tồn tại hay không


@pytest.mark.asyncio
async def test_reset_password_invalid_token():
    async with app_ctx() as (client, _):
        r = await client.post(
            "/api/reset-password", json={"token": "bad-token", "newPassword": "Xx@12345"}
        )
        assert r.status_code == 400
        assert r.json()["errorKey"] == "E1025"


@pytest.mark.asyncio
async def test_verify_email_invalid_token():
    async with app_ctx() as (client, _):
        r = await client.post("/api/verify-email", json={"token": "bad-token"})
        assert r.status_code == 400
        assert r.json()["errorKey"] == "E1025"


# ── Happy paths (mint token qua container) ───────────────────────────────────

@pytest.mark.asyncio
async def test_verify_email_flow():
    async with app_ctx() as (client, test_app):
        me, headers, _ = await _register_and_login(client, _S + "v")
        assert me["email_verified"] is False

        tokens = test_app.get(AuthTokenService)
        raw = await tokens.create_verify_email(me["id"])

        r = await client.post("/api/verify-email", json={"token": raw})
        assert r.status_code == 200, r.text

        me2 = (await client.get("/api/me", headers=headers)).json()
        assert me2["email_verified"] is True

        # Dùng lại token -> E1025 (đã dùng)
        r = await client.post("/api/verify-email", json={"token": raw})
        assert r.status_code == 400
        assert r.json()["errorKey"] == "E1025"


@pytest.mark.asyncio
async def test_reset_password_revokes_refresh_tokens():
    async with app_ctx() as (client, test_app):
        me, headers, _ = await _register_and_login(client, _S + "r")

        # Refresh token hoạt động trước khi reset (cookie đặt lúc login)
        r = await client.post("/api/refresh-token")
        assert r.status_code == 200, r.text

        tokens = test_app.get(AuthTokenService)
        raw = await tokens.create_reset_password(me["id"])
        new_pw = "NewPass@456"
        r = await client.post(
            "/api/reset-password", json={"token": raw, "newPassword": new_pw}
        )
        assert r.status_code == 200, r.text

        # Sau reset: refresh token cũ bị thu hồi -> refresh thất bại
        r = await client.post("/api/refresh-token")
        assert r.status_code in (400, 401)

        # Đăng nhập bằng mật khẩu mới được
        r = await client.post(
            "/api/login", json={"username": me["username"], "password": new_pw}
        )
        assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_otp_flow():
    async with app_ctx() as (client, test_app):
        me, headers, _ = await _register_and_login(client, _S + "o")

        tokens = test_app.get(AuthTokenService)
        code = await tokens.create_otp(me["id"])

        # Mã sai -> E1026
        wrong = "999999" if code != "999999" else "000000"
        r = await client.post("/api/otp/verify", json={"otp": wrong}, headers=headers)
        assert r.status_code == 400
        assert r.json()["errorKey"] == "E1026"

        # Mã đúng -> 200
        r = await client.post("/api/otp/verify", json={"otp": code}, headers=headers)
        assert r.status_code == 200, r.text

        # Dùng lại -> E1026 (đã dùng)
        r = await client.post("/api/otp/verify", json={"otp": code}, headers=headers)
        assert r.status_code == 400
        assert r.json()["errorKey"] == "E1026"
