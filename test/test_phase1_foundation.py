"""
Phase 1 - Test nền tảng.

Bao gồm:
- DB stack: DI build + transaction + AsyncSession (SELECT 1).
- AppException → JSON qua ShopWebAdapter exception handler.
- Lỗi validation → JSON E10711.
- Unit: AppException, error_code fallback, current_user/require_login + SecurityContext.
"""
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel
from sqlalchemy import text

import app.config.web  # noqa: F401 - side effect: configure_controllers + openapi
from app.config.dependency import dependency
from app.exception.app_exception import AppException
from app.exception.error_code import get_error
from app.security.current_user import current_user, require_login, set_current_user
from app.shop_web_adapter import ShopWebAdapter
from xime.core.security import clear_security
from xime.starters.sqlalchemy import SqlAlchemyTransactionManager
from xime.starters.sqlalchemy.session import AsyncSessionFactory
from xime.testing import TestApplication


# ── DB stack ──────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_db_transaction_select_1():
    async with TestApplication(binding=dependency) as test_app:
        tm = test_app.get(SqlAlchemyTransactionManager)
        sessions = test_app.get(AsyncSessionFactory)
        async with tm():
            result = await sessions.current().execute(text("SELECT 1"))
            assert result.scalar() == 1


@pytest.mark.asyncio
async def test_session_outside_transaction_raises():
    async with TestApplication(binding=dependency) as test_app:
        sessions = test_app.get(AsyncSessionFactory)
        with pytest.raises(RuntimeError):
            sessions.current()  # gọi ngoài transaction → lỗi


# ── Exception handler qua HTTP ───────────────────────────────────────────────
def _build_app_with_probe(test_app) -> FastAPI:
    """Build FastAPI qua ShopWebAdapter + thêm route thử raise lỗi."""
    fastapi_app = ShopWebAdapter().build_app(test_app)

    @fastapi_app.get("/_probe/app-exception")
    async def _raise_app_exc():
        raise AppException("E2021")

    class _Body(BaseModel):
        name: str

    @fastapi_app.post("/_probe/validate")
    async def _validate(body: _Body):
        return {"name": body.name}

    return fastapi_app


@pytest.mark.asyncio
async def test_app_exception_returns_structured_json():
    async with TestApplication(binding=dependency) as test_app:
        fastapi_app = _build_app_with_probe(test_app)
        async with fastapi_app.router.lifespan_context(fastapi_app):
            transport = ASGITransport(app=fastapi_app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/_probe/app-exception")

        assert resp.status_code == 403  # E2021 → 403
        body = resp.json()
        assert body["errorKey"] == "E2021"
        assert body["code"] == 2021
        assert "không được phép" in body["message"]


@pytest.mark.asyncio
async def test_validation_error_returns_e10711():
    async with TestApplication(binding=dependency) as test_app:
        fastapi_app = _build_app_with_probe(test_app)
        async with fastapi_app.router.lifespan_context(fastapi_app):
            transport = ASGITransport(app=fastapi_app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post("/_probe/validate", json={})  # thiếu name

        assert resp.status_code == 400
        body = resp.json()
        assert body["errorKey"] == "E10711"
        assert body["code"] == 10711


# ── Unit ──────────────────────────────────────────────────────────────────────
def test_app_exception_reads_error_code():
    exc = AppException("E2021")
    assert exc.code == 2021
    assert exc.http_status == 403
    assert exc.error_key == "E2021"


def test_app_exception_custom_message():
    exc = AppException("E10711", "Sai định dạng tên")
    assert exc.message == "Sai định dạng tên"
    assert exc.code == 10711


def test_error_code_unknown_falls_back_to_e0000():
    err = get_error("E_KHONG_TON_TAI")
    assert err.code == 0
    assert err.http_status == 500


def test_require_login_without_user_raises_e2025():
    clear_security()
    with pytest.raises(AppException) as ei:
        require_login()
    assert ei.value.error_key == "E2025"


def test_set_and_get_current_user():
    clear_security()

    class _FakeUser:
        id = 1
        username = "tester"

    fake = _FakeUser()
    set_current_user(fake, "jwt-token-abc")
    assert current_user() is fake
    assert require_login() is fake
    clear_security()
    assert current_user() is None
