"""
Phase 0 - Test health-check endpoint.

Xác minh:
- DI container khởi động được với binding thật (app.config.dependency).
- WebAdapter build được FastAPI app.
- Route GET /api/health trả 200 {"status": "ok"}.
"""
import pytest
from httpx import ASGITransport, AsyncClient

import app.config.web  # noqa: F401  - side effect: configure_controllers + configure_openapi
from app.config.dependency import dependency
from xime.adapters.web import WebAdapter
from xime.testing import TestApplication


@pytest.mark.asyncio
async def test_health_endpoint_returns_ok():
    async with TestApplication(binding=dependency) as test_app:
        fastapi_app = WebAdapter().build_app(test_app)
        # Lifespan đăng ký route controller - phải chạy trước khi gọi request
        # Lifespan registers controller routes - must run before requests
        async with fastapi_app.router.lifespan_context(fastapi_app):
            transport = ASGITransport(app=fastapi_app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/health")

        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_openapi_exposes_health_path():
    async with TestApplication(binding=dependency) as test_app:
        fastapi_app = WebAdapter().build_app(test_app)
        async with fastapi_app.router.lifespan_context(fastapi_app):
            transport = ASGITransport(app=fastapi_app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/openapi.json")

        assert resp.status_code == 200
        schema = resp.json()
        assert schema["info"]["title"] == "Shop Backend"
        assert "/api/health" in schema["paths"]
