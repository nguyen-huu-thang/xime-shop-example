"""
ShopWebAdapter - mở rộng WebAdapter của Xime để gắn exception handler + JWT middleware.

Middleware ordering (LIFO - last added = outermost = runs first):
  1. CORSMiddleware   (added last → outermost → runs first): xử lý preflight OPTIONS
  2. JwtMiddleware    (inner hơn CORS): xác thực token
  3. RequestContextMiddleware (added by super() → innermost): setup/teardown context

Kết quả: CORS xử lý preflight trước, rồi JWT middleware chạy trước handler, sau đó
context middleware dọn dẹp.
"""
from __future__ import annotations

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from xime.adapters.web import WebAdapter
from xime.core.config.runtime import RuntimeConfig

from app.exception.handler import register_exception_handlers


class ShopWebAdapter(WebAdapter):
    def build_app(self, xime_app) -> FastAPI:
        fastapi_app = super().build_app(xime_app)
        register_exception_handlers(fastapi_app)

        # Register JWT middleware AFTER super() so it becomes the outermost layer.
        # Đăng ký JWT middleware sau super() để nó là lớp ngoài cùng.
        from app.security.jwt_middleware import JwtMiddleware
        from app.service.authentication_service import AuthenticationService
        from app.service.blacklist_token_service import BlacklistTokenService
        from app.service.user_service import UserService

        fastapi_app.add_middleware(
            JwtMiddleware,
            auth_svc=xime_app.get(AuthenticationService),
            user_svc=xime_app.get(UserService),
            blacklist_svc=xime_app.get(BlacklistTokenService),
        )

        # CORS: add SAU JwtMiddleware để là lớp ngoài cùng (xử lý preflight OPTIONS trước
        # khi JWT middleware chạy). Origin lấy từ config; KHÔNG dùng "*" khi có credentials.
        # CORS must be outermost so preflight is handled before JWT auth.
        config = xime_app.get(RuntimeConfig)
        origins = config.get("cors.allow_origins", ["http://localhost:3000"])
        # allow_origin_regex (tùy chọn, CHỈ dùng cho dev): cho khớp mọi origin localhost/IP LAN
        # trên cổng bất kỳ mà không phải liệt kê từng IP. Prod đặt rỗng/null để TẮT (an toàn).
        # Optional dev-only regex to match any localhost/LAN origin. Disabled in prod.
        origin_regex = config.get("cors.allow_origin_regex", None)

        cors_kwargs: dict = {
            "allow_origins": origins,     # danh sách origin cụ thể của frontend
            "allow_credentials": True,    # cho phép gửi cookie refresh + header Authorization
            "allow_methods": ["*"],
            "allow_headers": ["*"],
        }
        if origin_regex:  # rỗng/None → bỏ qua (prod chỉ dùng allow_origins)
            cors_kwargs["allow_origin_regex"] = origin_regex

        fastapi_app.add_middleware(CORSMiddleware, **cors_kwargs)
        return fastapi_app
