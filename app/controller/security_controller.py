"""
SecurityController - xác thực: đăng nhập, đăng xuất, refresh token, đổi mật khẩu.

Chiến lược token (chốt với người dùng):
  - /login           -> trả accessToken trong body + đặt refresh token vào httpOnly cookie.
  - /refresh-token   -> đọc refresh token từ cookie, xoay refresh mới (đặt lại cookie),
                        trả accessToken mới trong body.
  - /logout          -> thu hồi access token (blacklist) + xóa refresh token + xóa cookie.
  - /change-password -> đổi mật khẩu (cần đăng nhập).
  - /verify-password -> xác thực lại mật khẩu hiện tại (cần đăng nhập).

Refresh token KHÔNG bao giờ nằm trong body (JS không đọc được, httpOnly), cookie path-scoped
tới /api/refresh-token nên không gửi kèm các request khác.
"""
from __future__ import annotations

from fastapi import Request, Response

from xime.adapters.web import get, post
from xime.core.config.runtime import RuntimeConfig

from app.dto.request.auth_request import (
    ChangePasswordRequest,
    LoginRequest,
    VerifyPasswordRequest,
)
from app.dto.response.token_response import AccessTokenResponse, MessageResponse
from app.exception.app_exception import AppException
from app.security.cookies import (
    REFRESH_COOKIE_NAME,
    clear_refresh_cookie,
    set_refresh_cookie,
)
from app.security.current_user import current_jwt, current_user, require_login
from app.service.authentication_service import AuthenticationService
from app.service.user_service import UserService


class SecurityController:
    prefix = "/api"
    tags = ["security"]

    def __init__(
        self,
        config: RuntimeConfig,
        authentication_service: AuthenticationService,
        user_service: UserService,
    ) -> None:
        self._auth_svc = authentication_service
        self._user_svc = user_service
        self._refresh_ttl: int = config.get("jwt.refresh_ttl", 5184000)
        self._cookie_secure: bool = config.get("cookie.secure", False)
        self._cookie_samesite: str = config.get("cookie.samesite", "lax")

    @post("/login", status_code=200)
    async def login(self, body: LoginRequest, response: Response) -> AccessTokenResponse:
        """Đăng nhập: trả access token (body) + refresh token (httpOnly cookie)."""
        if current_user() is not None:
            raise AppException("S0000")

        user = await self._user_svc.verify_user_password(body.username, body.password)

        # Create refresh token first, then access token referencing it
        # Tạo refresh token trước, sau đó access token tham chiếu đến nó
        refresh_token = await self._auth_svc.create_token(user, "refresh")
        refresh_id = self._auth_svc.extract_token_id(refresh_token)
        if not refresh_id:
            raise RuntimeError("Failed to extract refresh token id")
        access_token = await self._auth_svc.create_token(user, "access", refresh_id)

        set_refresh_cookie(
            response,
            refresh_token,
            max_age=self._refresh_ttl,
            secure=self._cookie_secure,
            samesite=self._cookie_samesite,
        )
        return AccessTokenResponse(accessToken=access_token)

    @post("/refresh-token", status_code=200)
    async def refresh_token(self, request: Request, response: Response) -> AccessTokenResponse:
        """Cấp lại access token từ refresh token trong cookie, đồng thời xoay refresh mới."""
        refresh = request.cookies.get(REFRESH_COOKIE_NAME)
        if not refresh:
            raise AppException("E2050")

        access_token, new_refresh = await self._auth_svc.rotate_tokens(refresh)
        set_refresh_cookie(
            response,
            new_refresh,
            max_age=self._refresh_ttl,
            secure=self._cookie_secure,
            samesite=self._cookie_samesite,
        )
        return AccessTokenResponse(accessToken=access_token)

    @get("/logout", status_code=200)
    async def logout(self, response: Response) -> MessageResponse:
        """Đăng xuất - thu hồi access token, xóa refresh token + xóa cookie."""
        jwt_str = current_jwt()
        if not jwt_str:
            raise AppException("E2025")
        await self._auth_svc.logout(jwt_str)
        clear_refresh_cookie(response, self._cookie_secure, self._cookie_samesite)
        return MessageResponse(message="Logout successful")

    @post("/change-password", status_code=200)
    async def change_password(self, body: ChangePasswordRequest) -> MessageResponse:
        """Đổi mật khẩu (cần đăng nhập)."""
        user = require_login()
        await self._user_svc.change_user_password(
            user, body.currentPassword, body.newPassword
        )
        return MessageResponse(message="Password changed successfully.")

    @post("/verify-password", status_code=200)
    async def verify_password(self, body: VerifyPasswordRequest) -> MessageResponse:
        """Xác thực lại mật khẩu hiện tại (cần đăng nhập)."""
        user = require_login()
        is_valid = await self._user_svc.verify_password(user, body.password)
        if not is_valid:
            raise AppException("E1024")
        return MessageResponse(message="Password is correct.")
