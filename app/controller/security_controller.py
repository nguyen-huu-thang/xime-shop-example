"""
SecurityController — xác thực: đăng nhập, đăng xuất, refresh token, đổi mật khẩu.
Port từ SecurityController.php — giữ nguyên path, method, mã lỗi.
"""
from __future__ import annotations

from xime.adapters.web import get, post

from app.dto.request.auth_request import (
    ChangePasswordRequest,
    LoginRequest,
    RefreshTokenRequest,
    VerifyPasswordRequest,
)
from app.dto.response.token_response import (
    AccessTokenResponse,
    MessageResponse,
    RefreshTokenResponse,
    TokenResponse,
)
from app.exception.app_exception import AppException
from app.security.current_user import current_jwt, current_user, require_login
from app.service.authentication_service import AuthenticationService
from app.service.user_service import UserService


class SecurityController:
    prefix = "/api"
    tags = ["security"]

    def __init__(
        self,
        authentication_service: AuthenticationService,
        user_service: UserService,
    ) -> None:
        self._auth_svc = authentication_service
        self._user_svc = user_service

    @post("/login", status_code=200)
    async def login(self, body: LoginRequest) -> TokenResponse:
        """Đăng nhập, nhận access + refresh token."""
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

        return TokenResponse(accessToken=access_token, refreshToken=refresh_token)

    @post("/refresh-token", status_code=200)
    async def refresh_token(self, body: RefreshTokenRequest) -> AccessTokenResponse:
        """Cấp lại access token từ refresh token."""
        access_token = await self._auth_svc.refresh_access_token(body.refreshToken)
        return AccessTokenResponse(accessToken=access_token)

    @get("/logout", status_code=200)
    async def logout(self) -> MessageResponse:
        """Đăng xuất — thu hồi access token, xóa refresh token."""
        jwt_str = current_jwt()
        if not jwt_str:
            raise AppException("E2025")
        await self._auth_svc.logout(jwt_str)
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

    @post("/refresh-refresh-token", status_code=200)
    async def refresh_refresh_token(self, body: RefreshTokenRequest) -> RefreshTokenResponse:
        """Cấp lại refresh token mới (giữ access token hiện tại)."""
        new_refresh = await self._auth_svc.refresh_refresh_token(body.refreshToken)
        return RefreshTokenResponse(refreshToken=new_refresh)
