"""
AuthTokenService - quản lý token/mã dùng một lần cho email bảo mật (1 bảng auth_tokens chung).

Loại: 'verify_email' (xác minh email), 'reset_password' (đặt lại mật khẩu), 'otp'.
Token thô CHỈ trả về lúc tạo (để nhúng vào email); DB chỉ lưu SHA-256 hash.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from xime.core.transaction.manager import TransactionManager

from app.entity.auth_token import AuthToken
from app.exception.app_exception import AppException
from app.repository.auth_token_repository import AuthTokenRepository

# TTL từng loại (giây)
VERIFY_EMAIL_TTL = 24 * 3600       # 24 giờ
RESET_PASSWORD_TTL = 30 * 60       # 30 phút
OTP_TTL = 5 * 60                   # 5 phút

# Số lần nhập OTP sai tối đa trước khi vô hiệu mã
MAX_OTP_ATTEMPTS = 5


class AuthTokenService:
    def __init__(
        self,
        transaction: TransactionManager,
        auth_token_repository: AuthTokenRepository,
    ) -> None:
        self._transaction = transaction
        self._repo = auth_token_repository

    @staticmethod
    def _hash(raw: str) -> str:
        return hashlib.sha256(raw.encode()).hexdigest()

    async def _create(
        self, user_id: int, type_: str, ttl_seconds: int, raw: str
    ) -> str:
        """Lưu token (hash) cho user; vô hiệu các token chưa dùng cùng loại trước đó. Trả raw."""
        expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
        async with self._transaction():
            await self._repo.invalidate_unused_for_user(user_id, type_)
            await self._repo.save(
                AuthToken(
                    user_id=user_id,
                    type=type_,
                    token_hash=self._hash(raw),
                    expires_at=expires_at,
                )
            )
        return raw

    # ── Tạo token ───────────────────────────────────────────────────────────────

    async def create_verify_email(self, user_id: int) -> str:
        return await self._create(
            user_id, "verify_email", VERIFY_EMAIL_TTL, secrets.token_urlsafe(32)
        )

    async def create_reset_password(self, user_id: int) -> str:
        return await self._create(
            user_id, "reset_password", RESET_PASSWORD_TTL, secrets.token_urlsafe(32)
        )

    async def create_otp(self, user_id: int) -> str:
        # Mã 6 số
        code = f"{secrets.randbelow(10**6):06d}"
        return await self._create(user_id, "otp", OTP_TTL, code)

    # ── Tiêu thụ token ──────────────────────────────────────────────────────────

    async def consume_token(self, type_: str, raw: str) -> int:
        """Tiêu thụ token định danh user (verify_email/reset_password). Trả user_id.
        Lỗi E1025 nếu token không hợp lệ / hết hạn / đã dùng.
        """
        async with self._transaction():
            token = await self._repo.find_active_by_hash(type_, self._hash(raw))
            if not token:
                raise AppException("E1025")
            token.used_at = datetime.now(UTC)
            await self._repo.save(token)
            return token.user_id

    async def consume_otp(self, user_id: int, raw: str) -> None:
        """Tiêu thụ OTP của user. Lỗi E1026 nếu sai/hết hạn (đếm số lần thử)."""
        async with self._transaction():
            token = await self._repo.find_active_for_user(user_id, "otp")
            if not token:
                raise AppException("E1026")
            if token.token_hash == self._hash(raw):
                token.used_at = datetime.now(UTC)
                await self._repo.save(token)
                return
            # Sai mã -> tăng số lần thử; quá ngưỡng -> vô hiệu mã
            token.attempts += 1
            if token.attempts >= MAX_OTP_ATTEMPTS:
                token.used_at = datetime.now(UTC)
            await self._repo.save(token)
            raise AppException("E1026")
