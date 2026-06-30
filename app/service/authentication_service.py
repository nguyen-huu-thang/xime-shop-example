"""
AuthenticationService - tạo/xác thực JWT, refresh, logout.
Port từ AuthenticationService.php (HS256, claims: jti/uid/type/refreshId/reuseCount).
"""
from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

import jwt as pyjwt
from jwt import ExpiredSignatureError, PyJWTError

from xime.core.config.runtime import RuntimeConfig

from app.entity.user import User
from app.exception.app_exception import AppException
from app.service.blacklist_token_service import BlacklistTokenService
from app.service.refresh_token_service import RefreshTokenService
from app.service.user_service import UserService


class AuthenticationService:
    def __init__(
        self,
        config: RuntimeConfig,
        refresh_token_service: RefreshTokenService,
        blacklist_token_service: BlacklistTokenService,
        user_service: UserService,
    ) -> None:
        self._secret: str = config.get("jwt.secret", "dev-secret-CHANGE-IN-PRODUCTION")
        self._issuer: str = config.get("jwt.issuer", "https://scime.click")
        self._audience: str = config.get("jwt.audience", "https://shop.scime.click")
        self._access_ttl: int = config.get("jwt.access_ttl", 3600)
        self._refresh_ttl: int = config.get("jwt.refresh_ttl", 5184000)
        self._refresh_svc = refresh_token_service
        self._blacklist_svc = blacklist_token_service
        self._user_svc = user_service

    # ── Token creation ─────────────────────────────────────────────────────────

    async def create_token(
        self,
        user: User,
        token_type: str,
        refresh_token_id: str | None = None,
        reuse_count: int = 0,
    ) -> str:
        """Create a signed JWT. For type='refresh', also persists jti to DB.
        Tạo JWT đã ký. Với type='refresh', lưu jti vào bảng refresh_tokens.
        """
        if token_type not in ("access", "refresh"):
            raise ValueError(f"Invalid token type: {token_type!r}")
        if token_type == "access" and not refresh_token_id:
            raise ValueError("refresh_token_id is required for access tokens")

        now = datetime.now(UTC)
        ttl = self._access_ttl if token_type == "access" else self._refresh_ttl
        expires_at = now + timedelta(seconds=ttl)
        # 64-char hex id - same as PHP: bin2hex(random_bytes(32))
        jti = secrets.token_hex(32)

        payload: dict = {
            "jti": jti,
            "iss": self._issuer,
            "aud": self._audience,
            "iat": now,
            "exp": expires_at,
            "uid": user.id,
            "username": user.username,
            "email": user.email,
            "isActive": user.is_active,
            "type": token_type,
        }
        if token_type == "access":
            payload["refreshId"] = refresh_token_id
        if token_type == "refresh":
            payload["reuseCount"] = reuse_count

        token_str: str = pyjwt.encode(payload, self._secret, algorithm="HS256")

        if token_type == "refresh":
            await self._refresh_svc.create_token(jti, expires_at, user.id)

        return token_str

    # ── Token validation ───────────────────────────────────────────────────────

    def validate_token(self, token_str: str) -> dict:
        """Parse and validate JWT signature + claims. Sync - no DB.
        Xác thực chữ ký và claims của JWT. Không cần DB.
        """
        try:
            claims: dict = pyjwt.decode(
                token_str,
                self._secret,
                algorithms=["HS256"],
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["jti", "exp", "iss", "aud"]},
            )
        except ExpiredSignatureError:
            raise AppException("E1021")
        except PyJWTError:
            raise AppException("E1020")
        return claims

    def extract_token_id(self, token_str: str) -> str | None:
        """Extract jti from token string. Returns None on any error.
        Lấy jti từ chuỗi token - trả None nếu có lỗi.
        """
        try:
            return self.validate_token(token_str).get("jti")
        except Exception:
            return None

    # ── Auth flows ─────────────────────────────────────────────────────────────

    async def rotate_tokens(self, refresh_token_str: str) -> tuple[str, str]:
        """Validate a refresh token, then issue a fresh access + a rotated refresh token.

        Trả về (access_token, new_refresh_token). Refresh token cũ bị thu hồi (one-time use):
        mỗi lần gọi /refresh-token vừa cấp access mới (body) vừa xoay refresh mới (đặt lại
        cookie). Refresh mới có TTL trượt (60 ngày kể từ bây giờ) nên phiên duy trì khi người
        dùng còn hoạt động, tối đa tới mốc 60 ngày không refresh thì hết hạn.

        Ghi chú: bản PHP gốc giới hạn reuseCount <= 12 cho thao tác xoay refresh thủ công.
        Khi gộp xoay vào mỗi lần refresh access, giới hạn đó sẽ buộc đăng nhập lại sau ~12 lần
        nên ta bỏ chặn cứng; vẫn tăng reuseCount để phục vụ audit/phát hiện bất thường.
        """
        claims = self.validate_token(refresh_token_str)
        if claims.get("type") != "refresh":
            raise AppException("E2050")

        old_jti: str = claims["jti"]
        uid: int = claims["uid"]
        reuse_count: int = claims.get("reuseCount", 0)

        stored = await self._refresh_svc.get_token_by_id(old_jti)
        if not stored:
            raise AppException("E2050")
        if stored.expires_at < datetime.now(UTC):
            raise AppException("E2051")

        user = await self._user_svc.get_user_by_id(uid)
        if not user:
            raise AppException("E1004")

        # Issue rotated refresh first, then an access token referencing it.
        # Cấp refresh mới trước, sau đó access token tham chiếu tới nó.
        new_refresh = await self.create_token(user, "refresh", reuse_count=reuse_count + 1)
        new_refresh_id = self.extract_token_id(new_refresh)
        if not new_refresh_id:
            raise RuntimeError("Failed to extract rotated refresh token id")
        access_token = await self.create_token(user, "access", new_refresh_id)

        # Revoke the old refresh token so it cannot be reused.
        # Thu hồi refresh token cũ để không thể tái sử dụng.
        await self._refresh_svc.delete_token(old_jti)

        return access_token, new_refresh

    async def logout(self, access_token_str: str) -> None:
        """Blacklist access token + delete its paired refresh token.
        Thu hồi access token và xóa refresh token liên kết.
        """
        claims = self.validate_token(access_token_str)

        jti: str = claims["jti"]
        exp_ts: int = claims["exp"]  # Unix timestamp from PyJWT
        refresh_id: str | None = claims.get("refreshId")

        if not refresh_id:
            raise AppException("E2050")

        expires_at = datetime.fromtimestamp(exp_ts, UTC)
        await self._blacklist_svc.add_token(jti, expires_at)
        await self._refresh_svc.delete_token(refresh_id)
