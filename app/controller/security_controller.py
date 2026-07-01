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
from app.service.rate_limiter_service import RateLimiterService
from app.service.refresh_token_service import RefreshTokenService
from app.service.user_service import UserService

# Chống dò mật khẩu: tối đa 5 lần đăng nhập SAI cho mỗi username trong 15 phút.
# Login brute-force guard: max 5 FAILED logins per username per 15 minutes.
_LOGIN_MAX_FAILS = 5
_LOGIN_WINDOW = 15 * 60


class SecurityController:
    prefix = "/api"
    tags = ["security"]

    def __init__(
        self,
        config: RuntimeConfig,
        authentication_service: AuthenticationService,
        user_service: UserService,
        rate_limiter_service: RateLimiterService,
        refresh_token_service: RefreshTokenService,
    ) -> None:
        self._auth_svc = authentication_service
        self._user_svc = user_service
        self._rate = rate_limiter_service
        self._refresh_svc = refresh_token_service
        self._refresh_ttl: int = config.get("jwt.refresh_ttl", 5184000)
        self._cookie_secure: bool = config.get("cookie.secure", False)
        self._cookie_samesite: str = config.get("cookie.samesite", "lax")

    @post("/login", status_code=200)
    async def login(self, body: LoginRequest, response: Response) -> AccessTokenResponse:
        """Đăng nhập: trả access token (body) + refresh token (httpOnly cookie)."""
        if current_user() is not None:
            raise AppException("S0000")

        # Rate limit theo username: chặn nếu đã sai quá ngưỡng; đếm mỗi lần SAI, reset khi ĐÚNG.
        # Per-username rate limit: block if too many failures; count on failure, reset on success.
        rl_key = f"rl:login:{body.username.strip().lower()}"
        await self._rate.ensure(rl_key, _LOGIN_MAX_FAILS, error_key="E2003")
        try:
            user = await self._user_svc.verify_user_password(body.username, body.password)
        except AppException:
            await self._rate.hit(rl_key, _LOGIN_WINDOW)
            raise
        await self._rate.reset(rl_key)

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

    async def _logout(self, response: Response) -> MessageResponse:
        """Thu hồi access token, xóa refresh token + xóa cookie (dùng chung cho GET và POST)."""
        jwt_str = current_jwt()
        if not jwt_str:
            raise AppException("E2025")
        await self._auth_svc.logout(jwt_str)
        clear_refresh_cookie(response, self._cookie_secure, self._cookie_samesite)
        return MessageResponse(message="Logout successful")

    @post("/logout", status_code=200)
    async def logout_post(self, response: Response) -> MessageResponse:
        """Đăng xuất (chuẩn REST: thao tác có side-effect nên dùng POST)."""
        return await self._logout(response)

    @get("/logout", status_code=200)
    async def logout(self, response: Response) -> MessageResponse:
        """Đăng xuất - GIỮ GET để tương thích ngược frontend đang gọi GET (POST là bản chuẩn)."""
        return await self._logout(response)

    @post("/change-password", status_code=200)
    async def change_password(self, body: ChangePasswordRequest) -> MessageResponse:
        """Đổi mật khẩu (cần đăng nhập). Tùy chọn đăng xuất các phiên đăng nhập KHÁC
        (giữ nguyên phiên hiện tại)."""
        user = require_login()
        await self._user_svc.change_user_password(
            user, body.currentPassword, body.newPassword
        )
        # Nếu người dùng tích "đăng xuất các phiên khác": thu hồi refresh token của mọi phiên
        # khác, giữ lại refresh token gắn với access token hiện tại (phiên đang dùng không bị out).
        # If requested, revoke other sessions' refresh tokens, keeping the current session alive.
        if body.logoutOtherSessions:
            keep_refresh_id: str | None = None
            jwt_str = current_jwt()
            if jwt_str:
                keep_refresh_id = self._auth_svc.validate_token(jwt_str).get("refreshId")
            await self._refresh_svc.delete_by_user_except(user.id, keep_refresh_id)
        return MessageResponse(message="Password changed successfully.")

    @post("/verify-password", status_code=200)
    async def verify_password(self, body: VerifyPasswordRequest) -> MessageResponse:
        """Xác thực lại mật khẩu hiện tại (cần đăng nhập)."""
        user = require_login()
        is_valid = await self._user_svc.verify_password(user, body.password)
        if not is_valid:
            raise AppException("E1024")
        return MessageResponse(message="Password is correct.")
