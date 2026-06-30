"""
AuthAccountController - các luồng tài khoản qua email bảo mật (gửi ĐỒNG BỘ):
xác minh email, quên/đặt lại mật khẩu, OTP.

Xem .claude/docs/thiet-ke-email.md. Token/mã quản lý bởi AuthTokenService (bảng auth_tokens chung).
"""
from __future__ import annotations

import logging

from xime.adapters.web.routing import post
from xime.starters.mail import MailError

from app.dto.request.account_request import (
    ForgotPasswordRequest,
    OtpVerifyRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
)
from app.dto.response.token_response import MessageResponse
from app.exception.app_exception import AppException
from app.security.current_user import require_login
from app.service.auth_token_service import AuthTokenService
from app.service.email_service import EmailService
from app.service.refresh_token_service import RefreshTokenService
from app.service.user_service import UserService

logger = logging.getLogger(__name__)


class AuthAccountController:
    prefix = "/api"
    tags = ["account"]

    def __init__(
        self,
        auth_token_service: AuthTokenService,
        user_service: UserService,
        email_service: EmailService,
        refresh_token_service: RefreshTokenService,
    ) -> None:
        self._tokens = auth_token_service
        self._user_svc = user_service
        self._email = email_service
        self._refresh_svc = refresh_token_service

    # ── Xác minh email ──────────────────────────────────────────────────────────

    @post("/verify-email", status_code=200)
    async def verify_email(self, body: VerifyEmailRequest) -> MessageResponse:
        # Công khai: token trong email định danh user.
        user_id = await self._tokens.consume_token("verify_email", body.token)
        await self._user_svc.mark_email_verified(user_id)
        return MessageResponse(message="Email đã được xác minh.")

    @post("/verify-email/resend", status_code=200)
    async def resend_verify_email(self) -> MessageResponse:
        # Cần đăng nhập: gửi lại email xác minh cho chính user.
        user = require_login()
        token = await self._tokens.create_verify_email(user.id)
        try:
            await self._email.send_verify_email(user.email, token)
        except MailError as exc:
            raise AppException("E1027") from exc
        return MessageResponse(message="Đã gửi email xác minh.")

    # ── Quên / Đặt lại mật khẩu ─────────────────────────────────────────────────

    @post("/forgot-password", status_code=200)
    async def forgot_password(self, body: ForgotPasswordRequest) -> MessageResponse:
        # Công khai. Luôn trả 200 dù email không tồn tại (tránh dò tài khoản).
        user = await self._user_svc.get_user_by_email(body.email)
        if user is not None:
            token = await self._tokens.create_reset_password(user.id)
            try:
                await self._email.send_reset_password(user.email, token)
            except MailError:
                # Nuốt lỗi gửi để không lộ email có tồn tại hay không
                logger.exception("Gửi email reset mật khẩu thất bại cho %s", user.email)
        return MessageResponse(
            message="Nếu email tồn tại, chúng tôi đã gửi liên kết đặt lại mật khẩu."
        )

    @post("/reset-password", status_code=200)
    async def reset_password(self, body: ResetPasswordRequest) -> MessageResponse:
        # Công khai: token trong email định danh user.
        user_id = await self._tokens.consume_token("reset_password", body.token)
        await self._user_svc.set_password(user_id, body.new_password)
        # Thu hồi MỌI refresh token của user (quyết định: chỉ thu hồi khi reset qua quên mật khẩu)
        await self._refresh_svc.delete_by_user(user_id)
        return MessageResponse(message="Đặt lại mật khẩu thành công. Vui lòng đăng nhập lại.")

    # ── OTP ─────────────────────────────────────────────────────────────────────

    @post("/otp/request", status_code=200)
    async def request_otp(self) -> MessageResponse:
        # Cần đăng nhập: gửi OTP tới email của user (gửi đồng bộ).
        user = require_login()
        code = await self._tokens.create_otp(user.id)
        try:
            await self._email.send_otp(user.email, code)
        except MailError as exc:
            raise AppException("E1027") from exc
        return MessageResponse(message="Đã gửi mã OTP tới email của bạn.")

    @post("/otp/verify", status_code=200)
    async def verify_otp(self, body: OtpVerifyRequest) -> MessageResponse:
        user = require_login()
        await self._tokens.consume_otp(user.id, body.otp)
        return MessageResponse(message="Xác thực OTP thành công.")
