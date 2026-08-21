"""
AuthenticationService - tạo/xác thực JWT, refresh, logout.
Port từ AuthenticationService.php (HS256, claims: jti/uid/type/refreshId/reuseCount).

Đổi 2026-08-21: ký/verify đi qua JwtTokenSigner / JwtTokenVerifier của Xime (starter jwt) thay
vì gọi thẳng pyjwt. Ba thứ lấy được mà bản tự viết không có:

- `kid` trong header token + nhiều khóa ứng viên lúc verify -> XOAY ĐƯỢC KHÓA mà không đăng
  xuất toàn bộ người dùng (xem app/security/jwt_key_provider.py).
- `leeway`: dung sai đồng hồ cho exp/nbf/iat. Thiếu nó thì hai máy lệch vài giây sinh 401 chập
  chờn, và đó là loại lỗi không ai tái hiện được trên máy dev.
- `algorithms` là DANH SÁCH TRẮNG áp trước khi kiểm chữ ký: khóa khai thuật toán ngoài danh
  sách bị từ chối, token không tự chọn được thuật toán yếu hơn.

Vẫn giữ pyjwt cho đúng MỘT việc: đọc header chưa verify để lấy `kid` (không cần khóa).
"""
from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

import jwt as pyjwt

from xime.core.config.runtime import RuntimeConfig
from xime.core.exception.framework import AuthenticationException
from xime.starters.jwt import JwtTokenSigner, JwtTokenVerifier

from app.entity.user import User
from app.exception.app_exception import AppException
from app.security.jwt_key_provider import ShopJwtKeyProvider
from app.service.blacklist_token_service import BlacklistTokenService
from app.service.refresh_token_service import RefreshTokenService
from app.service.user_service import UserService

# Claim bắt buộc phải có mặt. `exp` nằm đây là cố ý: PyJWT chỉ kiểm exp KHI claim tồn tại, nên
# token không mang exp sẽ không bao giờ hết hạn.
# `exp` is only checked when present, so a token without it would never expire.
_REQUIRED_CLAIMS = ["jti", "exp", "iss", "aud"]


class AuthenticationService:
    def __init__(
        self,
        config: RuntimeConfig,
        refresh_token_service: RefreshTokenService,
        blacklist_token_service: BlacklistTokenService,
        user_service: UserService,
        signer: JwtTokenSigner,
        verifier: JwtTokenVerifier,
        key_provider: ShopJwtKeyProvider,
    ) -> None:
        self._signer = signer
        self._verifier = verifier
        self._keys = key_provider
        self._algorithms: list[str] = [self._keys.signing_key.algorithm]
        # Dung sai đồng hồ (giây) cho exp/nbf/iat giữa máy ký và máy verify.
        self._leeway: float = config.get("jwt.leeway", 30)
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

        # Ký bằng khóa đang hoạt động; KeyContext.key_id trở thành header `kid`, nhờ đó bên
        # verify định tuyến được token này tới đúng khóa khi khóa đã xoay.
        # Sign with the active key; its key_id becomes the token's `kid` header.
        token_str: str = self._signer.sign(payload, self._keys.signing_key)

        if token_type == "refresh":
            await self._refresh_svc.create_token(jti, expires_at, user.id)

        return token_str

    # ── Token validation ───────────────────────────────────────────────────────

    def validate_token(self, token_str: str) -> dict:
        """Parse and validate JWT signature + claims. Sync - no DB.
        Xác thực chữ ký và claims của JWT. Không cần DB.
        """
        try:
            kid = pyjwt.get_unverified_header(token_str).get("kid")
        except pyjwt.PyJWTError:
            # Header hỏng -> token không phân tích nổi, khỏi bàn tới khóa nào.
            raise AppException("E1020")

        candidates = self._keys.keys(kid)
        if not candidates:
            # Không biết kid này: khóa đã bị loại bỏ, hoặc token của hệ thống khác.
            raise AppException("E1020")

        expired = False
        for key in candidates:
            try:
                return self._verifier.verify(
                    token_str,
                    key,
                    audience=self._audience,
                    issuer=self._issuer,
                    algorithms=self._algorithms,
                    leeway=self._leeway,
                    require=_REQUIRED_CLAIMS,
                )
            except AuthenticationException as exc:
                # Nhiều khóa ứng viên là chuyện bình thường trong cửa sổ xoay khóa: khóa sai
                # thì thử khóa kế. Riêng "hết hạn" thì mọi khóa đều cho cùng kết cục, và nó
                # phải giữ được mã lỗi riêng (E1021) để client biết đường gọi /refresh-token.
                # A wrong key just means "try the next"; an expired token keeps its own code.
                if "expired" in str(exc).lower():
                    expired = True
        raise AppException("E1021" if expired else "E1020")

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
