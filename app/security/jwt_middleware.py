"""
JwtMiddleware - xác thực Bearer JWT cho mỗi request.
Port từ JwtAuthenticatorListener.php.

Pure-ASGI middleware (KHÔNG dùng starlette BaseHTTPMiddleware). Lý do: BaseHTTPMiddleware
chạy app downstream trong một task anyio riêng, nên ContextVar identity set ở đây không cùng
context với handler -> framework không clear được -> rò identity sang request sau khi chạy
in-process (xem dental-clinic issue-001 và CHANGELOG Xime 0.5.0). Pure-ASGI gọi downstream NGAY
trong cùng context, nên identity do set_current_user() đặt sẽ được RequestContextMiddleware của
framework dọn ở cuối mỗi request (clear_security()).

Logic:
  - Không có header Authorization -> bỏ qua (request ẩn danh; controller tự quyết định)
  - Header không bắt đầu "Bearer " -> 401 E1023
  - Mọi lỗi trong quá trình xác thực -> 401 E1023 (giống PHP catch-all)
"""
from __future__ import annotations

import json

from app.security.current_user import set_current_user
from app.service.authentication_service import AuthenticationService
from app.service.blacklist_token_service import BlacklistTokenService
from app.service.user_service import UserService

_E1023_BODY = {"errorKey": "E1023", "code": 1023, "message": "Không thể xác thực"}
_E1023_BYTES = json.dumps(_E1023_BODY, ensure_ascii=False).encode("utf-8")


class JwtMiddleware:
    """Validate Bearer JWT -> check blacklist -> load user into security context.
    Xác thực JWT -> kiểm tra blacklist -> nạp user vào security context.
    """

    def __init__(
        self,
        app,
        auth_svc: AuthenticationService,
        user_svc: UserService,
        blacklist_svc: BlacklistTokenService,
    ) -> None:
        self.app = app
        self._auth_svc = auth_svc
        self._user_svc = user_svc
        self._blacklist_svc = blacklist_svc

    async def __call__(self, scope, receive, send) -> None:
        # Chỉ xử lý request HTTP; websocket/lifespan đi thẳng qua.
        # Only handle HTTP requests; websocket/lifespan pass through.
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        auth_header = self._header(scope, b"authorization")

        if not auth_header:
            # Anonymous request - pass through; controller decides if login is needed
            # Request ẩn danh - tiếp tục; controller quyết định có cần đăng nhập không
            await self.app(scope, receive, send)
            return

        if not auth_header.startswith("Bearer "):
            await self._send_401(send)
            return

        jwt_str = auth_header[7:]
        try:
            claims = self._auth_svc.validate_token(jwt_str)

            # Reject blacklisted tokens (e.g. after logout)
            # Từ chối token đã bị thu hồi (ví dụ sau khi đăng xuất)
            token_id: str = claims["jti"]
            if await self._blacklist_svc.is_blacklisted(token_id):
                await self._send_401(send)
                return

            # Only access tokens are allowed in Authorization header
            # Chỉ chấp nhận access token trong header Authorization
            if claims.get("type") != "access":
                await self._send_401(send)
                return

            uid: int = claims["uid"]
            user = await self._user_svc.get_user_by_id(uid)
            if not user or not user.is_active:
                await self._send_401(send)
                return

            set_current_user(user, jwt_str)

        except Exception:
            # Any unexpected error during auth -> generic 401 (same as PHP catch-all)
            # Mọi lỗi không mong đợi khi xác thực -> 401 chung (giống PHP catch-all)
            await self._send_401(send)
            return

        await self.app(scope, receive, send)

    @staticmethod
    def _header(scope, name: bytes) -> str | None:
        """Đọc một header (bytes) từ scope ASGI, trả về str hoặc None."""
        for key, value in scope.get("headers", ()):
            if key == name:
                return value.decode("latin-1")
        return None

    @staticmethod
    async def _send_401(send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [(b"content-type", b"application/json; charset=utf-8")],
            }
        )
        await send({"type": "http.response.body", "body": _E1023_BYTES})
