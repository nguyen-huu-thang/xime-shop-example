"""
ShopWebAdapter — mở rộng WebAdapter của Xime để gắn exception handler + JWT middleware.

Middleware ordering (LIFO — last added = outermost = runs first):
  1. JwtMiddleware    (added last → outermost → runs first): xác thực token
  2. RequestContextMiddleware (added by super() → inner): setup/teardown context

Kết quả: JWT middleware chạy trước handler, sau đó context middleware dọn dẹp.
"""
from __future__ import annotations

from fastapi import FastAPI

from xime.adapters.web import WebAdapter

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
        return fastapi_app
